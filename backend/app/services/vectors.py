"""Shared vector helpers: dimension bookkeeping and placeholder detection.

Why this module exists: chat and embeddings are configured independently and the
embedding provider can change at runtime (UI settings -> .env -> lru_cache
cleared).  Vectors written under a previous provider keep their old dimension,
and cosine similarity across mismatched dimensions silently returns a
meaningless number instead of failing loudly.  Everything that touches vectors
goes through here so the mismatch is visible instead of silent.
"""

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import ResumeChunk


def cosine(a: list[float], b: list[float]) -> float:
    import math

    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return float(dot / norm) if norm else 0.0


def vector_stats(db: Session) -> dict:
    """Count chunks per stored vector dimension and flag config mismatches."""
    settings = get_settings()
    expected = settings.embedding_dimensions
    rows = db.execute(select(ResumeChunk.embedding)).scalars().all()
    dimensions: Counter[int] = Counter()
    missing = 0
    for value in rows:
        if value is None:
            missing += 1
            continue
        dimensions[len(value)] += 1
    mismatched = sum(count for size, count in dimensions.items() if size != expected)
    return {
        "total_chunks": len(rows),
        "missing_vectors": missing,
        "dimension_counts": {str(size): count for size, count in sorted(dimensions.items())},
        "expected_dimension": expected,
        "mismatched_vectors": mismatched,
        "needs_reindex": missing > 0 or mismatched > 0,
        "is_placeholder": settings.embedding_is_placeholder,
        "embedding_label": settings.embedding_label,
        "embedding_provider": settings.embedding_provider,
        "embedding_mode": settings.embedding_mode,
        "embedding_model": settings.embedding_model,
        "has_embedding_key": bool(settings.embedding_api_key),
    }
