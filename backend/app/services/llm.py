import hashlib
import json
import math
import re
import time
from typing import Any, TypeVar, Type
from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..config import get_settings
from ..models import ModelCallAudit
from ..schemas import (
    CandidateExtract,
    ExperienceData,
    JobRequirements,
    MatchExplanation,
    QueryRewrite,
    RecallGrade,
    RerankResult,
)

T = TypeVar("T", bound=BaseModel)


class ModelServiceError(RuntimeError):
    pass


class ModelService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.client = None
        if self.settings.model_mode in {"openai", "deepseek"}:
            if not self.settings.chat_api_key:
                provider = "DeepSeek" if self.settings.model_mode == "deepseek" else "OpenAI"
                raise ModelServiceError(f"{provider} 模式未配置 API Key，请前往设置页填写并保存")
            self.client = OpenAI(api_key=self.settings.chat_api_key, base_url=self.settings.chat_base_url.rstrip("/"), timeout=45, max_retries=2)
        # Embeddings need their own credential.  A DeepSeek chat key is not an
        # embeddings credential -- reusing it (and swallowing the resulting
        # error) is exactly what silently downgraded every stored vector to a
        # hash placeholder before.
        self.embedding_client = None
        if self.settings.embedding_uses_remote:
            self.embedding_client = OpenAI(
                api_key=self.settings.embedding_api_key,
                base_url=self.settings.embedding_base_url.rstrip("/"),
                timeout=45,
                max_retries=2,
            )

    def _audit(self, operation: str, model: str, source: str, started: float, status: str, usage=None, error_code=None, provider: str | None = None):
        if self.db is None:
            # 并行调用场景（见 search.py 的解释线程池）：线程内不碰数据库，
            # 否则 SQLite 并发写会撞锁；审计由主线程聚合写一条。
            return
        self.db.add(ModelCallAudit(
            operation=operation,
            provider=provider or ("mock" if self.settings.model_mode == "mock" else "openai-compatible"),
            model=model,
            request_hash=hashlib.sha256(source.encode("utf-8")).hexdigest(),
            status=status,
            latency_ms=int((time.perf_counter() - started) * 1000),
            input_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
            output_tokens=getattr(usage, "completion_tokens", None) if usage else None,
            error_code=error_code,
        ))
        self.db.flush()

    def _structured(self, operation: str, instructions: str, text: str, schema: Type[T]) -> T:
        started = time.perf_counter()
        try:
            # DeepSeek implements the OpenAI-compatible chat endpoint but does
            # not consistently implement beta Pydantic parsing.  Request JSON
            # mode explicitly, then validate it locally against our schema.
            schema_hint = json.dumps(schema.model_json_schema(), ensure_ascii=False)
            response = self.client.chat.completions.create(
                model=self.settings.chat_model,
                messages=[
                    {"role": "system", "content": instructions + "\n必须只返回 JSON，不要 Markdown 代码块。JSON Schema：" + schema_hint},
                    {"role": "user", "content": text},
                ],
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or ""
            content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.I)
            parsed = schema.model_validate(json.loads(content))
            self._audit(operation, self.settings.chat_model, text, started, "success", response.usage)
            return parsed
        except json.JSONDecodeError as exc:
            self._audit(operation, self.settings.chat_model, text, started, "failed", error_code="INVALID_JSON")
            raise ModelServiceError("云端模型返回的不是有效 JSON，请重试") from exc
        except (ValueError, TypeError) as exc:
            self._audit(operation, self.settings.chat_model, text, started, "failed", error_code="SCHEMA_VALIDATION_FAILED")
            raise ModelServiceError(f"云端模型返回字段不完整：{exc}") from exc
        except Exception as exc:
            self._audit(operation, self.settings.chat_model, text, started, "failed", error_code=type(exc).__name__)
            raise ModelServiceError(f"云端模型调用失败：{exc}") from exc

    def extract_candidate(self, text: str) -> CandidateExtract:
        if self.settings.model_mode == "mock":
            started = time.perf_counter()
            result = mock_candidate(text)
            self._audit("resume_extract", "mock-rule-v1", text, started, "success")
            return result
        return self._structured(
            "resume_extract",
            "你是严谨的中文招聘数据分析师。只提取简历明确出现的信息，不推断敏感属性；未出现的字段留空。工作经历描述保留可验证业绩。",
            text,
            CandidateExtract,
        )

    def parse_job(self, text: str) -> JobRequirements:
        if self.settings.model_mode == "mock":
            started = time.perf_counter()
            result = mock_job(text)
            self._audit("job_parse", "mock-rule-v1", text, started, "success")
            return result
        return self._structured(
            "job_parse",
            "你是招聘需求分析师。将自然语言招聘需求拆成可编辑的客观筛选条件，并提取明确出现的公司、岗位和工作地点。禁止加入性别、年龄、民族等敏感条件；区分必要条件与优先条件；未出现的字段留空。",
            text,
            JobRequirements,
        )

    def explain(self, job: JobRequirements, candidate: CandidateExtract, evidence: list[str]) -> MatchExplanation:
        source = json.dumps({"job": job.model_dump(), "candidate": candidate.model_dump(), "evidence": evidence}, ensure_ascii=False)
        if self.settings.model_mode == "mock":
            started = time.perf_counter()
            result = evidence_explanation(job, candidate)
            self._audit("match_explain", "mock-rule-v1", source, started, "success")
            return result
        try:
            return self._structured(
                "match_explain",
                "你是谨慎的人才匹配分析师。优势和缺口必须来自输入事实，每项使用简短中文；证据不足就写入缺口，不得臆测。",
                source,
                MatchExplanation,
            )
        except Exception:
            # An explanation is an enhancement, never a dependency: a model
            # hiccup must not turn a finished ranking into a failed search.
            # Fall back to the deterministic rule-based summary instead.
            started = time.perf_counter()
            result = evidence_explanation(job, candidate)
            self._audit("match_explain", "rule-fallback", source, started, "fallback")
            return result

    def rerank(self, job: JobRequirements, candidates: list[dict]) -> dict[str, float]:
        """Score each candidate's fit against the job with one batched call.

        Returns ``{candidate_key: score 0-100}``.  On any failure the caller
        keeps its rule-based ordering, so a model outage degrades quality
        rather than breaking search.

        Batching matters: one call per *job* (not per candidate) keeps latency
        and cost flat as the candidate pool grows, which is also what makes the
        "llm vs rule" evaluation affordable.
        """
        if not candidates:
            return {}
        source = json.dumps({"job": job.model_dump(), "candidates": candidates}, ensure_ascii=False)
        try:
            result = self._structured(
                "match_rerank",
                "你是资深招聘顾问。请只依据给定事实，为每位候选人打 0-100 的匹配分："
                "岗位核心要求被满足的程度占主要权重，行业与技能相关度、年限、管理经验次之。"
                "不得臆造简历中没有的信息。必须为每一个 key 打分，不要遗漏。",
                source,
                RerankResult,
            )
        except Exception:
            return {}
        return {item.key: max(0.0, min(100.0, item.score)) for item in result.ranked}

    def grade_recall(self, job: JobRequirements, matches: list[Any]) -> dict:
        """Judge whether the recalled candidates actually cover the job's core asks.

        This is the decision node of the orchestration graph: its verdict decides
        whether to rewrite the query and retrieve again.  Failures degrade to
        "good" (single pass) rather than blocking the search -- a broken judge
        must not be able to loop the graph forever.
        """
        compact = []
        for m in matches[:10]:
            candidate = m.candidate
            compact.append({
                "name": candidate.name,
                "title": candidate.current_title,
                "years": candidate.years_experience,
                "industries": candidate.industries,
                "skills": candidate.skills,
                "score": m.total_score,
            })
        source = json.dumps({"job": job.model_dump(), "candidates": compact}, ensure_ascii=False)

        if self.settings.model_mode == "mock":
            return {"verdict": "good", "reasons": ["离线模式：默认单轮通过"], "missing": []}
        if not matches:
            return {"verdict": "weak", "reasons": ["没有召回任何候选人"], "missing": ["任何候选人"]}

        try:
            result = self._structured(
                "recall_grade",
                "你是检索质量评估员。判断召回的候选人是否覆盖了岗位的核心要求（行业、技能、年限、管理经验）。"
                "覆盖良好 verdict=good；明显跑偏或关键条件全部落空 verdict=weak。宁可 good 也不要吹毛求疵："
                "只有当大多数候选人都不相关时才判 weak。",
                source,
                RecallGrade,
            )
            return result.model_dump()
        except Exception:
            return {"verdict": "good", "reasons": ["评估失败，按单轮继续"], "missing": []}

    def rewrite_query(self, job: JobRequirements, grade: dict, raw_text: str) -> tuple[JobRequirements, str]:
        """Loosen / synonymise the query after a weak recall verdict.

        Deliberately one-way: only ever widens the net (adds synonyms, drops an
        over-tight filter).  Tightening a query on retry is how agents start
        hallucinating their way away from the user's actual ask.
        """
        source = json.dumps({"job": job.model_dump(), "grade": grade, "raw_text": raw_text}, ensure_ascii=False)
        if self.settings.model_mode == "mock":
            return job, raw_text
        try:
            result = self._structured(
                "query_rewrite",
                "你是检索查询改写器。召回质量不佳时，改写招聘查询以提高召回："
                "补充行业与技能的同义说法（如 半导体→芯片/晶圆、大客户→KA/战略客户），"
                "可放宽过于具体的条件。禁止删改岗位名称与公司名，禁止发明新的硬性要求。"
                "raw_text 返回改写后的完整招聘描述。",
                source,
                QueryRewrite,
            )
            updates: dict[str, Any] = {}
            if result.industries:
                updates["industries"] = sorted(set(job.industries) | set(result.industries))
            if result.skills:
                updates["skills"] = sorted(set(job.skills) | set(result.skills))
            if result.must_have:
                updates["must_have"] = sorted(set(job.must_have) | set(result.must_have))
            merged = job.model_copy(update=updates) if updates else job
            new_text = result.raw_text.strip()
            return merged, (new_text if len(new_text) >= 10 else raw_text)
        except Exception:
            return job, raw_text

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        started = time.perf_counter()
        source = "\n".join(texts)
        dimensions = self.settings.embedding_dimensions

        # 1) No usable embedding credential -> deterministic hash placeholder.
        #    Audited as "placeholder" (not "success") so the UI and the audit
        #    trail can tell the difference between real semantics and filler.
        if not self.embedding_client:
            vectors = [hash_embedding(t, dimensions) for t in texts]
            self._audit("embedding", "deterministic-hash-v1", source, started, "placeholder",
                        provider="local", error_code="EMBEDDING_PLACEHOLDER")
            return vectors

        try:
            kwargs: dict[str, Any] = {"model": self.settings.embedding_model, "input": texts}
            # Some providers size the model at training time and do not accept
            # this parameter (SiliconFlow's bge-m3 is fixed at 1024); others do.
            # Zhipu's embedding-3 *defaults to 2048* -- without passing
            # dimensions we get 2048 back and silently throw half the signal
            # away in fit_vector.  Ask for the configured size explicitly.
            if self.settings.embedding_provider in DIMENSION_PARAM_PROVIDERS and dimensions:
                kwargs["dimensions"] = dimensions
            response = self.embedding_client.embeddings.create(**kwargs)
            vectors = [fit_vector(row.embedding, dimensions) for row in response.data]
            self._audit("embedding", self.settings.embedding_model, source, started, "success",
                        response.usage, provider=f"{self.settings.embedding_provider}:openai-compatible")
            return vectors
        except Exception as exc:
            # embedding_mode="hash" means the caller explicitly accepts a
            # placeholder fallback (offline demo).  Any other mode fails loudly:
            # silently degrading here is how semantic search quietly becomes
            # meaningless.
            if self.settings.embedding_mode == "hash":
                vectors = [hash_embedding(t, dimensions) for t in texts]
                self._audit("embedding", "deterministic-hash-v1", source, started, "placeholder",
                            provider="local", error_code=type(exc).__name__)
                return vectors
            self._audit("embedding", self.settings.embedding_model, source, started, "failed",
                        provider=f"{self.settings.embedding_provider}:openai-compatible",
                        error_code=type(exc).__name__)
            raise ModelServiceError(f"向量生成失败（{self.settings.embedding_provider}）：{exc}") from exc


