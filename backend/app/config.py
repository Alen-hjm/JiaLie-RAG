from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Always resolve the project-level .env explicitly.  Uvicorn is commonly
# started from either the repository root or backend/, and pydantic's relative
# env_file resolution would otherwise make settings appear to reset when the
# page is revisited.
PROJECT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
BACKEND_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


# OpenAI-compatible embedding providers we ship presets for.
# provider -> (base_url, default model, native dimensions)
#
# Why this table exists: chat and embeddings are served by *different*
# providers in practice (DeepSeek has no public embeddings endpoint), so
# embedding must be configured independently.  Filling EMBEDDING_PROVIDER with
# one of these keys is enough -- base_url / model / dimensions fall back to the
# preset, and only EMBEDDING_API_KEY has to be supplied.
EMBEDDING_PRESETS: dict[str, tuple[str, str, int]] = {
    "hash": ("", "deterministic-hash-v1", 1536),
    "siliconflow": ("https://api.siliconflow.cn/v1", "BAAI/bge-m3", 1024),
    "zhipu": ("https://open.bigmodel.cn/api/paas/v4", "embedding-3", 1024),
    "dashscope": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "text-embedding-v3", 1024),
    "openai": ("https://api.openai.com/v1", "text-embedding-3-small", 1536),
}

EMBEDDING_MODES = ("auto", "real", "hash")

# Final-stage relevance judging.
#   "rule" -> keyword coverage over the evidence (free, offline, deterministic)
#   "llm"  -> one batched chat call scores the top-N candidates (needs a key)
# The evaluation script can select either, so the two are directly comparable.
RERANK_MODES = ("rule", "llm")

# How the search flow is wired.
#   "pipeline"  -> fixed orchestration: recall -> score -> explain (default)
#   "langgraph" -> LangGraph StateGraph that adds a recall-quality judge and a
#                  bounded rewrite-and-retrieve loop (services/orchestration.py)
ORCHESTRATION_MODES = ("pipeline", "langgraph")


class Settings(BaseSettings):
    app_name: str = "明猎智能问答系统"
    app_env: str = "development"
    secret_key: str = "development-only-change-me"
    admin_username: str = "admin"
    admin_password: str = "minglie123"
    database_url: str = "sqlite:///./minglie.db"
    upload_dir: Path = Path("./uploads")

    # ---------- chat / structured extraction ----------
    model_mode: str = "mock"  # mock / openai / deepseek
    chat_provider: str = ""  # empty -> derived from model_mode
    chat_api_key: str = ""  # empty -> falls back to openai_api_key
    chat_base_url: str = ""  # empty -> falls back to openai_base_url
    chat_model: str = "deepseek-chat"

    # ---------- embeddings (independent of chat, never reuses the chat key) ----------
    embedding_provider: str = "hash"  # hash / siliconflow / zhipu / dashscope / openai
    embedding_mode: str = "auto"  # auto: real when a key exists, else placeholder
    embedding_api_key: str = ""
    embedding_base_url: str = ""  # empty -> provider preset
    embedding_model: str = ""  # empty -> provider preset
    embedding_dimensions: int = 0  # 0 -> provider preset

    # ---------- final-stage rerank ----------
    rerank_mode: str = "rule"  # rule / llm
    rerank_top_n: int = 20  # how many candidates the llm judge sees

    # ---------- orchestration ----------
    orchestration_mode: str = "pipeline"  # pipeline / langgraph
    # 只给排在前 N 位的候选人生成大模型解释，其余用规则即时生成。
    # 解释是最贵的环节（每人一次调用，串行 20 人要 40 秒以上），
    # 而用户实际细看的只有前几名——这是花在刀刃上的取舍。
    explain_top_n: int = 8

    # ---------- legacy aliases (kept so existing .env files keep working) ----------
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    max_upload_mb: int = 20
    web_origin: str = "http://localhost:5173"

    # The backend-local file stays as a supported override for existing local
    # installs, while the project root remains the canonical settings file.
    # NOTE: with a tuple, later entries win -- so the project root .env is the
    # source of truth and backend/.env only fills gaps it does not define.
    model_config = SettingsConfigDict(
        env_file=(str(BACKEND_ENV_FILE), str(PROJECT_ENV_FILE)), extra="ignore"
    )

    @model_validator(mode="after")
    def _resolve_defaults(self) -> "Settings":
        # chat: legacy variable names keep working as fallbacks
        if not self.chat_api_key:
            self.chat_api_key = self.openai_api_key
        if not self.chat_base_url:
            self.chat_base_url = self.openai_base_url or "https://api.deepseek.com"
        if not self.chat_provider:
            self.chat_provider = {"deepseek": "deepseek", "openai": "openai"}.get(self.model_mode, "mock")

        # embeddings: fill base_url / model / dimensions from the preset
        if self.embedding_provider not in EMBEDDING_PRESETS:
            self.embedding_provider = "hash"
        base_url, model, dimensions = EMBEDDING_PRESETS[self.embedding_provider]
        if not self.embedding_base_url:
            self.embedding_base_url = base_url
        if not self.embedding_model:
            self.embedding_model = model
        if not self.embedding_dimensions:
            self.embedding_dimensions = dimensions

        if self.embedding_mode not in EMBEDDING_MODES:
            self.embedding_mode = "auto"

        # rerank: "llm" only makes sense when a chat model is actually reachable.
        if self.rerank_mode not in RERANK_MODES:
            self.rerank_mode = "rule"
        if self.rerank_mode == "llm" and (self.model_mode == "mock" or not self.chat_api_key):
            self.rerank_mode = "rule"
        if self.rerank_top_n < 1:
            self.rerank_top_n = 20
        if self.orchestration_mode not in ORCHESTRATION_MODES:
            self.orchestration_mode = "pipeline"
        if self.explain_top_n < 0:
            self.explain_top_n = 0
        return self

    # ---------- derived runtime switches ----------

    @property
    def embedding_uses_remote(self) -> bool:
        """True when a remote embedding call can actually be made.

        Deliberately checks the *embedding* key only: a DeepSeek chat key is not
        an embedding credential, and reusing it is what silently degraded every
        vector to a hash placeholder before.
        """
        if self.embedding_provider == "hash" or self.embedding_mode == "hash":
            return False
        return bool(self.embedding_api_key and self.embedding_base_url)

    @property
    def embedding_is_placeholder(self) -> bool:
        """True when vectors are deterministic hash placeholders, not semantics."""
        return not self.embedding_uses_remote

    @property
    def embedding_label(self) -> str:
        if self.embedding_is_placeholder:
            return "占位向量（哈希，无语义）"
        return f"{self.embedding_provider}:{self.embedding_model}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
