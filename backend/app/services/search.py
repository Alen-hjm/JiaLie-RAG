from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import time

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..config import RERANK_MODES, get_settings
from ..models import CandidateProfile, JobRequirement, MatchResult, ResumeChunk
from ..schemas import CandidateExtract, JobRequirements, MatchExplanation
from .llm import ModelService, evidence_explanation
from .privacy import mask_pii
from .synonyms import expand_terms
from .vectors import cosine

__all__ = ["cosine", "overlap", "structured_score", "keyword_rerank", "search_job", "empty_result_hint", "RECALL_LIMIT"]

# How many chunks each recall lane contributes before fusion.
RECALL_LIMIT = 100

# Constant from the Reciprocal Rank Fusion paper.  Dampens the weight of very
# high ranks so that neither lane can dominate purely by having a long tail.
RRF_K = 60

# How many evidence quotes a candidate card carries.
EVIDENCE_LIMIT = 3


def _clip(text: str, limit: int, mask: bool) -> str:
    """截断 + 可选脱敏。任何对外的简历引用都必须走这里。"""
    clipped = text[:limit]
    return mask_pii(clipped) if mask else clipped


def _mask(text: str, mask: bool) -> str:
    """整段文本的可选脱敏（用于送模型的上下文，不截断）。"""
    return mask_pii(text) if mask else text

# Fusion strategies:
#   "hybrid"      -> RRF over [vector lane, keyword lane] (default)
#   "vector_only" -> the previous behaviour: rank every chunk by cosine only
# Kept selectable so the evaluation script can produce a like-for-like baseline.
FUSION_MODES = ("hybrid", "vector_only")


def overlap(query: list[str], values: list[str]) -> float:
    if not query:
        return 1.0
    q = {x.lower() for x in query}
    v = {x.lower() for x in values}
    return len(q & v) / len(q)


def structured_score(job: JobRequirements, candidate: CandidateProfile) -> float:
    dimensions = []
    if job.industries: dimensions.append(overlap(job.industries, candidate.industries))
    if job.locations: dimensions.append(1.0 if candidate.location and any(x in candidate.location or candidate.location in x for x in job.locations) else 0.0)
    if job.minimum_years: dimensions.append(min(candidate.years_experience / job.minimum_years, 1.0))
    if job.skills: dimensions.append(overlap(job.skills, candidate.skills))
    if job.management_required: dimensions.append(1.0 if candidate.management_experience else 0.0)
    return sum(dimensions) / len(dimensions) if dimensions else 0.5


def keyword_rerank(job: JobRequirements, candidate: CandidateProfile, evidence: str) -> float:
    terms = job.industries + job.skills + job.must_have + [job.title]
    if not terms:
        return 0.5
    haystack = " ".join([candidate.current_title or "", *candidate.industries, *candidate.skills, evidence]).lower()
    hits = sum(1 for term in terms if term.lower() in haystack)
    return hits / len(terms)


# ---------------------------------------------------------------------------
# 召回层：两路召回 + RRF 融合
# ---------------------------------------------------------------------------

def _query_terms(job: JobRequirements, expand: bool = True) -> list[str]:
    """Keywords used by the lexical lane (exact matches an embedding can miss).

    ``expand`` 打开时会把 JD 原词按别名词典双向扩展（services/synonyms.py）。
    扩展发生在截断**之后**：先保证 JD 里说过的词都在，再拿别名去补召回，
    免得词表把原词挤出 24 个名额。

    注意扩展只影响"能不能被捞出来"，不参与打分——``keyword_rerank`` 与
    ``structured_score`` 仍按 JD 原词计算，所以词表里的噪声最多让候选人进入
    候选池，不会把他排到不该有的位置。
    """
    seen: set[str] = set()
    terms: list[str] = []
    candidates = [job.title, *job.industries, *job.locations, *job.skills, *job.must_have, *job.preferred]
    for raw in candidates:
        term = (raw or "").strip()
        # 单字词噪声太大（“的”“年”），至少两字才作为检索词
        if len(term) < 2 or term in seen:
            continue
        seen.add(term)
        terms.append(term)
    base = terms[:24]
    return expand_terms(base) if expand else base


def _vector_lane(db: Session, query_vector: list[float], limit: int) -> list[str]:
    """Vector recall.

    PostgreSQL: push the distance computation down to pgvector so the HNSW index
    in migration 0002 can be used (``<=>`` / cosine distance, ORDER BY + LIMIT).

    SQLite: pgvector does not exist, so the vectors are stored as text.  Score
    them in Python instead -- acceptable for the local demo corpus, and the
    limiter is that this is O(n) per query.
    """
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        stmt = (
            select(ResumeChunk.id)
            .where(ResumeChunk.embedding.is_not(None))
            .order_by(ResumeChunk.embedding.cosine_distance(query_vector))
            .limit(limit)
        )
        return list(db.scalars(stmt).all())

    rows = db.execute(select(ResumeChunk.id, ResumeChunk.embedding)).all()
    scored = []
    for chunk_id, vector in rows:
        if vector is None:
            continue
        score = cosine(query_vector, list(vector))
        if score > 0:
            scored.append((chunk_id, score))
    scored.sort(key=lambda item: item[1], reverse=True)
    return [chunk_id for chunk_id, _ in scored[:limit]]


