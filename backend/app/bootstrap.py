from sqlalchemy import inspect, select, text

from .config import get_settings
from .db import Base, SessionLocal, engine
from .models import AdminUser
from .security import hash_password


def _ensure_schema() -> None:
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("job_requirements")}
    with engine.begin() as connection:
        if "company" not in columns:
            connection.execute(text("ALTER TABLE job_requirements ADD COLUMN company VARCHAR(255) DEFAULT ''"))
        if "location" not in columns:
            connection.execute(text("ALTER TABLE job_requirements ADD COLUMN location VARCHAR(128) DEFAULT ''"))
    # create_all() never ALTERs an existing table, so columns added after a
    # database was first created have to be backfilled here.
    match_columns = {column["name"] for column in inspector.get_columns("match_results")}
    if "rerank_mode" not in match_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE match_results ADD COLUMN rerank_mode VARCHAR(16) DEFAULT 'rule'"))


def _ensure_admin() -> None:
    settings = get_settings()
    with SessionLocal() as db:
        if not db.scalar(select(AdminUser).where(AdminUser.username == settings.admin_username)):
            db.add(AdminUser(username=settings.admin_username, password_hash=hash_password(settings.admin_password)))
            db.commit()


def bootstrap() -> None:
    """Prepare the database, the admin account and the upload directory.

    Deliberately does NOT re-parse existing resumes.

    The previous version gated a full re-parse on
    ``upload_dir.parent / ".reparse-v2.done"``.  Because the marker path moved
    with UPLOAD_DIR (``./uploads`` -> ``/data/uploads``), the check never
    matched again and *every* startup re-parsed every document and re-ran
    embedding for all of them -- slow locally and, once a real embedding
    provider is configured, repeatedly billed.

    Manual, resumable re-vectorisation now lives in
    ``scripts/reindex_embeddings.py`` so it is an explicit action.
    """
    settings = get_settings()
    _ensure_schema()
    _ensure_admin()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    if settings.embedding_is_placeholder:
        print(
            "[bootstrap] 向量化当前使用本地哈希占位向量（无语义）。"
            "配置真实 embedding 后请执行: python -m scripts.reindex_embeddings"
        )


if __name__ == "__main__":
    bootstrap()
