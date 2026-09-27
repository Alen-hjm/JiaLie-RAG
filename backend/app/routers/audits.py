from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..dependencies import current_user
from ..models import ModelCallAudit

router = APIRouter(prefix="/api/audits", tags=["audits"], dependencies=[Depends(current_user)])


@router.get("")
def list_audits(db: Session = Depends(get_db)):
    rows = list(db.scalars(select(ModelCallAudit).order_by(ModelCallAudit.created_at.desc()).limit(100)))
    return {"items": [{
        "id": x.id, "operation": x.operation, "provider": x.provider, "model": x.model,
        "request_hash": x.request_hash, "status": x.status, "latency_ms": x.latency_ms,
        "input_tokens": x.input_tokens, "output_tokens": x.output_tokens,
        "error_code": x.error_code, "created_at": x.created_at,
    } for x in rows]}