def _keyword_lane(db: Session, terms: list[str], limit: int) -> list[str]:
    if not terms:
        return []
    conditions = [ResumeChunk.content.ilike(f"%{term}%") for term in terms]
    stmt = select(ResumeChunk.id).where(or_(*conditions)).limit(limit)
    return list(db.scalars(stmt).all())


def _rrf_fuse(lanes: list[list[str]], k: int = RRF_K) -> list[str]:
    scores: dict[str, float] = defaultdict(float)
    for lane in lanes:
        for rank, key in enumerate(lane, 1):
            scores[key] += 1.0 / (k + rank)
    return [key for key, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)]


def _recall(db: Session, query_vector: list[float], terms: list[str], fusion: str) -> list[str]:
    vector_ids = _vector_lane(db, query_vector, RECALL_LIMIT)
    if fusion == "vector_only":
        return vector_ids
    keyword_ids = _keyword_lane(db, terms, RECALL_LIMIT)
    fused = _rrf_fuse([vector_ids, keyword_ids])
    if not fused:
        # Nothing matched either lane (tiny corpus with no lexical overlap):
        # fall back to everything so the caller still gets a usable ranking.
        fused = list(db.scalars(select(ResumeChunk.id)))
    return fused


# ---------------------------------------------------------------------------
# 排序层：对外分数契约保持不变（0.35 结构化 / 0.45 语义 / 0.20 证据覆盖）
# ---------------------------------------------------------------------------

def _pad_evidence(db: Session, candidate_id: str, already: set[str], quote_chars: int = 360, mask: bool = True) -> list[dict]:
    """Top up a shortlisted candidate's evidence with their remaining chunks.

    Recall only returns the chunks that matched, so a strong candidate can end
    up with a single quote even though their resume was split into several
    sections.  Matched chunks stay first (they are the reason the candidate was
    retrieved); the rest just fill the card out so a reviewer sees the whole
    picture without leaving the page.
    """
    room = EVIDENCE_LIMIT - len(already)
    if room <= 0:
        return []
    rows = db.execute(
        select(ResumeChunk)
        .where(ResumeChunk.candidate_id == candidate_id, ResumeChunk.id.not_in(already))
        .order_by(ResumeChunk.chunk_index)
        .limit(room)
    ).scalars()
    return [
        {"chunk_id": chunk.id, "section": chunk.section, "page_number": chunk.page_number, "quote": _clip(chunk.content, quote_chars, mask)}
        for chunk in rows
    ]


def _explain_offline(requirements: JobRequirements, data: CandidateExtract, chunks: list[str]) -> MatchExplanation:
    """线程池里跑的大模型解释。

    刻意传入 ``db=None``：线程内**不做任何数据库读写**（SQLite 并发写会撞锁，
    SQLAlchemy Session 也不是线程安全的），审计由主线程聚合补一条。
    """
    return ModelService(None).explain(requirements, data, chunks)


def _candidate_payload(candidate: CandidateProfile, data: CandidateExtract, evidence_text: str) -> dict:
    """Compact view handed to the LLM judge -- deliberately no free-text resume."""
    return {
        "key": candidate.id,
        "current_title": candidate.current_title or "",
        "years_experience": candidate.years_experience,
        "location": candidate.location or "",
        "industries": candidate.industries,
        "skills": candidate.skills,
        "management": bool(candidate.management_experience),
        "summary": (getattr(data, "summary", "") or "")[:200],
        "evidence": evidence_text[:600],
    }


def resolve_rerank_mode(settings, requested: str | None) -> str:
    """Decide which judge actually runs, and report that honestly.

    An unsupported value or an unreachable chat model downgrades to ``rule``
    rather than failing the search -- and the caller stores the *effective*
    mode, so a score is never attributed to a judge that did not produce it.
    """
    mode = (requested or settings.rerank_mode or "rule").strip()
    if mode not in RERANK_MODES:
        return "rule"
    if mode == "llm" and (settings.model_mode == "mock" or not settings.chat_api_key):
        return "rule"
    return mode


