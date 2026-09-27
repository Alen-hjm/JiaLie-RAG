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


# 这里写的是 config.py 里那几个字段的**出厂默认值**。只要配置里还是这些值，
# 就说明跑的是"开箱即用"的演示配置，绝不该直接暴露到公网。
_INSECURE_DEFAULTS = {
    "SECRET_KEY": "development-only-change-me",
    "ADMIN_PASSWORD": "minglie123",
}


def check_insecure_settings() -> list[str]:
    """把"能跑、但危险"的配置挑出来。返回告警列表，空列表表示没问题。

    为什么要做这件事：这些默认值让项目 clone 下来就能跑，体验很好——
    但也意味着很容易带着它们上线。SECRET_KEY 用于签发登录令牌，泄露等于
    任何人都能伪造管理员身份；默认管理员密码更是直接开门。

    与其在 README 里写一句没人看的提醒，不如让它在每次启动时自己喊出来——
    告警是幂等的、只打印、不阻断启动，所以不会影响正常开发。
    """
    settings = get_settings()
    warnings: list[str] = []

    if settings.secret_key == _INSECURE_DEFAULTS["SECRET_KEY"]:
        warnings.append("SECRET_KEY 仍是默认值 —— 登录令牌可被伪造，请换成随机字符串")
    if settings.admin_password == _INSECURE_DEFAULTS["ADMIN_PASSWORD"]:
        warnings.append("ADMIN_PASSWORD 仍是默认值 —— 等同于没有密码保护，请立即修改")
    if settings.model_mode != "mock" and not settings.chat_api_key:
        warnings.append(
            f"MODEL_MODE={settings.model_mode} 但没有配置 CHAT_API_KEY —— 岗位解析会直接失败"
        )

    return warnings


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

    for warning in check_insecure_settings():
        print(f"[bootstrap][安全告警] {warning}")

    if settings.embedding_is_placeholder:
        print(
            "[bootstrap] 向量化当前使用本地哈希占位向量（无语义）。"
            "配置真实 embedding 后请执行: python -m scripts.reindex_embeddings"
        )


if __name__ == "__main__":
    bootstrap()
