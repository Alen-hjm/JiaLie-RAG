from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import get_settings
from ..db import get_db
from ..dependencies import current_user
from ..models import Conversation, ConversationMessage, JobRequirement
from ..schemas import ConversationCreateIn, ConversationMessageIn, JobRequirements
from ..services.llm import ModelService, ModelServiceError
from ..services.orchestration import run_orchestrated_search
from ..services.search import search_job
from .jobs import match_dict

router = APIRouter(prefix="/api", tags=["conversations"], dependencies=[Depends(current_user)])


def merge_requirements(previous: JobRequirements | None, incoming: JobRequirements) -> JobRequirements:
    if previous is None:
        return incoming
    data = previous.model_dump()
    incoming_data = incoming.model_dump()
    for key in ("industries", "locations", "skills", "must_have", "preferred", "performance_expectations"):
        if incoming_data[key]:
            data[key] = list(dict.fromkeys([*data[key], *incoming_data[key]]))
    if incoming.title != "未命名岗位":
        data["title"] = incoming.title
    if incoming.minimum_years:
        data["minimum_years"] = incoming.minimum_years
    if incoming.management_required:
        data["management_required"] = True
    return JobRequirements.model_validate(data)


def conversation_out(row: Conversation) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "job_id": row.job_id,
        "requirements": row.requirements_json,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "messages": [
            {"id": m.id, "role": m.role, "content": m.content, "response": m.response_json, "created_at": m.created_at}
            for m in row.messages
        ],
    }


@router.post("/conversations")
def create_conversation(payload: ConversationCreateIn | None = None, db: Session = Depends(get_db)):
    job = JobRequirement(title="未命名岗位", raw_text="", requirements_json=JobRequirements().model_dump())
    row = Conversation(title=(payload.title if payload and payload.title else "新的人才搜索"), job=job, requirements_json=job.requirements_json)
    db.add(row)
    db.commit()
    db.refresh(row)
    return conversation_out(row)


@router.get("/conversations")
def list_conversations(db: Session = Depends(get_db)):
    rows = list(db.scalars(select(Conversation).order_by(Conversation.updated_at.desc()).limit(30)))
    return {"items": [{"id": r.id, "title": r.title, "requirements": r.requirements_json, "updated_at": r.updated_at} for r in rows]}


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, db: Session = Depends(get_db)):
    row = db.scalar(select(Conversation).options(selectinload(Conversation.messages)).where(Conversation.id == conversation_id))
    if not row:
        raise HTTPException(404, detail={"code": "CONVERSATION_NOT_FOUND", "message": "问答会话不存在"})
    return conversation_out(row)


@router.post("/conversations/{conversation_id}/messages")
def send_message(conversation_id: str, payload: ConversationMessageIn, db: Session = Depends(get_db)):
    row = db.scalar(select(Conversation).where(Conversation.id == conversation_id))
    if not row or not row.job:
        raise HTTPException(404, detail={"code": "CONVERSATION_NOT_FOUND", "message": "问答会话不存在"})
    try:
        service = ModelService(db)
        parsed = service.parse_job(payload.content)
    except ModelServiceError as exc:
        # Surface provider/network/configuration failures to the UI as a
        # useful 503 instead of the generic "服务暂时不可用" toast.
        raise HTTPException(
            status_code=503,
            detail={"code": "MODEL_UNAVAILABLE", "message": str(exc)},
        ) from exc
    previous = JobRequirements.model_validate(row.requirements_json) if row.requirements_json else None
    requirements = merge_requirements(previous, parsed)
    row.requirements_json = requirements.model_dump()
    row.title = "-".join([requirements.company or "未指定", requirements.title or "未指定", requirements.locations[0] if requirements.locations else "未指定"])
    row.job.title = requirements.title
    row.job.company = requirements.company
    row.job.location = requirements.locations[0] if requirements.locations else ""
    row.job.raw_text = "\n".join([m.content for m in row.messages if m.role == "user"] + [payload.content])
    row.job.requirements_json = requirements.model_dump()
    user_message = ConversationMessage(conversation_id=row.id, role="user", content=payload.content)
    db.add(user_message)
    db.flush()

    orchestration_info: dict = {"mode": get_settings().orchestration_mode, "steps": []}
    try:
        if get_settings().orchestration_mode == "langgraph":
            result = run_orchestrated_search(db, row.job, 20)
            matches = result["matches"]
            assistant = result["summary"]
            orchestration_info = {
                "mode": "langgraph",
                "attempts": result.get("attempts", 1),
                "steps": result.get("trace", []),
            }
        else:
            matches = search_job(db, row.job, 20)
            assistant = f"我根据“{requirements.title}”整理了 {len(matches)} 位候选人。以下推荐均来自简历可核验内容。"
    except ModelServiceError as exc:
        # 检索链路里的模型调用失败（向量服务超限、网络抖动等）必须给用户一个
        # 明确的 503，而不是让它变成一个看不出原因的 500。
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail={"code": "MODEL_UNAVAILABLE", "message": f"检索暂时失败，请重试：{exc}"},
        ) from exc

    response = {
        "assistant_text": assistant,
        "requirements": requirements.model_dump(),
        "items": [match_dict(match) for match in matches],
        "total": len(matches),
        "follow_up_suggestions": ["只看上海候选人", "把最低经验放宽到 8 年", "优先有晶圆厂客户资源的人"],
        "orchestration": orchestration_info,
    }
    user_message.response_json = response
    db.add(ConversationMessage(conversation_id=row.id, role="assistant", content=assistant, response_json=response))
    db.commit()
    return response


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, db: Session = Depends(get_db)):
    row = db.get(Conversation, conversation_id)
    if not row:
        raise HTTPException(404, detail={"code": "CONVERSATION_NOT_FOUND", "message": "问答会话不存在"})
    job = row.job
    db.delete(row)
    if job:
        db.delete(job)
    db.commit()
