"""Add an HNSW index on resume_chunks.embedding (PostgreSQL / pgvector only).

Before this, similarity search loaded every chunk into memory and scored it in
Python.  The index lets ``ORDER BY embedding <=> :query`` be served by an
approximate nearest-neighbour scan instead, which is what makes the retrieval
stage scale past a demo corpus.

Not applied to SQLite: the dialect has no vector type, so vectors there are
stored as text and scored in Python (handled in
``app/services/search.py::_vector_lane``).

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

INDEX_NAME = "ix_resume_chunks_embedding_hnsw"


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    # HNSW needs a fixed dimension on the column; it is created by 0001.
    op.execute(
        f"""
        CREATE INDEX IF NOT EXISTS {INDEX_NAME}
        ON resume_chunks USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