def empty_result_hint(db: Session, requirements: JobRequirements) -> str:
    """检索无结果时给一句「为什么 + 怎么办」，而不是留一片空白。

    空结果是产品里最容易被忽略的状态：用户看到空列表，第一反应是"系统不行"，
    但实际上多半是某一条硬性条件把候选人全筛掉了——只要知道是哪一条，放宽它就行。

    刻意只做诊断、不改检索行为：返回空结果是诚实的，这里补充的是**解释**，
    而不是把不合适的人塞进结果里凑数。
    """
    total = db.scalar(select(func.count()).select_from(CandidateProfile)) or 0
    if total == 0:
        return "简历库中还没有候选人，请先上传简历（支持 PDF / DOCX）后再检索。"

    blockers: list[str] = []

    if requirements.locations:
        hit = db.scalar(
            select(func.count()).select_from(CandidateProfile).where(
                or_(*[CandidateProfile.location.ilike(f"%{loc}%") for loc in requirements.locations])
            )
        ) or 0
        if hit == 0:
            blockers.append(f"没有候选人的所在地符合「{'/'.join(requirements.locations)}」")

    if requirements.minimum_years:
        hit = db.scalar(
            select(func.count()).select_from(CandidateProfile)
            .where(CandidateProfile.years_experience >= requirements.minimum_years)
        ) or 0
        if hit == 0:
            # minimum_years 是浮点数，直接插值会显示成「99.0 年」——对用户只是噪音。
            min_years = requirements.minimum_years
            years_text = f"{min_years:g}" if isinstance(min_years, float) else str(min_years)
            blockers.append(f"没有候选人的工作年限达到 {years_text} 年")

    if requirements.management_required:
        hit = db.scalar(
            select(func.count()).select_from(CandidateProfile)
            .where(CandidateProfile.management_experience.is_(True))
        ) or 0
        if hit == 0:
            blockers.append("没有候选人具备团队管理经验")

    if blockers:
        return "没有找到匹配的候选人，原因可能是：" + "；".join(blockers) + "。放宽其中任意一项都能扩大范围。"

    return (
        f"简历库里有 {total} 位候选人，但没有一位同时满足全部条件。"
        "建议减少硬性要求，或把行业词换成更通用的说法"
        "（例如用「半导体」代替具体的产品线名称）。"
    )


