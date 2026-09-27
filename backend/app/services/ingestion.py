from pathlib import Path
from sqlalchemy import delete, select
from .documents import DocumentParseError, extract_text, split_chunks
from .llm import ModelService, ModelServiceError
from ..db import SessionLocal
from ..models import CandidateProfile, Experience, ImportTask, ResumeChunk, ResumeDocument


def process_document(document_id: str, task_id: str):
    with SessionLocal() as db:
        document = db.get(ResumeDocument, document_id)
        task = db.get(ImportTask, task_id)
        if not document or not task:
            return
        try:
            task.attempts += 1
            task.status = document.status = "processing"
            task.progress, task.message = 10, "正在提取文档文字"
            db.commit()
            text = extract_text(Path(document.storage_path))
            document.raw_text = text
            task.progress, task.message = 35, "正在提取人才画像"
            db.commit()
            service = ModelService(db)
            profile = service.extract_candidate(text)
            if document.candidate:
                db.delete(document.candidate)
                db.flush()
            candidate = CandidateProfile(
                document_id=document.id, name=profile.name, email=profile.email, phone=profile.phone,
                location=profile.location, current_title=profile.current_title,
                years_experience=profile.years_experience, industries=profile.industries,
                skills=profile.skills, highlights=profile.highlights,
                management_experience=profile.management_experience, profile_json=profile.model_dump(),
            )
            db.add(candidate)
            db.flush()
            for exp in profile.experiences:
                db.add(Experience(candidate_id=candidate.id, **exp.model_dump()))
            task.progress, task.message = 60, "正在向量化并写入索引"
            task.status = document.status = "vectorizing"
            db.commit()
            chunks = split_chunks(text)
            vectors = service.embed([chunk["content"] for chunk in chunks])
            for index, (chunk, vector) in enumerate(zip(chunks, vectors)):
                db.add(ResumeChunk(candidate_id=candidate.id, chunk_index=index, embedding=vector, **chunk))
            task.status = document.status = "completed"
            task.progress, task.message = 100, "解析与索引完成"
            document.error_code = document.error_message = None
            db.commit()
        except (DocumentParseError, ModelServiceError) as exc:
            db.rollback()
            document = db.get(ResumeDocument, document_id)
            task = db.get(ImportTask, task_id)
            document.status = task.status = "failed"
            document.error_code = type(exc).__name__
            document.error_message = str(exc)
            task.message = str(exc)[:255]
            db.commit()
        except Exception as exc:
            db.rollback()
            document = db.get(ResumeDocument, document_id)
            task = db.get(ImportTask, task_id)
            if document and task:
                document.status = task.status = "failed"
                document.error_code = "INTERNAL_ERROR"
                document.error_message = str(exc)
                task.message = "处理失败，请查看服务日志"
                db.commit()
