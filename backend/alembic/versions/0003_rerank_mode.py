"""Record which reranker produced match_results.rerank_score.

The relevance score can come from two different judges:

* ``rule`` - deterministic keyword coverage over the retrieved evidence
  (free, offline, reproducible -- the historical behaviour)
* ``llm``  - one batched chat call that scores the top-N candidates

Without persisting the choice, a stored match cannot be interpreted later:
the same 0.6 means different things depending on who produced it, and an
evaluation run could silently compare numbers from two different judges.

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "match_results",
        sa.Column("rerank_mode", sa.String(length=16), nullable=False, server_default="rule"),
    )


def downgrade() -> None:
    op.drop_column("match_results", "rerank_mode")
