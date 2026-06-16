"""task embeddings (pgvector) for semantic search

Adds a 768-dim ``embedding`` column to ``tasks`` and enables the ``vector``
extension — but only on PostgreSQL. On SQLite (used for local dev and tests) this
migration is a deliberate no-op, so the app still boots and runs its startup
migrations without a vector-capable database. Semantic search degrades gracefully
when the column is absent (see ``app/services/embedding.py``).

Revision ID: 003_task_embeddings
Revises: 002_users_and_task_ownership
Create Date: 2026-06-16

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003_task_embeddings"
down_revision: str | None = "002_users_and_task_ownership"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBED_DIM = 768


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite (and anything non-Postgres) has no vector type — skip cleanly.
        return

    from pgvector.sqlalchemy import Vector

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("tasks", sa.Column("embedding", Vector(EMBED_DIM), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.drop_column("tasks", "embedding")
