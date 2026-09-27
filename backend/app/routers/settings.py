from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import EMBEDDING_PRESETS, PROJECT_ENV_FILE, get_settings
from ..db import get_db
from ..dependencies import current_user
from ..schemas import SettingsUpdateIn
from ..services.llm import ModelService, ModelServiceError
from ..services.search import resolve_rerank_mode
from ..services.vectors import vector_stats

router = APIRouter(prefix="/api/settings", tags=["settings"], dependencies=[Depends(current_user)])


def env_path():
    """The project root .env is the single source of truth.

    Previously this returned ``backend/.env`` whenever that file existed, so
    saving from the UI wrote to a different file than the one the app actually
    loaded first -- the two then disagreed about model mode and database URL.
    """
    return PROJECT_ENV_FILE


def read_env() -> dict[str, str]:
    path = env_path()
    values: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def write_env(updates: dict[str, str]) -> None:
    path = env_path()
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    seen: set[str] = set()
    output: list[str] = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else ""
        if key in updates:
            output.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            output.append(line)
    for key, value in updates.items():
        if key not in seen:
            output.append(f"{key}={value}")
    path.write_text("\n".join(output) + "\n", encoding="utf-8")


def _mask(value: str) -> str:
    return f"{value[:5]}••••{value[-4:]}" if len(value) > 9 else ""


@router.get("")
def get_settings_view(db: Session = Depends(get_db)):
    settings = get_settings()
    chat_key = settings.chat_api_key or ""
    embedding_key = settings.embedding_api_key or ""
    return {
        "model_mode": settings.model_mode,
        "base_url": settings.chat_base_url,
        "chat_model": settings.chat_model,
        "timeout_seconds": 45,
        "api_key_configured": bool(chat_key),
        "api_key_masked": _mask(chat_key),
        # ---- embeddings ----
        "embedding_provider": settings.embedding_provider,
        "embedding_mode": settings.embedding_mode,
        "embedding_base_url": settings.embedding_base_url,
        "embedding_model": settings.embedding_model,
        "embedding_dimensions": settings.embedding_dimensions,
        "embedding_key_configured": bool(embedding_key),
        "embedding_key_masked": _mask(embedding_key),
        "embedding_is_placeholder": settings.embedding_is_placeholder,
        "embedding_label": settings.embedding_label,
        "vectors": vector_stats(db),
        # ---- final-stage rerank ----
        "rerank_mode": settings.rerank_mode,
        "rerank_top_n": settings.rerank_top_n,
        # What will actually run right now -- "llm" silently degrades to "rule"
        # when no chat model is reachable, and the UI should show that.
        "rerank_effective": resolve_rerank_mode(settings, None),
    }


@router.put("")
def update_settings(payload: SettingsUpdateIn, db: Session = Depends(get_db)):
    current = read_env()
    updates: dict[str, str] = {
        "MODEL_MODE": payload.model_mode,
        "CHAT_BASE_URL": payload.base_url,
        "CHAT_MODEL": payload.chat_model,
    }

    # Keep the legacy OPENAI_* names in sync so older scripts and .env files
    # continue to resolve the same values.
    chat_key = current.get("CHAT_API_KEY", "") or current.get("OPENAI_API_KEY", "")
    if payload.api_key and "••••" not in payload.api_key:
        chat_key = payload.api_key
    updates["CHAT_API_KEY"] = chat_key
    updates["OPENAI_API_KEY"] = chat_key
    updates["OPENAI_BASE_URL"] = payload.base_url

    provider = (payload.embedding_provider or current.get("EMBEDDING_PROVIDER") or "hash").strip()
    if payload.embedding_provider is not None:
        updates["EMBEDDING_PROVIDER"] = provider
    if payload.embedding_mode is not None:
        updates["EMBEDDING_MODE"] = payload.embedding_mode

    # base_url / model / dimensions follow a simple contract: EMPTY means "use the
    # provider preset". That matters because a provider switch changes the preset
    # -- leaving a stale value behind would silently keep calling the old model
    # name, or keep the old dimension and zero-pad the new model's vectors.
    #
    # So when the form submits, these three are always rewritten, and any value
    # equal to the preset being saved is stored as empty.
    preset_base, preset_model, preset_dims = EMBEDDING_PRESETS.get(provider, EMBEDDING_PRESETS["hash"])
    provider_submitted = payload.embedding_provider is not None

    def collapse(value, preset_default: object) -> str:
        text = "" if value is None else str(value).strip()
        if not text or text == str(preset_default):
            return ""
        return text

    base_url = collapse(payload.embedding_base_url, preset_base)
    model = collapse(payload.embedding_model, preset_model)
    if provider_submitted or payload.embedding_base_url is not None:
        updates["EMBEDDING_BASE_URL"] = base_url
    if provider_submitted or payload.embedding_model is not None:
        updates["EMBEDDING_MODEL"] = model
    if payload.embedding_dimensions is not None:
        dimensions = payload.embedding_dimensions
        updates["EMBEDDING_DIMENSIONS"] = "0" if dimensions in (0, preset_dims) else str(dimensions)
    elif provider_submitted:
        # 留空 = 使用新服务商的预设维度；显式清零，避免残留旧维度
        updates["EMBEDDING_DIMENSIONS"] = "0"
    if payload.embedding_api_key and "••••" not in payload.embedding_api_key:
        updates["EMBEDDING_API_KEY"] = payload.embedding_api_key

    if payload.rerank_mode is not None:
        updates["RERANK_MODE"] = payload.rerank_mode
    if payload.rerank_top_n is not None:
        updates["RERANK_TOP_N"] = str(payload.rerank_top_n)

    write_env(updates)
    get_settings.cache_clear()
    # db is threaded through explicitly: calling this view without it used to
    # raise inside vector_stats(), so every save wrote .env and then 500'd.
    return get_settings_view(db)


@router.post("/test-connection")
def test_connection(db: Session = Depends(get_db)):
    settings = get_settings()
    report: dict[str, object] = {}

    if settings.model_mode == "mock":
        report["chat"] = {"ok": True, "message": "当前为 Mock 模式，无需远程连接"}
    else:
        try:
            ModelService(db).parse_job("测试一个销售经理岗位")
            report["chat"] = {"ok": True, "message": f"{settings.chat_provider} 连接成功"}
        except ModelServiceError as exc:
            report["chat"] = {"ok": False, "message": str(exc)}

    embedding = {
        "ok": True,
        "placeholder": settings.embedding_is_placeholder,
        "model": settings.embedding_model,
        "message": (
            "未配置独立向量服务，当前使用本地哈希占位向量（无语义）"
            if settings.embedding_is_placeholder
            else f"向量服务可用：{settings.embedding_provider} / {settings.embedding_model}"
        ),
    }
    if settings.embedding_uses_remote:
        try:
            ModelService(db).embed(["连接测试"])
            embedding["message"] = f"向量服务连接成功：{settings.embedding_model}"
        except ModelServiceError as exc:
            embedding["ok"] = False
            embedding["message"] = str(exc)
    report["embedding"] = embedding

    chat_ok = bool(report["chat"]["ok"])
    return {
        "ok": chat_ok and bool(embedding["ok"]),
        "message": f"{report['chat']['message']}；{embedding['message']}",
        "detail": report,
    }