def search_job(
    db: Session,
    job: JobRequirement,
    limit: int = 20,
    fusion: str = "hybrid",
    rerank: str | None = None,
    raw_text: str | None = None,
    requirements_override: "JobRequirements | None" = None,
) -> list[MatchResult]:
    """Rank candidates for a job.

    Three stages, each independently testable:

    1. **Recall** - hybrid (dense vector + lexical) fused with RRF.
    2. **Rerank** - ``rule`` (keyword coverage over the evidence) or ``llm``
       (one batched chat call scores the top-N).  The judge only ever feeds the
       20% ``rerank_score`` slot, so the UI's three transparent sub-scores and
       the 0.35 / 0.45 / 0.20 weighting stay intact.
    3. **Explain** - strengths/gaps are generated for the returned page only,
       not for every recalled candidate.
    """
    if fusion not in FUSION_MODES:
        fusion = "hybrid"

    settings = get_settings()
    mode = resolve_rerank_mode(settings, rerank)
    mask = settings.mask_pii

    # raw_text / requirements_override let the orchestration graph retry with a
    # rewritten query while still persisting results under the real job.
    requirements = requirements_override or JobRequirements.model_validate(job.requirements_json)
    query_text = (raw_text or job.raw_text or "").strip() or job.raw_text
    service = ModelService(db)
    query_vector = service.embed([query_text])[0]
    terms = _query_terms(requirements, settings.synonym_expansion)

    recalled_ids = _recall(db, query_vector, terms, fusion)
    if not recalled_ids:
        return []

    chunks = list(
        db.scalars(
            select(ResumeChunk)
            .where(ResumeChunk.id.in_(recalled_ids))
            .options(selectinload(ResumeChunk.candidate))
        )
    )
    by_id = {chunk.id: chunk for chunk in chunks}

    by_candidate: dict[str, list[tuple[ResumeChunk, float]]] = defaultdict(list)
    for chunk_id in recalled_ids:
        chunk = by_id.get(chunk_id)
        if chunk is None:
            continue
        vector = list(chunk.embedding) if chunk.embedding is not None else []
        by_candidate[chunk.candidate_id].append((chunk, max(0.0, cosine(query_vector, vector))))

    rows = []
    for candidate_id, candidate_chunks in by_candidate.items():
        candidate = db.get(CandidateProfile, candidate_id)
        if candidate is None:
            continue
        # Rank a candidate's own chunks by similarity: the best chunk gives the
        # semantic score, and the top few become the human-readable evidence.
        candidate_chunks.sort(key=lambda item: item[1], reverse=True)
        best_chunk, semantic = candidate_chunks[0]
        rows.append({
            "candidate": candidate,
            "structured": structured_score(requirements, candidate),
            "semantic": semantic,
            "rerank": keyword_rerank(requirements, candidate, best_chunk.content),
            # 对外的简历引用统一走 _clip / _mask：截断 + 脱敏（手机号 / 邮箱 / 身份证）。
            # explain_chunks 与 evidence_text 会被送进大模型，同样必须先脱敏。
            "evidence": [{"chunk_id": chunk.id, "section": chunk.section, "page_number": chunk.page_number, "quote": _clip(chunk.content, 360, mask)} for chunk, _ in candidate_chunks[:EVIDENCE_LIMIT]],
            "explain_chunks": [_mask(chunk.content, mask) for chunk, _ in candidate_chunks[:EVIDENCE_LIMIT]],
            "evidence_text": " ".join(_mask(chunk.content, mask) for chunk, _ in candidate_chunks[:2]),
        })

    def weighted(row: dict) -> float:
        return row["structured"] * 0.35 + row["semantic"] * 0.45 + row["rerank"] * 0.20

    rows.sort(key=weighted, reverse=True)

    if mode == "llm":
        shortlist = rows[: settings.rerank_top_n]
        payloads = [
            _candidate_payload(row["candidate"], CandidateExtract.model_validate(row["candidate"].profile_json), row["evidence_text"])
            for row in shortlist
        ]
        scores = service.rerank(requirements, payloads)
        if scores:
            for row in shortlist:
                if row["candidate"].id in scores:
                    row["rerank"] = scores[row["candidate"].id] / 100.0
            rows.sort(key=weighted, reverse=True)
        else:
            # Judge unavailable: keep the rule ordering and say so, rather than
            # storing scores that were not actually produced by the LLM.
            mode = "rule"

    # Evidence is only padded for the shortlist actually returned, so the extra
    # query cost is bounded by `limit` rather than by the recall pool.
    for row in rows[:limit]:
        if len(row["evidence"]) >= EVIDENCE_LIMIT:
            continue
        row["evidence"] += _pad_evidence(db, row["candidate"].id, {item["chunk_id"] for item in row["evidence"]}, mask=mask)
        row["explain_chunks"] = [item["quote"] for item in row["evidence"]]

    db.execute(delete(MatchResult).where(MatchResult.job_id == job.id))

    page = rows[:limit]

    # ------------------------------------------------------------------ 解释
    # 解释是整条链路最贵的环节：每个候选人一次大模型调用，串行时 20 人要
    # 40 秒以上，用户会以为系统卡死了。两个取舍：
    #   1. 只给前 explain_top_n 位用大模型解释——用户真正细看的只有前几名；
    #   2. 这几位**并行**调用（线程池，各自独立会话，线程内不写库），
    #      其余的用规则即时生成，零成本零延迟。
    # 排序不受影响：解释只产出门面上的 strengths/gaps，分数在进这里之前就算完了。
    page_top = page[: settings.explain_top_n]
    explanations: dict[int, MatchExplanation] = {}

    if page_top:
        prepared = []
        for row in page_top:
            data = CandidateExtract.model_validate(row["candidate"].profile_json)
            prepared.append((row, data, row["explain_chunks"]))
        batch_started = time.perf_counter()
        workers = max(1, min(6, len(prepared)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [(row, data, pool.submit(_explain_offline, requirements, data, chunks))
                       for row, data, chunks in prepared]
            for row, data, future in futures:
                try:
                    explanations[id(row)] = future.result()
                except Exception:  # noqa: BLE001 - 单个解释失败不该拖垮整页
                    explanations[id(row)] = evidence_explanation(requirements, data)
        # 聚合审计：并行线程里各自写库会撞 SQLite 写锁，这里由主线程补一条
        service._audit(
            "match_explain", settings.chat_model,
            f"match_explain:{job.id}:{len(prepared)}", batch_started, "success",
            provider=f"parallel:{workers}w",
        )

    for row in page[settings.explain_top_n:]:
        data = CandidateExtract.model_validate(row["candidate"].profile_json)
        explanations[id(row)] = evidence_explanation(requirements, data)

    results = []
    for row in page:
        candidate = row["candidate"]
        explanation = explanations[id(row)]
        result = MatchResult(
            job_id=job.id, candidate_id=candidate.id,
            total_score=round(weighted(row) * 100, 1),
            structured_score=round(row["structured"] * 100, 1),
            semantic_score=round(row["semantic"] * 100, 1),
            rerank_score=round(row["rerank"] * 100, 1),
            rerank_mode=mode,
            strengths=explanation.strengths,
            gaps=explanation.gaps, evidence=row["evidence"],
        )
        db.add(result)
        results.append(result)
    db.flush()
    db.commit()
    return results
