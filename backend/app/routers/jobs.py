from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..dependencies import current_user
from ..models import Conversation, JobRequirement, MatchResult
from ..schemas import JobCreateIn, JobParseIn, JobRequirements, JobUpdateIn, SearchOptions
from ..services.llm import ModelService
from ..services.search import empty_result_hint, search_job

router = APIRouter(prefix="/api", tags=["jobs"], dependencies=[Depends(current_user)])


def match_dict(match: MatchResult) -> dict:
    candidate = match.candidate
    return {
        "id": match.id, "job_id": match.job_id, "total_score": match.total_score,
        "structured_score": match.structured_score, "semantic_score": match.semantic_score,
        "rerank_score": match.rerank_score, "rerank_mode": match.rerank_mode,
        "strengths": match.strengths, "gaps": match.gaps, "evidence": match.evidence,
        "candidate": {
            "id": candidate.id, "name": candidate.name, "location": candidate.location,
            "current_title": candidate.current_title, "years_experience": candidate.years_experience,
            "industries": candidate.industries, "skills": candidate.skills,
            "management_experience": candidate.management_experience,
        },
    }


@router.post("/jobs/parse")
def parse_job(payload: JobParseIn, db: Session = Depends(get_db)):
    requirements = ModelService(db).parse_job(payload.text)
    job = JobRequirement(company=requirements.company, location=(requirements.locations[0] if requirements.locations else ""), title=requirements.title, raw_text=payload.text, requirements_json=requirements.model_dump())
    db.add(job)
    db.commit()
    return {"id": job.id, "title": job.title, "raw_text": job.raw_text, "requirements": job.requirements_json, "created_at": job.created_at}


@router.post("/jobs")
def create_job(payload: JobCreateIn, db: Session = Depends(get_db)):
    requirements = payload.requirements.model_copy(update={"company": payload.company, "title": payload.title})
    job = JobRequirement(company=payload.company, location=(requirements.locations[0] if requirements.locations else ""), title=payload.title, raw_text=payload.raw_text, requirements_json=requirements.model_dump())
    db.add(job); db.commit(); db.refresh(job)
    return {"id": job.id, "title": job.title, "raw_text": job.raw_text, "requirements": job.requirements_json, "created_at": job.created_at, "match_count": 0}


@router.put("/jobs/{job_id}")
def update_job(job_id: str, payload: JobUpdateIn, db: Session = Depends(get_db)):
    job = db.get(JobRequirement, job_id)
    if not job:
        raise HTTPException(404, detail={"code": "JOB_NOT_FOUND", "message": "岗位不存在"})
    job.title = payload.requirements.title
    job.company = payload.requirements.company
    job.location = payload.requirements.locations[0] if payload.requirements.locations else ""
    job.requirements_json = payload.requirements.model_dump()
    db.commit()
    return {"id": job.id, "title": job.title, "raw_text": job.raw_text, "requirements": job.requirements_json}


@router.get("/jobs")
def list_jobs(db: Session = Depends(get_db)):
    jobs = list(db.scalars(select(JobRequirement).order_by(JobRequirement.created_at.desc()).limit(100)))
    return {"items": [{"id": j.id, "company": j.company, "location": j.location, "title": j.title, "created_at": j.created_at, "match_count": len(j.matches), "requirements": j.requirements_json, "conversation_id": db.scalar(select(Conversation.id).where(Conversation.job_id == j.id))} for j in jobs]}


@router.get("/jobs/{job_id}/conversation")
def get_job_conversation(job_id: str, db: Session = Depends(get_db)):
    conversation = db.scalar(select(Conversation).where(Conversation.job_id == job_id))
    if not conversation:
        raise HTTPException(404, detail={"code": "CONVERSATION_NOT_FOUND", "message": "该岗位尚未建立问答会话"})
    return {"conversation_id": conversation.id}


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(JobRequirement, job_id)
    if not job:
        raise HTTPException(404, detail={"code": "JOB_NOT_FOUND", "message": "岗位不存在"})
    conversation = db.scalar(select(Conversation).where(Conversation.job_id == job_id))
    if conversation:
        db.delete(conversation)
    db.delete(job)
    db.commit()


@router.post("/jobs/{job_id}/search")
def run_search(job_id: str, payload: SearchOptions = SearchOptions(), db: Session = Depends(get_db)):
    job = db.get(JobRequirement, job_id)
    if not job:
        raise HTTPException(404, detail={"code": "JOB_NOT_FOUND", "message": "岗位不存在"})
    results = search_job(db, job, payload.limit)
    payload_out = {
        "job": {"id": job.id, "title": job.title, "requirements": job.requirements_json},
        "items": [match_dict(m) for m in results],
        "total": len(results),
    }
    # 空结果最容易被当成"系统不行"。补一句可操作的原因（hint 是可选字段，
    # 老调用方忽略它即可，不影响既有契约）。
    if not results:
        payload_out["hint"] = empty_result_hint(db, JobRequirements.model_validate(job.requirements_json))
    return payload_out


@router.get("/jobs/{job_id}/matches")
def get_matches(job_id: str, db: Session = Depends(get_db)):
    rows = list(db.scalars(select(MatchResult).where(MatchResult.job_id == job_id).order_by(MatchResult.total_score.desc())))
    return {"items": [match_dict(row) for row in rows], "total": len(rows)}


@router.get("/matches/{match_id}")
def get_match(match_id: str, db: Session = Depends(get_db)):
    match = db.get(MatchResult, match_id)
    if not match:
        raise HTTPException(404, detail={"code": "MATCH_NOT_FOUND", "message": "匹配记录不存在"})
    return match_dict(match)
