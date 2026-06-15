"""The :class:`Task` ORM model and its enums."""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TaskStatus(str, enum.Enum):
    """Lifecycle state of a task."""

    todo = "todo"
    in_progress = "in_progress"
    done = "done"


class TaskPriority(str, enum.Enum):
    """Relative importance of a task."""

    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


def _utcnow() -> datetime:
    """Return the current timezone-aware UTC timestamp."""

    return datetime.now(UTC)


class Task(Base):
    """A single task owned by the user.

    The column definitions deliberately use portable types (``JSON``,
    ``DateTime(timezone=True)``, native ``Enum``) so the schema migrates
    cleanly from SQLite to PostgreSQL in a later milestone.
    """

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status", native_enum=False, length=20),
        nullable=False,
        default=TaskStatus.todo,
        server_default=TaskStatus.todo.value,
        index=True,
    )
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority, name="task_priority", native_enum=False, length=20),
        nullable=False,
        default=TaskPriority.medium,
        server_default=TaskPriority.medium.value,
        index=True,
    )
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the task to a plain JSON-friendly dictionary.

        Used by the agent tools when returning data to the language model.
        """

        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value if self.status else None,
            "priority": self.priority.value if self.priority else None,
            "tags": self.tags or [],
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Task id={self.id} title={self.title!r} status={self.status}>"
