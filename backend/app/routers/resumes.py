import hashlib
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from ..config import get_settings
from ..db import get_db
from ..dependencies import current_user
from ..models import AdminUser, CandidateProfile, ImportTask, ResumeDocument
from ..schemas import CandidateSummary, ImportTaskOut
from ..services.ingestion import process_document

router = APIRouter(prefix="/api", tags=["resumes"], dependencies=[Depends(current_user)])


def normalize_filename(raw: str | None, suffix: str) -> str:
    """Repair non-ASCII multipart filenames.

    Browsers send the ``filename=`` field as raw UTF-8 bytes, but Starlette's
    multipart parser decodes the header as latin-1, so a Chinese resume name
    arrives as mojibake (``½¯×Óºã_°ëµ¼Ìå....docx``).  Re-encoding back through
    latin-1 recovers the original text when that is what happened, and leaves
    genuine ASCII names untouched.
    """
    if not raw:
        return f"resume{suffix}"
    try:
        repaired = raw.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return raw
    return repaired


@router.post("/resumes/import")
async def import_resumes(background: BackgroundTasks, files: list[UploadFile] = File(...), db: Session = Depends(get_db)):
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    accepted, duplicates, rejected = [], [], []
    for upload in files:
        suffix = Path(upload.filename or "").suffix.lower()
        filename = normalize_filename(upload.filename, suffix)
        content = await upload.read()
        if suffix not in {".pdf", ".docx"}:
            rejected.append({"filename": filename, "reason": "仅支持 PDF、DOCX"})
            continue
        if len(content) > settings.max_upload_mb * 1024 * 1024:
            rejected.append({"filename": filename, "reason": f"文件超过 {settings.max_upload_mb} MB"})
            continue
        digest = hashlib.sha256(content).hexdigest()
        existing = db.scalar(select(ResumeDocument).where(ResumeDocument.sha256 == digest))
        if existing:
            duplicates.append({"filename": filename, "document_id": existing.id})
            continue
        document = ResumeDocument(filename=filename, content_type=upload.content_type or "application/octet-stream", sha256=digest, storage_path="")
        db.add(document)
        db.flush()
        target = settings.upload_dir / f"{document.id}{suffix}"
        target.write_bytes(content)
        document.storage_path = str(target)
        task = ImportTask(document_id=document.id)
        db.add(task)
        db.commit()
        accepted.append({"document_id": document.id, "task_id": task.id, "filename": document.filename})
        background.add_task(process_document, document.id, task.id)
    return {"accepted": accepted, "duplicates": duplicates, "rejected": rejected}


@router.get("/import-tasks/{task_id}", response_model=ImportTaskOut)
def get_task(task_id: str, db: Session = Depends(get_db)):
    task = db.get(ImportTask, task_id)
    if not task:
        raise HTTPException(404, detail={"code": "TASK_NOT_FOUND", "message": "导入任务不存在"})
    return task


@router.post("/import-tasks/{task_id}/retry", response_model=ImportTaskOut)
def retry_task(task_id: str, background: BackgroundTasks, db: Session = Depends(get_db)):
    task = db.get(ImportTask, task_id)
    if not task:
        raise HTTPException(404, detail={"code": "TASK_NOT_FOUND", "message": "导入任务不存在"})
    task.status, task.progress, task.message = "queued", 0, "等待重新处理"
    task.document.status = "queued"
    db.commit()
    background.add_task(process_document, task.document_id, task.id)
    return task


@router.get("/candidates")
def list_candidates(q: str = "", status: str | None = None, db: Session = Depends(get_db)):
    statement = select(ResumeDocument).order_by(ResumeDocument.created_at.desc())
    if status:
        statement = statement.where(ResumeDocument.status == status)
    documents = list(db.scalars(statement))
    rows = []
    for doc in documents:
        candidate = doc.candidate
        if q and q.lower() not in " ".join([doc.filename, candidate.name if candidate else "", candidate.current_title or "" if candidate else ""]).lower():
            continue
        rows.append({
            "document_id": doc.id, "filename": doc.filename, "status": doc.status,
            "error_message": doc.error_message, "created_at": doc.created_at,
            "task": {"id": doc.task.id, "progress": doc.task.progress, "message": doc.task.message} if doc.task else None,
            "candidate": CandidateSummary.model_validate(candidate).model_dump() if candidate else None,
        })
    return {"items": rows, "total": len(rows)}


@router.get("/candidates/{candidate_id}")
def candidate_detail(candidate_id: str, db: Session = Depends(get_db)):
    candidate = db.get(CandidateProfile, candidate_id)
    if not candidate:
        raise HTTPException(404, detail={"code": "CANDIDATE_NOT_FOUND", "message": "候选人不存在"})
    return {
        **CandidateSummary.model_validate(candidate).model_dump(),
        "email": candidate.email, "phone": candidate.phone, "highlights": candidate.highlights,
        "experiences": [{"id": e.id, "company": e.company, "title": e.title, "industry": e.industry, "start_date": e.start_date, "end_date": e.end_date, "description": e.description} for e in candidate.experiences],
        "chunks": [{"id": c.id, "section": c.section, "page_number": c.page_number, "content": c.content} for c in candidate.chunks],
        "filename": candidate.document.filename,
    }


@router.delete("/candidates/{candidate_id}", status_code=204)
def delete_candidate(candidate_id: str, db: Session = Depends(get_db)):
    candidate = db.get(CandidateProfile, candidate_id)
    if not candidate:
        raise HTTPException(404, detail={"code": "CANDIDATE_NOT_FOUND", "message": "候选人不存在"})
    document = candidate.document
    file_path = Path(document.storage_path)
    db.delete(document)
    db.commit()
    # Removing the stored file is best effort.  The database row is already
    # gone, so a locked / already-removed / permission-denied file must not
    # turn a successful delete into a 500: the caller would then believe (and
    # the UI would keep showing) that the deletion failed.
    try:
        if file_path.exists():
            file_path.unlink()
    except OSError as exc:
        print(f"[delete] 数据库记录已删除，但源文件删除失败：{file_path} -> {exc}", flush=True)


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    return {
        "candidate_count": db.scalar(select(func.count()).select_from(CandidateProfile)) or 0,
        "processing_count": db.scalar(select(func.count()).select_from(ResumeDocument).where(ResumeDocument.status.in_(["queued", "processing", "vectorizing"]))) or 0,
        "failed_count": db.scalar(select(func.count()).select_from(ResumeDocument).where(ResumeDocument.status == "failed")) or 0,
    }
