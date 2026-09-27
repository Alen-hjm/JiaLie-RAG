from sqlalchemy import select

from app.db import SessionLocal
from app.models import ResumeDocument


with SessionLocal() as db:
    seen: set[str] = set()
    documents = db.scalars(select(ResumeDocument).order_by(ResumeDocument.created_at)).all()
    for document in documents:
        if document.filename in seen:
            db.delete(document)
        else:
            seen.add(document.filename)
    db.commit()
print("Demo duplicates cleaned.")
