"""users table and per-user task ownership

Adds the ``users`` table and a non-nullable ``tasks.user_id`` foreign key.
Existing tasks are reassigned to a seeded system user (id=1) with an unusable
password hash so the account can own legacy rows but can never be logged into.

Revision ID: 002_users_and_task_ownership
Revises: 001_initial
Create Date: 2026-06-15

"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_users_and_task_ownership"
down_revision: str | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SYSTEM_USER_ID = 1
SYSTEM_USER_EMAIL = "system@taskify.local"
# Deliberately not a valid bcrypt hash: verify_password() can never match it.
UNUSABLE_PASSWORD = "!"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # Seed the system user that will own all pre-auth tasks.
    users = sa.table(
        "users",
        sa.column("id", sa.Integer),
        sa.column("email", sa.String),
        sa.column("hashed_password", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("created_at", sa.DateTime),
    )
    op.bulk_insert(
        users,
        [
            {
                "id": SYSTEM_USER_ID,
                "email": SYSTEM_USER_EMAIL,
                "hashed_password": UNUSABLE_PASSWORD,
                "is_active": True,
                "created_at": datetime.now(UTC),
            }
        ],
    )

    # Add the column nullable, backfill, then enforce NOT NULL + FK + index.
    op.add_column("tasks", sa.Column("user_id", sa.Integer(), nullable=True))
    op.execute(f"UPDATE tasks SET user_id = {SYSTEM_USER_ID} WHERE user_id IS NULL")
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_index("ix_tasks_user_id", ["user_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_tasks_user_id_users", "users", ["user_id"], ["id"], ondelete="CASCADE"
        )


def downgrade() -> None:
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_constraint("fk_tasks_user_id_users", type_="foreignkey")
        batch_op.drop_index("ix_tasks_user_id")
        batch_op.drop_column("user_id")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