_dimension_warned: set[tuple[int, int]] = set()

# Providers whose embeddings endpoint accepts the OpenAI-style `dimensions`
# parameter.  Providers with a fixed-size model (SiliconFlow's bge-m3) would
# reject it, so they must not be listed here.
DIMENSION_PARAM_PROVIDERS = frozenset({"zhipu", "openai", "dashscope"})


def fit_vector(vector: list[float], size: int) -> list[float]:
    """Pad or truncate a vector to the configured dimension.

    Zero padding leaves cosine similarity unchanged, so a mismatch is not fatal
    -- but it almost always means EMBEDDING_DIMENSIONS disagrees with the model
    actually being called.  Warn once instead of silently wasting space.
    """
    if len(vector) != size and (len(vector), size) not in _dimension_warned:
        _dimension_warned.add((len(vector), size))
        action = "截断" if len(vector) > size else "补零"
        print(
            f"[embed] 警告：模型返回 {len(vector)} 维，配置为 {size} 维，已自动{action}。"
            "建议把 EMBEDDING_DIMENSIONS 设为 0（使用模型原生维度）并重建向量。"
        )
    if len(vector) >= size:
        return vector[:size]
    return vector + [0.0] * (size - len(vector))


def hash_embedding(text: str, size: int) -> list[float]:
    vector = [0.0] * size
    tokens = re.findall(r"[\u4e00-\u9fff]{1,3}|[a-zA-Z0-9+#.]+", text.lower())
    for token in tokens:
        digest = hashlib.sha256(token.encode()).digest()
        index = int.from_bytes(digest[:4], "big") % size
        vector[index] += -1.0 if digest[4] & 1 else 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def mock_candidate(text: str) -> CandidateExtract:
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("[第")]
    first = re.sub(r"简历|个人简历|求职", "", lines[0] if lines else "").strip(" ：:")
    name = first if 1 < len(first) <= 12 else "未识别候选人"
    email = (re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text) or [None])[0]
    phone = (re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", text) or [None])[0]
    locations = [x for x in ["上海", "北京", "深圳", "苏州", "杭州", "南京", "广州", "无锡"] if x in text]
    # Industry tags require an employment/experience context. A customer,
    # project, or partner mention alone must not classify the candidate.
    industries = []
    for industry in ["半导体", "芯片", "集成电路", "新能源", "医疗", "互联网", "制造业"]:
        contexts = [line for line in lines if industry in line]
        if any((re.search(r"行业经验|从业经验|销售经验|工作经验", line) is not None) or (re.search(r"行业|从业|主营|制造|设备|材料|公司|企业|领域", line) and not re.search(r"客户|项目|合作|供应商|服务对象|投资|IPO|收购|融资|资本市场|并购|交易", line)) for line in contexts):
            industries.append(industry)
    skills = [x for x in ["销售管理", "团队管理", "渠道管理", "大客户", "晶圆厂", "封装测试", "CRM", "英语", "项目管理"] if x.lower() in text.lower()]
    years = [int(x) for x in re.findall(r"(?<!\d)(\d{1,2})\s*年(?!\d)", text)]
    titles = [x for x in ["销售总监", "销售经理", "区域经理", "大客户经理", "销售工程师", "CFO", "财务总监"] if x in text]
    highlights = [line[:160] for line in lines if re.search(r"增长|业绩|销售额|客户|团队|百万|千万|亿", line)][:5]
    return CandidateExtract(
        name=name, email=email, phone=phone, location=locations[0] if locations else None,
        current_title=titles[0] if titles else None, years_experience=max(years, default=0),
        industries=industries, skills=skills, highlights=highlights,
        management_experience=bool(re.search(r"团队|管理\d+人|负责人|总监", text)),
        experiences=[ExperienceData(company="简历原文记录", title=titles[0] if titles else "", industry=industries[0] if industries else None, description="；".join(highlights))] if highlights else [],
    )


def mock_job(text: str) -> JobRequirements:
    company_match = re.search(r"(?:替|给|为|在|的)([一-鿿A-Za-z0-9·]{2,30}?)(?:找|招聘|需要|招一个|招募)", text)
    company = company_match.group(1).strip() if company_match else ""
    if not company:
        company_match = re.search(r"([\u4e00-\u9fffA-Za-z0-9·]{2,30}?)(?:需要|招聘|招一个)", text)
        company = company_match.group(1).strip() if company_match else ""
    company = re.sub(r"^(?:上海|北京|深圳|广州|杭州|苏州|南京|成都|武汉|西安)的", "", company)
    titles = [x for x in ["销售总监", "销售经理", "区域经理", "产品经理", "研发工程师"] if x in text]
    industries = [x for x in ["半导体", "芯片", "集成电路", "新能源", "医疗", "互联网"] if x in text]
    locations = [x for x in ["上海", "北京", "深圳", "苏州", "杭州", "南京", "华东", "华南"] if x in text]
    years = [int(x) for x in re.findall(r"(?<!\d)(\d{1,2})\s*年(?!\d)", text)]
    skills = [x for x in ["销售管理", "团队管理", "渠道管理", "大客户", "晶圆厂", "封装测试", "CRM", "英语"] if x.lower() in text.lower()]
    must = ([f"{min(years)}年以上经验"] if years else []) + ([f"具备{industries[0]}行业经验"] if industries else [])
    return JobRequirements(
        company=company, title=titles[0] if titles else "未命名岗位", industries=industries, locations=locations,
        minimum_years=min(years) if years else 0, skills=skills,
        management_required=bool(re.search(r"管理|带过团队|负责人|总监", text)),
        must_have=must, preferred=[x for x in skills if x in ["大客户", "晶圆厂", "英语"]],
        performance_expectations=[line.strip() for line in text.splitlines() if re.search(r"业绩|销售额|增长", line)][:3],
    )


def evidence_explanation(job: JobRequirements, candidate: CandidateExtract) -> MatchExplanation:
    strengths, gaps = [], []
    industry_hit = set(job.industries) & set(candidate.industries)
    skill_hit = set(job.skills) & set(candidate.skills)
    if industry_hit: strengths.append(f"具备{'、'.join(sorted(industry_hit))}行业经历")
    elif job.industries: gaps.append(f"未发现{'、'.join(job.industries)}行业证据")
    if candidate.years_experience >= job.minimum_years: strengths.append(f"约 {candidate.years_experience:g} 年经验满足年限要求")
    elif job.minimum_years: gaps.append(f"经验年限低于 {job.minimum_years:g} 年要求")
    if skill_hit: strengths.append(f"命中{'、'.join(sorted(skill_hit))}能力要求")
    missing = set(job.skills) - set(candidate.skills)
    if missing: gaps.append(f"简历未明确体现{'、'.join(sorted(missing))}")
    if job.management_required and candidate.management_experience: strengths.append("简历包含团队或管理经历")
    elif job.management_required: gaps.append("未发现明确的团队管理证据")
    return MatchExplanation(strengths=strengths or ["存在与岗位相关的语义证据"], gaps=gaps)
