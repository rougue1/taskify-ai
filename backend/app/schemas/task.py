"""Pydantic v2 schemas for the Task resource."""

from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.task import TaskPriority, TaskStatus


class TaskSortField(str, enum.Enum):
    """Columns the task list may be ordered by."""

    created_at = "created_at"
    updated_at = "updated_at"
    due_date = "due_date"
    priority = "priority"
    title = "title"


class SortOrder(str, enum.Enum):
    """Sort direction."""

    asc = "asc"
    desc = "desc"


class TaskCreate(BaseModel):
    """Payload for creating a task."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    status: TaskStatus = TaskStatus.todo
    priority: TaskPriority = TaskPriority.medium
    tags: list[str] | None = None
    due_date: datetime | None = None


class TaskUpdate(BaseModel):
    """Payload for partially updating a task.

    Every field is optional; only the fields that are explicitly provided are
    applied (see ``model_dump(exclude_unset=True)`` in the service layer).
    """

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    tags: list[str] | None = None
    due_date: datetime | None = None


class TaskRead(BaseModel):
    """Representation of a task returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    tags: list[str] = Field(default_factory=list)
    due_date: datetime | None
    created_at: datetime
    updated_at: datetime

    @field_validator("tags", mode="before")
    @classmethod
    def _coerce_tags(cls, value: object) -> object:
        # Normalize a NULL tags column to an empty array in the response.
        return value if value is not None else []


class PaginatedTasks(BaseModel):
    """A page of tasks plus pagination metadata."""

    items: list[TaskRead]
    total: int
    page: int
    page_size: int
    pages: int
