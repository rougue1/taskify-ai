"""Pydantic v2 schemas for the Task resource."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.task import TaskPriority, TaskStatus


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
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    tags: list[str] | None
    due_date: datetime | None
    created_at: datetime
    updated_at: datetime
