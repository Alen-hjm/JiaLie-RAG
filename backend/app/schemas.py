from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class LoginIn(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    username: str


class ExperienceData(BaseModel):
    company: str = ""
    title: str = ""
    industry: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str = ""


class CandidateExtract(BaseModel):
    name: str = "未识别候选人"
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    current_title: str | None = None
    years_experience: float = 0
    industries: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    management_experience: bool = False
    experiences: list[ExperienceData] = Field(default_factory=list)


class JobRequirements(BaseModel):
    company: str = ""
    title: str = "未命名岗位"
    industries: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    minimum_years: float = 0
    skills: list[str] = Field(default_factory=list)
    management_required: bool = False
    must_have: list[str] = Field(default_factory=list)
    preferred: list[str] = Field(default_factory=list)
    performance_expectations: list[str] = Field(default_factory=list)


class JobParseIn(BaseModel):
    text: str = Field(min_length=10, max_length=30000)


class JobUpdateIn(BaseModel):
    requirements: JobRequirements


class MatchExplanation(BaseModel):
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class RerankItem(BaseModel):
    """One candidate judged by the LLM reranker.

    ``key`` is the opaque id handed to the model so its answer can be mapped
    back without leaking candidate names into the prompt key space.
    """

    key: str
    score: float = Field(ge=0, le=100)
    reason: str = ""


class RerankResult(BaseModel):
    ranked: list[RerankItem] = Field(default_factory=list)


class RecallGrade(BaseModel):
    """召回质量评估：决定要不要改写查询再查一次。"""

    verdict: str = Field(default="good", pattern="^(good|weak)$")
    reasons: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


class QueryRewrite(BaseModel):
    """改写后的查询：只允许放宽 / 补充同义说法，不允许收紧岗位核心条件。"""

    raw_text: str = ""
    industries: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    must_have: list[str] = Field(default_factory=list)


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ImportTaskOut(OrmModel):
    id: str
    document_id: str
    status: str
    progress: int
    message: str
    attempts: int


class CandidateSummary(OrmModel):
    id: str
    name: str
    location: str | None
    current_title: str | None
    years_experience: float
    industries: list[str]
    skills: list[str]
    management_experience: bool


class SearchOptions(BaseModel):
    limit: int = Field(default=20, ge=1, le=50)


class ConversationMessageIn(BaseModel):
    content: str = Field(min_length=2, max_length=30000)


class ConversationCreateIn(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class JobCreateIn(BaseModel):
    company: str = Field(default="", max_length=255)
    title: str = Field(min_length=1, max_length=255)
    raw_text: str = Field(default="", max_length=30000)
    requirements: JobRequirements = Field(default_factory=JobRequirements)


class SettingsUpdateIn(BaseModel):
    model_mode: str = Field(default="mock", pattern="^(mock|deepseek|openai)$")
    api_key: str | None = None
    base_url: str = Field(default="https://api.deepseek.com", max_length=500)
    chat_model: str = Field(default="deepseek-chat", max_length=128)
    timeout_seconds: int = Field(default=45, ge=5, le=180)
    rerank_mode: str | None = Field(default=None, pattern="^(rule|llm)$")
    rerank_top_n: int | None = Field(default=None, ge=1, le=50)
    # Embeddings are configured independently of the chat model, because the chat
    # provider (DeepSeek) does not expose an embeddings endpoint at all.
    embedding_provider: str | None = Field(default=None, max_length=64)
    embedding_mode: str | None = Field(default=None, pattern="^(auto|real|hash)$")
    embedding_api_key: str | None = None
    embedding_base_url: str | None = Field(default=None, max_length=500)
    embedding_model: str | None = Field(default=None, max_length=128)
    embedding_dimensions: int | None = Field(default=None, ge=0, le=4096)


class ApiError(BaseModel):
    code: str
    message: str
    request_id: str | None = None
