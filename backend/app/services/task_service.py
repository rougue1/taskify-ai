"""Business logic for the Task resource.

These functions are intentionally transport-agnostic: they accept a session and
plain arguments, and are reused by both the REST API and the agent tools.

Every query accepts an optional ``user_id``; when provided, results are scoped
to that owner (this is how per-user data isolation is enforced from v0.5). The
agent tools always pass the authenticated user's id so the LLM can never reach
another account's tasks.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, case, func, nulls_last, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskPriority, TaskStatus
from app.schemas.task import SortOrder, TaskCreate, TaskSortField, TaskUpdate

# Semantic rank for priority so sorting follows urgency, not alphabetical order.
_PRIORITY_ORDER = {
    TaskPriority.low: 0,
    TaskPriority.medium: 1,
    TaskPriority.high: 2,
    TaskPriority.urgent: 3,
}


def _priority_rank() -> Any:
    """A SQL CASE expression mapping each priority to its semantic rank."""

    return case(
        *((Task.priority == member, rank) for member, rank in _PRIORITY_ORDER.items()),
        else_=0,
    )


def _scoped(stmt: Select, user_id: int | None) -> Select:
    """Restrict a statement to a single owner when ``user_id`` is given."""

    if user_id is not None:
        stmt = stmt.where(Task.user_id == user_id)
    return stmt


def _order_by(sort_by: TaskSortField, sort_order: SortOrder) -> list[Any]:
    """Build the ORDER BY column list, including a stable id tiebreaker."""

    descending = sort_order == SortOrder.desc
    if sort_by == TaskSortField.priority:
        column: Any = _priority_rank()
    elif sort_by == TaskSortField.title:
        column = func.lower(Task.title)
    else:  # created_at, updated_at, due_date
        column = getattr(Task, sort_by.value)

    ordered = column.desc() if descending else column.asc()
    if sort_by == TaskSortField.due_date:
        # Keep undated tasks at the end regardless of direction.
        ordered = nulls_last(ordered)
    return [ordered, Task.id.desc()]


async def list_tasks(
    session: AsyncSession,
    *,
    user_id: int | None = None,
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    sort_by: TaskSortField = TaskSortField.created_at,
    sort_order: SortOrder = SortOrder.desc,
) -> list[Task]:
    """Return all matching tasks (unpaginated), optionally filtered and sorted."""

    stmt = _scoped(select(Task), user_id)
    if status is not None:
        stmt = stmt.where(Task.status == status)
    if priority is not None:
        stmt = stmt.where(Task.priority == priority)
    stmt = stmt.order_by(*_order_by(sort_by, sort_order))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_tasks_page(
    session: AsyncSession,
    *,
    user_id: int | None = None,
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    sort_by: TaskSortField = TaskSortField.created_at,
    sort_order: SortOrder = SortOrder.desc,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Task], int]:
    """Return one page of tasks plus the total count of matching rows."""

    base = _scoped(select(Task), user_id)
    if status is not None:
        base = base.where(Task.status == status)
    if priority is not None:
        base = base.where(Task.priority == priority)

    count_stmt = select(func.count()).select_from(base.order_by(None).subquery())
    total = int((await session.execute(count_stmt)).scalar_one())

    stmt = (
        base.order_by(*_order_by(sort_by, sort_order))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_task(
    session: AsyncSession, task_id: int, *, user_id: int | None = None
) -> Task | None:
    """Return a single task by id (scoped to ``user_id``), or ``None``."""

    task = await session.get(Task, task_id)
    if task is None:
        return None
    if user_id is not None and task.user_id != user_id:
        return None
    return task


async def create_task(session: AsyncSession, data: TaskCreate, *, user_id: int) -> Task:
    """Persist a new task owned by ``user_id`` and return it."""

    task = Task(**data.model_dump(), user_id=user_id)
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def update_task(
    session: AsyncSession, task_id: int, data: TaskUpdate, *, user_id: int | None = None
) -> Task | None:
    """Apply a partial update to a task. Returns ``None`` if not found/owned."""

    task = await get_task(session, task_id, user_id=user_id)
    if task is None:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    await session.commit()
    await session.refresh(task)
    return task


async def delete_task(
    session: AsyncSession, task_id: int, *, user_id: int | None = None
) -> bool:
    """Delete a task. Returns ``True`` if a row owned by the user was removed."""

    task = await get_task(session, task_id, user_id=user_id)
    if task is None:
        return False
    await session.delete(task)
    await session.commit()
    return True


async def search_tasks(
    session: AsyncSession,
    query: str,
    *,
    user_id: int | None = None,
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
) -> list[Task]:
    """Search tasks whose title or description matches ``query`` (case-insensitive)."""

    stmt = _scoped(select(Task), user_id)
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


async def prioritize_tasks(
    session: AsyncSession,
    *,
    user_id: int | None = None,
    by: str = "due_date",
    limit: int = 10,
) -> list[Task]:
    """Return the top ``limit`` *incomplete* tasks ranked by ``by``.

    ``by`` is one of ``due_date`` (soonest first, undated last),
    ``priority`` (most urgent first) or ``created_at`` (oldest first).
    """

    stmt = _scoped(select(Task), user_id).where(Task.status != TaskStatus.done)

    if by == "priority":
        order = [_priority_rank().desc(), nulls_last(Task.due_date.asc()), Task.id.asc()]
    elif by == "created_at":
        order = [Task.created_at.asc(), Task.id.asc()]
    else:  # due_date (default)
        order = [nulls_last(Task.due_date.asc()), _priority_rank().desc(), Task.id.asc()]

    stmt = stmt.order_by(*order).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def summarize(session: AsyncSession, *, user_id: int | None = None) -> dict[str, Any]:
    """Return aggregate counts plus the soonest-due open tasks.

    The summary contains the total task count, counts grouped by status and by
    priority, and the next three open tasks ordered by due date.
    """

    by_status: dict[str, int] = {s.value: 0 for s in TaskStatus}
    status_stmt = _scoped(select(Task.status, func.count()), user_id).group_by(Task.status)
    for status_value, count in (await session.execute(status_stmt)).all():
        key = status_value.value if isinstance(status_value, TaskStatus) else str(status_value)
        by_status[key] = count

    by_priority: dict[str, int] = {p.value: 0 for p in TaskPriority}
    priority_stmt = _scoped(select(Task.priority, func.count()), user_id).group_by(Task.priority)
    for priority_value, count in (await session.execute(priority_stmt)).all():
        key = (
            priority_value.value
            if isinstance(priority_value, TaskPriority)
            else str(priority_value)
        )
        by_priority[key] = count

    upcoming_stmt = (
        _scoped(select(Task), user_id)
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
