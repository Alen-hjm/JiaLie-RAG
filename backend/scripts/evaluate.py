"""检索质量评测。

在此之前，本文件只打印一句 "Run API searches and add ranked_candidate_keys
before scoring." —— 指标函数写好了，但从来没有真正跑出过数字。现在它会：

  1) 用真实检索链路（``search_job``，含召回融合 + 打分）对每条黄金样例排序；
  2) 计算 Recall@K / MRR / NDCG@K（NDCG 使用分级相关度，gain = 2^grade - 1）；
  3) 把配置快照与逐条明细写入 ``eval/results.json``，便于做基线对比。

两种对比方式：
  A. 融合策略对比（同一批向量，无需重建索引）
       python -m scripts.evaluate --fusion vector_only --out eval/results_baseline.json
       python -m scripts.evaluate --fusion hybrid      --out eval/results_hybrid.json
  B. 向量后端对比（需重建索引，见 scripts/reindex_embeddings.py）
       先配 hash 并 reindex --force  ->  --out eval/results_embed_hash.json
       再配真实 provider 并 reindex --force  ->  --out eval/results_embed_real.json

用法示例：
    cd backend
    .venv\\Scripts\\python -m scripts.evaluate --list-candidates
    .venv\\Scripts\\python -m scripts.evaluate
    .venv\\Scripts\\python -m scripts.evaluate --fusion vector_only --keep
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.models import CandidateProfile, JobRequirement, ResumeDocument  # noqa: E402
from app.services.llm import ModelService  # noqa: E402
from app.services.search import search_job  # noqa: E402
from app.services.vectors import vector_stats  # noqa: E402

DEFAULT_GOLD = BACKEND_DIR / "eval" / "gold.json"
DEFAULT_OUT = BACKEND_DIR / "eval" / "results.json"
DEFAULT_KS = (5, 10)
# 评测产生的岗位带这个前缀，便于识别与清理。
EVAL_TITLE_PREFIX = "【评测】"


# ---------------------------------------------------------------------------
# 指标
# ---------------------------------------------------------------------------

def recall_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 1.0
    return len(set(ranked_ids[:k]) & relevant_ids) / len(relevant_ids)


def reciprocal_rank(ranked_ids: list[str], relevant_ids: set[str]) -> float:
    for index, item in enumerate(ranked_ids, 1):
        if item in relevant_ids:
            return 1 / index
    return 0.0


def ndcg_at_k(ranked_grades: list[int], ideal_grades: list[int], k: int) -> float:
    """NDCG with graded relevance; gain = 2^grade - 1."""
    dcg = sum((2 ** grade - 1) / math.log2(index + 2) for index, grade in enumerate(ranked_grades[:k]))
    idcg = sum((2 ** grade - 1) / math.log2(index + 2) for index, grade in enumerate(sorted(ideal_grades, reverse=True)[:k]))
    return dcg / idcg if idcg else 1.0


# ---------------------------------------------------------------------------
# 黄金集
# ---------------------------------------------------------------------------

def load_gold(path: Path) -> tuple[list[dict], dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    # Backwards compatible with the original v1 file, which was a bare list.
    if isinstance(payload, list):
        cases = [
            {
                "case_id": item.get("case_id", f"case-{index}"),
                "jd": item["jd"],
                "expected": [{"key": f"name:{name}", "label": name, "grade": 3} for name in item.get("expected_candidate_keys", [])],
                "required_evidence": item.get("required_evidence", []),
            }
            for index, item in enumerate(payload)
        ]
        return cases, {"version": 1, "relevant_grade_threshold": 2}
    return payload.get("cases", []), {
        "version": payload.get("version", 2),
        "relevant_grade_threshold": int(payload.get("relevant_grade_threshold", 2)),
    }


def candidate_index(db) -> tuple[dict[str, tuple[str, str]], dict[str, str]]:
    """Return (candidate_id -> (sha256 key, name), lookup key -> candidate_id)."""
    rows = db.execute(
        select(CandidateProfile.id, CandidateProfile.name, ResumeDocument.sha256).join(
            ResumeDocument, ResumeDocument.id == CandidateProfile.document_id
        )
    ).all()
    info: dict[str, tuple[str, str]] = {}
    by_key: dict[str, str] = {}
    for candidate_id, name, sha256 in rows:
        key = f"sha256:{sha256}"
        info[candidate_id] = (key, name)
        by_key[key] = candidate_id
        by_key.setdefault(f"name:{name}", candidate_id)
    return info, by_key


def resolve_entry(raw_key: str, by_key: dict[str, str]) -> str | None:
    """Look a gold entry up by sha256 key, explicit name key, or bare name."""
    candidate_id = by_key.get(raw_key)
    if candidate_id is None and not raw_key.startswith(("sha256:", "name:")):
        candidate_id = by_key.get(f"name:{raw_key}")
    return candidate_id


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def evaluate(gold_path: Path, fusion: str, ks: tuple[int, ...], limit: int, keep: bool, rerank: str | None = None) -> dict:
    settings = get_settings()
    cases, meta = load_gold(gold_path)
    threshold = meta["relevant_grade_threshold"]

    case_results: list[dict] = []
    unresolved: dict[str, list[str]] = {}

    with SessionLocal() as db:
        info, by_key = candidate_index(db)
        service = ModelService(db)
        created_jobs: list[JobRequirement] = []

        for case in cases:
            expected: list[tuple[str, int, str]] = []
            missing: list[str] = []
            for entry in case.get("expected", []):
                raw_key = str(entry.get("key", ""))
                candidate_id = resolve_entry(raw_key, by_key)
                if candidate_id is None:
                    missing.append(str(entry.get("label") or raw_key))
                    continue
                key, name = info[candidate_id]
                expected.append((key, int(entry.get("grade", 3)), str(entry.get("label") or name)))
            if missing:
                unresolved[case["case_id"]] = missing

            requirements = service.parse_job(case["jd"])
            job = JobRequirement(
                company=requirements.company,
                location=requirements.locations[0] if requirements.locations else "",
                title=f"{EVAL_TITLE_PREFIX}{requirements.title}",
                raw_text=case["jd"],
                requirements_json=requirements.model_dump(),
            )
            db.add(job)
            db.flush()
            created_jobs.append(job)

            matches = search_job(db, job, limit=limit, fusion=fusion, rerank=rerank)
            ranked: list[tuple[str, str, object]] = [
                (info.get(match.candidate_id, (f"id:{match.candidate_id}", ""))[0],
                 info.get(match.candidate_id, ("", match.candidate_id))[1],
                 match)
                for match in matches
            ]
            ranked_ids = [key for key, _, _ in ranked]

            grades = {key: grade for key, grade, _ in expected}
            relevant_ids = {key for key, grade in grades.items() if grade >= threshold}
            ranked_grades = [grades.get(key, 0) for key in ranked_ids]

            evidence_blob = " ".join(
                str(item.get("quote", "")) for _, _, match in ranked for item in (match.evidence or [])
            )
            required_terms = case.get("required_evidence", [])
            evidence_hits = [term for term in required_terms if term in evidence_blob]

            case_result: dict = {
                "case_id": case["case_id"],
                "jd": case["jd"],
                "expected": [{"key": key, "label": label, "grade": grade} for key, grade, label in expected],
                "unresolved": missing,
                "ranked": [
                    {
                        "rank": index,
                        "key": key,
                        "label": label,
                        "grade": grades.get(key, 0),
                        "total_score": match.total_score,
                        "structured_score": match.structured_score,
                        "semantic_score": match.semantic_score,
                        "rerank_score": match.rerank_score,
                        "rerank_mode": match.rerank_mode,
                    }
                    for index, (key, label, match) in enumerate(ranked, 1)
                ],
                "evidence_coverage": round(len(evidence_hits) / len(required_terms), 3) if required_terms else None,
                "evidence_missing": [term for term in required_terms if term not in evidence_hits],
            }
            for k in ks:
                case_result[f"recall@{k}"] = round(recall_at_k(ranked_ids, relevant_ids, k), 4)
                case_result[f"ndcg@{k}"] = round(ndcg_at_k(ranked_grades, [g for _, g, _ in expected], k), 4)
            case_result["mrr"] = round(reciprocal_rank(ranked_ids, relevant_ids), 4)
            case_results.append(case_result)

        stats = vector_stats(db)

        if not keep:
            for job in created_jobs:
                db.delete(job)  # cascades to its MatchResult rows
            db.commit()

    aggregate: dict[str, float] = {}
    if case_results:
        for k in ks:
            aggregate[f"recall@{k}"] = round(sum(c[f"recall@{k}"] for c in case_results) / len(case_results), 4)
            aggregate[f"ndcg@{k}"] = round(sum(c[f"ndcg@{k}"] for c in case_results) / len(case_results), 4)
        aggregate["mrr"] = round(sum(c["mrr"] for c in case_results) / len(case_results), 4)
        coverage = [c["evidence_coverage"] for c in case_results if c["evidence_coverage"] is not None]
        if coverage:
            aggregate["evidence_coverage"] = round(sum(coverage) / len(coverage), 4)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "gold_file": gold_path.name,
        "gold_version": meta["version"],
        "config": {
            "database": engine.dialect.name,
            "fusion": fusion,
            "rerank_mode": rerank or settings.rerank_mode,
            "weights": {"structured": 0.35, "semantic": 0.45, "rerank": 0.20},
            "model_mode": settings.model_mode,
            "chat_model": settings.chat_model,
            "embedding_provider": settings.embedding_provider,
            "embedding_model": settings.embedding_model,
            "embedding_dimensions": settings.embedding_dimensions,
            "embedding_is_placeholder": settings.embedding_is_placeholder,
            "relevant_grade_threshold": threshold,
            "corpus": {
                "candidates": sum(1 for key in by_key if key.startswith("sha256:")),
                "chunks": stats["total_chunks"],
            },
        },
        "aggregate": aggregate,
        "unresolved_expected": unresolved,
        "cases": case_results,
    }


def list_candidates() -> None:
    with SessionLocal() as db:
        rows = db.execute(
            select(CandidateProfile.name, CandidateProfile.current_title, ResumeDocument.sha256).join(
                ResumeDocument, ResumeDocument.id == CandidateProfile.document_id
            ).order_by(CandidateProfile.name)
        ).all()
    print(f"共 {len(rows)} 位候选人（可直接粘进 eval/gold.json 的 expected[].key）\n")
    for name, title, sha256 in rows:
        print(f"  {name:<8} {title or '-':<10} sha256:{sha256}")


def main() -> int:
    parser = argparse.ArgumentParser(description="检索质量评测")
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--fusion", choices=("hybrid", "vector_only"), default="hybrid")
    parser.add_argument("--rerank", choices=("rule", "llm"), default=None,
                        help="重排打分者：rule=关键词覆盖（默认），llm=大模型批量打分。留空则跟随 .env 的 RERANK_MODE")
    parser.add_argument("--top-k", type=int, nargs="+", default=list(DEFAULT_KS))
    parser.add_argument("--limit", type=int, default=50, help="每条样例最多返回多少位候选人")
    parser.add_argument("--keep", action="store_true", help="保留评测产生的岗位与匹配记录（默认清理）")
    parser.add_argument("--list-candidates", action="store_true", help="只列出候选人标识，便于编写黄金集")
    args = parser.parse_args()

    if args.list_candidates:
        list_candidates()
        return 0

    if not args.gold.exists():
        print(f"找不到黄金集：{args.gold}", file=sys.stderr)
        return 2

    report = evaluate(args.gold, args.fusion, tuple(args.top_k), args.limit, args.keep, args.rerank)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    config = report["config"]
    print("=" * 78)
    print(f"检索评测  fusion={config['fusion']}  rerank={config['rerank_mode']}"
          f"  embedding={config['embedding_provider']}:{config['embedding_model']}")
    print(f"向量后端：{'占位（哈希，无语义）' if config['embedding_is_placeholder'] else '真实'}"
          f"  维度 {config['embedding_dimensions']}  语料 {config['corpus']['candidates']} 人 / {config['corpus']['chunks']} chunk")
    print("=" * 78)
    print(f"{'case_id':<40}" + "".join(f"{f'R@{k}':>8}" for k in args.top_k) + f"{'MRR':>8}" + "".join(f"{f'nDCG@{k}':>8}" for k in args.top_k))
    for case in report["cases"]:
        row = f"{case['case_id']:<40}"
        row += "".join(f"{case[f'recall@{k}']:>8.2f}" for k in args.top_k)
        row += f"{case['mrr']:>8.2f}"
        row += "".join(f"{case[f'ndcg@{k}']:>8.2f}" for k in args.top_k)
        print(row)
    print("-" * 78)
    agg = report["aggregate"]
    row = f"{'平均（aggregate）':<40}"
    row += "".join(f"{agg[f'recall@{k}']:>8.2f}" for k in args.top_k)
    row += f"{agg['mrr']:>8.2f}"
    row += "".join(f"{agg[f'ndcg@{k}']:>8.2f}" for k in args.top_k)
    print(row)
    if report["unresolved_expected"]:
        print("\n⚠ 以下黄金集条目未匹配到候选人（语料重建过？用 --list-candidates 更新 key）：")
        for case_id, labels in report["unresolved_expected"].items():
            print(f"  {case_id}: {', '.join(labels)}")
    print(f"\n明细已写入：{args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
