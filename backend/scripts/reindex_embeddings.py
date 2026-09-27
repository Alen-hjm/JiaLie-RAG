"""重建简历文本块的向量索引。

为什么需要这个脚本，而不是开机自动跑：
  1) 向量是派生数据，换了 embedding 服务商/模型/维度之后必须重算，旧向量与新
     配置混在一起会让余弦相似度算出无意义的结果（维度不同时必须显式清空再改列）。
  2) 真实 embedding 是按量计费的，放在启动流程里"每次开机全量重算"既慢又烧钱，
     所以这里做成显式、可续跑的动作。

典型用法：
    cd backend
    ..\\..\\           # 配置好 EMBEDDING_PROVIDER / EMBEDDING_API_KEY 之后
    .venv\\Scripts\\python -m scripts.reindex_embeddings --dry-run
    .venv\\Scripts\\python -m scripts.reindex_embeddings
    .venv\\Scripts\\python -m scripts.reindex_embeddings --only-failed
    .venv\\Scripts\\python -m scripts.reindex_embeddings --rebuild-index
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import func, select, text, update

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.models import ResumeChunk  # noqa: E402
from app.services.llm import ModelService  # noqa: E402

# Records which embedding configuration produced the vectors currently stored,
# so a provider/model switch is detected automatically instead of silently
# leaving old vectors (or placeholders) in place.
SIGNATURE_FILE = BACKEND_DIR / ".embedding-signature"
FAILED_FILE = BACKEND_DIR / "eval" / "reindex_failed.json"
HNSW_INDEX = "ix_resume_chunks_embedding_hnsw"


def current_signature() -> str:
    settings = get_settings()
    return f"{settings.embedding_provider}:{settings.embedding_model}:{settings.embedding_dimensions}"


def read_signature() -> str | None:
    if SIGNATURE_FILE.exists():
        return SIGNATURE_FILE.read_text(encoding="utf-8").strip() or None
    return None


def write_signature(value: str) -> None:
    SIGNATURE_FILE.write_text(value, encoding="utf-8")


def existing_column_dimension() -> int | None:
    """Read the declared vector dimension of resume_chunks.embedding (Postgres)."""
    if engine.dialect.name != "postgresql":
        return None
    sql = text(
        "SELECT format_type(a.atttypid, a.atttypmod) "
        "FROM pg_attribute a "
        "WHERE a.attrelid = 'resume_chunks'::regclass AND a.attname = 'embedding'"
    )
    with engine.begin() as connection:
        declared = connection.execute(sql).scalar()
    if not declared or "(" not in declared:
        return None
    digits = "".join(ch for ch in declared.split("(", 1)[1] if ch.isdigit())
    return int(digits) if digits else None


def resize_column(target_dimension: int, dry_run: bool) -> None:
    """NULL out vectors then ALTER the column to the new dimension.

    Order matters: Postgres cannot cast ``vector(1536)`` values into
    ``vector(1024)``, so the column has to be emptied before the type changes.
    """
    current = existing_column_dimension()
    if current is None:
        print(f"  · 跳过列维度调整（非 Postgres 或未检测到维度）")
        return
    if current == target_dimension:
        print(f"  · 列维度已是 vector({target_dimension})，无需调整")
        return
    print(f"  · 列维度 vector({current}) -> vector({target_dimension})，先清空旧向量")
    if dry_run:
        return
    with engine.begin() as connection:
        connection.execute(text("UPDATE resume_chunks SET embedding = NULL"))
        connection.execute(
            text(f"ALTER TABLE resume_chunks ALTER COLUMN embedding TYPE vector({target_dimension})")
        )


def rebuild_index(dry_run: bool, drop_first: bool = False) -> None:
    if engine.dialect.name != "postgresql":
        print("  · 非 Postgres，跳过 HNSW 索引")
        return
    with engine.begin() as connection:
        if drop_first:
            connection.execute(text(f"DROP INDEX IF EXISTS {HNSW_INDEX}"))
        connection.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS {HNSW_INDEX} "
                "ON resume_chunks USING hnsw (embedding vector_cosine_ops) "
                "WITH (m = 16, ef_construction = 64)"
            )
        )
    print(f"  · HNSW 索引就绪：{HNSW_INDEX}")


def pending_chunk_ids(force: bool, only_failed: bool) -> list[str]:
    failed_ids: list[str] = []
    if only_failed and FAILED_FILE.exists():
        try:
            failed_ids = json.loads(FAILED_FILE.read_text(encoding="utf-8")).get("chunk_ids", [])
        except json.JSONDecodeError:
            failed_ids = []
    with SessionLocal() as db:
        if force:
            ids = list(db.scalars(select(ResumeChunk.id).order_by(ResumeChunk.chunk_index)))
        elif only_failed:
            ids = []
            if failed_ids:
                ids = list(db.scalars(select(ResumeChunk.id).where(ResumeChunk.id.in_(failed_ids))))
        else:
            ids = list(
                db.scalars(select(ResumeChunk.id).where(ResumeChunk.embedding.is_(None)).order_by(ResumeChunk.chunk_index))
            )
    return ids


def null_mismatched_dimensions(target: int) -> int:
    """Drop vectors whose stored dimension differs from the target.

    This must happen *before* re-embedding, in its own commit.  Otherwise the
    ORM loads an old 1536-dim vector and assigns a new 1024-dim one, and the
    dirty check compares the two shapes element-wise -- which raises
    ``ValueError: operands could not be broadcast together`` instead of simply
    marking the field dirty.  NULLing first means the loaded value is None and
    the comparison is trivial.

    Vectors with the wrong dimension are unusable for cosine similarity anyway
    (``vectors.cosine`` returns 0 for them), so this loses nothing.
    """
    with SessionLocal() as db:
        rows = db.execute(select(ResumeChunk.id, ResumeChunk.embedding)).all()
        bad = [row_id for row_id, vector in rows if vector is not None and len(vector) != target]
        if not bad:
            return 0
        db.execute(update(ResumeChunk).where(ResumeChunk.id.in_(bad)).values(embedding=None))
        db.commit()
        return len(bad)


def main() -> int:
    parser = argparse.ArgumentParser(description="重建简历文本块的向量索引")
    parser.add_argument("--batch-size", type=int, default=32, help="每批提交的文本块数量")
    parser.add_argument("--force", action="store_true", help="忽略已有向量，全部重算")
    parser.add_argument("--only-failed", action="store_true", help="只重算上次失败的文本块")
    parser.add_argument("--rebuild-index", action="store_true", help="重建 HNSW 索引（会先删除）")
    parser.add_argument("--dry-run", action="store_true", help="只报告将要做什么，不写库")
    args = parser.parse_args()

    settings = get_settings()
    print("=" * 68)
    print("向量重建")
    print(f"  数据库      : {engine.dialect.name}")
    print(f"  provider    : {settings.embedding_provider}")
    print(f"  model       : {settings.embedding_model}")
    print(f"  dimensions  : {settings.embedding_dimensions}")
    print(f"  远程调用    : {'是' if settings.embedding_uses_remote else '否（将写入占位向量）'}")
    print("=" * 68)

    if settings.embedding_is_placeholder:
        print("⚠  当前没有可用的 embedding 凭证，本次只会写入**哈希占位向量**（无语义）。")
        print("   如果要做真实语义检索，请先在 .env 里配置 EMBEDDING_PROVIDER / EMBEDDING_API_KEY。")

    target = settings.embedding_dimensions
    signature = current_signature()
    previous = read_signature()
    switched = previous is not None and previous != signature
    if switched:
        print(f"检测到 embedding 配置变更：{previous}  ->  {signature}，需要全量重算。")
        args.force = True
    elif previous is None:
        print("首次运行：将记录本次 embedding 配置指纹。")

    print("\n[1/4] 调整向量列维度")
    resize_column(target, args.dry_run)
    if not args.dry_run:
        dropped = null_mismatched_dimensions(target)
        if dropped:
            print(f"  · 已清空 {dropped} 个维度与当前配置不一致的旧向量（稍后全部重算）")

    print("\n[2/4] 统计待处理文本块")
    ids = pending_chunk_ids(args.force, args.only_failed)
    with SessionLocal() as db:
        total_count = db.scalar(select(func.count()).select_from(ResumeChunk)) or 0
    print(f"  · 文本块总数：{total_count}，待处理：{len(ids)}")
    if not ids:
        print("  · 没有需要重建的向量（幂等：重复执行不会重算）")

    print("\n[3/4] 重算向量")
    if ids and not args.dry_run:
        failures: list[str] = []
        done = 0
        batch_size = max(1, args.batch_size)
        for start in range(0, len(ids), batch_size):
            batch = ids[start:start + batch_size]
            with SessionLocal() as db:
                rows = list(db.scalars(select(ResumeChunk).where(ResumeChunk.id.in_(batch))))
                if not rows:
                    continue
                service = ModelService(db)
                try:
                    vectors = service.embed([row.content for row in rows])
                except Exception as exc:  # noqa: BLE001 - report and keep going
                    print(f"  ! 批次 {start // batch_size + 1} 失败：{exc}")
                    failures.extend(row.id for row in rows)
                    db.commit()  # 保留审计记录
                    continue
                for row, vector in zip(rows, vectors):
                    row.embedding = vector
                db.commit()
                done += len(rows)
                print(f"  · 进度 {done}/{len(ids)}")
        if failures:
            FAILED_FILE.parent.mkdir(parents=True, exist_ok=True)
            FAILED_FILE.write_text(
                json.dumps({"signature": signature, "chunk_ids": failures}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"  ! {len(failures)} 个文本块失败，已写入 {FAILED_FILE.name}，可加 --only-failed 续跑")
        else:
            if FAILED_FILE.exists():
                FAILED_FILE.unlink()
    elif args.dry_run and ids:
        print(f"  · dry-run：将重算 {len(ids)} 个文本块")

    print("\n[4/4] 索引与指纹")
    if args.rebuild_index and not args.dry_run:
        rebuild_index(args.dry_run, drop_first=True)
    else:
        rebuild_index(args.dry_run)
    if not args.dry_run:
        write_signature(signature)
        print(f"  · 已记录配置指纹：{signature}")

    print("\n完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
