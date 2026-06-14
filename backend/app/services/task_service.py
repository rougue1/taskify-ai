"""Business logic for the Task resource.

These functions are intentionally transport-agnostic: they accept a session and
plain arguments, and are reused by both the REST API and the agent tools.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskPriority, TaskStatus
from app.schemas.task import TaskCreate, TaskUpdate


async def list_tasks(
    session: AsyncSession,
    *,
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
) -> list[Task]:
    """Return all tasks, optionally filtered by status and/or priority."""

    stmt = select(Task)
    if status is not None:
        stmt = stmt.where(Task.status == status)
    if priority is not None:
        stmt = stmt.where(Task.priority == priority)
    stmt = stmt.order_by(Task.created_at.desc(), Task.id.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_task(session: AsyncSession, task_id: int) -> Task | None:
    """Return a single task by id, or ``None`` if it does not exist."""

    return await session.get(Task, task_id)


async def create_task(session: AsyncSession, data: TaskCreate) -> Task:
    """Persist a new task and return it."""

    task = Task(**data.model_dump())
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def update_task(session: AsyncSession, task_id: int, data: TaskUpdate) -> Task | None:
    """Apply a partial update to a task. Returns ``None`` if not found."""

    task = await session.get(Task, task_id)
    if task is None:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    await session.commit()
    await session.refresh(task)
    return task


async def delete_task(session: AsyncSession, task_id: int) -> bool:
    """Delete a task. Returns ``True`` if a row was removed."""

    task = await session.get(Task, task_id)
    if task is None:
        return False
    await session.delete(task)
    await session.commit()
    return True


async def search_tasks(
    session: AsyncSession,
    query: str,
    *,
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
) -> list[Task]:
    """Search tasks whose title or description matches ``query`` (case-insensitive)."""

    stmt = select(Task)
    if query:
        pattern = f"%{query}%"
        stmt = stmt.where(or_(Task.title.ilike(pattern), Task.description.ilike(pattern)))
    if status is not None:
        stmt = stmt.where(Task.status == status)
    if priority is not None:
        stmt = stmt.where(Task.priority == priority)
    stmt = stmt.order_by(Task.created_at.desc(), Task.id.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def summarize(session: AsyncSession) -> dict[str, Any]:
    """Return aggregate counts plus the soonest-due open tasks.

    The summary contains the total task count, counts grouped by status and by
    priority, and the next three open tasks ordered by due date.
    """

    by_status: dict[str, int] = {s.value: 0 for s in TaskStatus}
    status_rows = await session.execute(select(Task.status, func.count()).group_by(Task.status))
    for status_value, count in status_rows.all():
        key = status_value.value if isinstance(status_value, TaskStatus) else str(status_value)
        by_status[key] = count

    by_priority: dict[str, int] = {p.value: 0 for p in TaskPriority}
    priority_rows = await session.execute(
        select(Task.priority, func.count()).group_by(Task.priority)
    )
    for priority_value, count in priority_rows.all():
        key = (
            priority_value.value
            if isinstance(priority_value, TaskPriority)
            else str(priority_value)
        )
        by_priority[key] = count

    upcoming_stmt = (
        select(Task)
        .where(Task.due_date.is_not(None))
        .where(Task.status != TaskStatus.done)
        .order_by(Task.due_date.asc())
        .limit(3)
    )
    upcoming_rows = await session.execute(upcoming_stmt)
    upcoming = [task.to_dict() for task in upcoming_rows.scalars().all()]

    return {
        "total": sum(by_status.values()),
        "by_status": by_status,
        "by_priority": by_priority,
        "upcoming": upcoming,
    }
