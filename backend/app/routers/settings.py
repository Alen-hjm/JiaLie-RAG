from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import EMBEDDING_PRESETS, PROJECT_ENV_FILE, Settings, get_settings
from dotenv import dotenv_values, set_key
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock
from ..db import get_db
from ..dependencies import current_user
from ..schemas import SettingsUpdateIn
from ..services.llm import ModelService
from ..services.search import resolve_rerank_mode
from ..services.vectors import vector_stats

router = APIRouter(prefix="/api/settings", tags=["settings"], dependencies=[Depends(current_user)])
_write_lock = Lock()


def env_path():
    """The project root .env is the single source of truth.

    Previously this returned ``backend/.env`` whenever that file existed, so
    saving from the UI wrote to a different file than the one the app actually
    loaded first -- the two then disagreed about model mode and database URL.
    """
    return PROJECT_ENV_FILE


def read_env() -> dict[str, str]:
    return {key: value or "" for key, value in dotenv_values(env_path()).items()}


def write_env(updates: dict[str, str]) -> None:
    # Quote values and replace atomically; never interpolate user input into .env lines.
    with _write_lock:
        path = env_path()
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as temp:
            temp.write(path.read_text(encoding="utf-8") if path.exists() else "")
            temporary = Path(temp.name)
        try:
            for key, value in updates.items():
                set_key(str(temporary), key, value, quote_mode="always")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    return


def _mask(value: str) -> str:
    return f"{value[:5]}••••{value[-4:]}" if len(value) > 9 else ""


@router.get("")
def get_settings_view(db: Session = Depends(get_db)):
    settings = get_settings()
    chat_key = settings.chat_api_key or ""
    embedding_key = settings.embedding_api_key or ""
    stats = vector_stats(db)
    signature_file = PROJECT_ENV_FILE.parent / "backend" / ".embedding-signature"
    signature = f"{settings.embedding_provider}:{settings.embedding_model}:{settings.embedding_dimensions}"
    previous = signature_file.read_text(encoding="utf-8").strip() if signature_file.exists() else None
    stats["needs_reindex"] = stats["needs_reindex"] or bool(stats["total_chunks"] and previous != signature)
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
        "vectors": stats,
        # ---- final-stage rerank ----
        "rerank_mode": settings.rerank_mode,
        "rerank_top_n": settings.rerank_top_n,
        # What will actually run right now -- "llm" silently degrades to "rule"
        # when no chat model is reachable, and the UI should show that.
        "rerank_effective": resolve_rerank_mode(settings, None),
    }


@router.put("")
def update_settings(payload: SettingsUpdateIn, db: Session = Depends(get_db)):
    before = get_settings()
    draft = draft_settings(payload)
    current = read_env()
    updates: dict[str, str] = {
        "MODEL_MODE": payload.model_mode,
        "CHAT_BASE_URL": payload.base_url,
        "CHAT_MODEL": payload.chat_model,
        "CHAT_PROVIDER": {"mock": "mock", "deepseek": "deepseek", "openai": "openai-compatible"}[payload.model_mode],
    }

    # Keep the legacy OPENAI_* names in sync so older scripts and .env files
    # continue to resolve the same values.
    chat_key = get_settings().chat_api_key
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
    identity = lambda settings: (settings.embedding_provider, settings.embedding_base_url, settings.embedding_model, settings.embedding_dimensions, settings.embedding_is_placeholder)
    if identity(before) != identity(draft):
        (PROJECT_ENV_FILE.parent / "backend" / ".embedding-signature").write_text("pending-reindex", encoding="utf-8")
    get_settings.cache_clear()
    # db is threaded through explicitly: calling this view without it used to
    # raise inside vector_stats(), so every save wrote .env and then 500'd.
    return get_settings_view(db)


def draft_settings(payload: SettingsUpdateIn) -> Settings:
    current = get_settings()
    values = current.model_dump()
    values.update(model_mode=payload.model_mode, chat_provider="", chat_base_url=payload.base_url,
                  chat_model=payload.chat_model, chat_api_key=payload.api_key or current.chat_api_key)
    provider = payload.embedding_provider or current.embedding_provider
    if payload.embedding_provider is not None:
        base, model, dimensions = EMBEDDING_PRESETS[provider]
        values.update(embedding_provider=provider, embedding_base_url=payload.embedding_base_url or base,
                      embedding_model=payload.embedding_model or model,
                      embedding_dimensions=payload.embedding_dimensions or dimensions)
    else:
        for key in ("embedding_base_url", "embedding_model", "embedding_dimensions"):
            value = getattr(payload, key)
            if value is not None:
                values[key] = value
    values["embedding_mode"] = payload.embedding_mode or current.embedding_mode
    values["embedding_api_key"] = payload.embedding_api_key or current.embedding_api_key
    result = Settings.model_validate(values)
    if result.model_mode != "mock" and not (result.chat_api_key and result.chat_base_url and result.chat_model):
        raise HTTPException(422, detail={"message": "请填写对话服务地址、模型名称和密钥"})
    if provider != "hash" and result.embedding_mode != "hash" and not (result.embedding_api_key and result.embedding_base_url and result.embedding_model):
        raise HTTPException(422, detail={"message": "请填写检索服务地址、模型和密钥"})
    return result


def connection_report(settings: Settings) -> dict:
    # Use only synthetic text; never send a stored resume during a connection check.
    chat = {"ok": False, "message": "演示模式，未连接远程对话服务"}
    embedding = {"ok": False, "placeholder": settings.embedding_is_placeholder,
                 "message": "演示检索，未连接语义检索服务"}
    if settings.model_mode != "mock":
        try:
            service = ModelService(None, settings=settings)
            service.client = service.client.with_options(timeout=20, max_retries=0)
            service.parse_job("连接测试：寻找一位销售经理，工作地点上海")
            chat = {"ok": True, "message": "对话服务已连接，结构化输出可用"}
        except Exception:
            chat = {"ok": False, "message": "对话测试失败，请核对地址、模型、密钥及服务额度"}
    if settings.embedding_uses_remote:
        try:
            # Test embedding independently, even if the chat configuration is unavailable.
            service = ModelService(None, settings=settings.model_copy(update={"model_mode": "mock"}))
            client = service.embedding_client.with_options(timeout=20, max_retries=0)
            kwargs = {"model": settings.embedding_model, "input": ["连接测试"]}
            if settings.embedding_provider in {"openai", "dashscope", "zhipu"}:
                kwargs["dimensions"] = settings.embedding_dimensions
            response = client.embeddings.create(**kwargs)
            valid = len(response.data) == 1 and len(response.data[0].embedding) == settings.embedding_dimensions
            embedding = {"ok": valid, "placeholder": False, "message": "检索服务已连接" if valid else "模型返回维度与配置不一致，请核对检索模型配置"}
        except Exception:
            embedding = {"ok": False, "placeholder": False, "message": "检索测试失败，请核对地址、模型、密钥和向量维度"}
    return {"ok": chat["ok"] and embedding["ok"], "message": "连接检查完成", "detail": {"chat": chat, "embedding": embedding}}


@router.post("/test-connection")
def test_connection(payload: SettingsUpdateIn | None = None):
    return connection_report(draft_settings(payload) if payload is not None else get_settings())
