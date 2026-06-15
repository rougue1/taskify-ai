"""LangGraph tools the agent can call.

Each tool is a real, async ``@tool`` that performs database work through the
shared service layer, scoped to the authenticated user (resolved from the
request context — never an LLM-visible argument). Tools return JSON strings so
the value on the resulting ``ToolMessage`` is always clean, unambiguous text.

Robustness: tools **never raise**. Any failure (validation, missing user,
database error) is caught and returned as a structured ``{"error": ...}`` object
so the agent can read what went wrong and recover instead of crashing the graph.
"""

from __future__ import annotations

import functools
import json
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from langchain_core.tools import tool

from app.agent.context import get_current_user_id
from app.database import session_scope
from app.models.task import TaskPriority, TaskStatus
from app.schemas.task import TaskCreate, TaskUpdate
from app.services import task_service

_STATUS_VALUES = [s.value for s in TaskStatus]
_PRIORITY_VALUES = [p.value for p in TaskPriority]
_PRIORITIZE_FIELDS = {"due_date", "priority", "created_at"}


def _error(message: str) -> str:
    """Serialize a structured, agent-readable error object."""

    return json.dumps({"error": message})


def safe_tool(func: Callable[..., Awaitable[str]]) -> Callable[..., Awaitable[str]]:
    """Wrap a tool coroutine so unexpected exceptions become error objects.

    ``functools.wraps`` preserves the signature/docstring so ``@tool`` still
    derives the correct schema from the wrapped function.
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> str:
        try:
            return await func(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - tools must never raise into the graph
            return _error(f"{func.__name__} failed: {exc}")

    return wrapper


def _coerce_status(value: str | None) -> TaskStatus | None:
    """Validate an optional status string, returning ``None`` when omitted."""

    if value is None or value == "":
        return None
    try:
        return TaskStatus(value)
    except ValueError as exc:
        raise ValueError(f"Invalid status '{value}'. Must be one of: {_STATUS_VALUES}.") from exc


def _coerce_priority(value: str | None) -> TaskPriority | None:
    """Validate an optional priority string, returning ``None`` when omitted."""

    if value is None or value == "":
        return None
    try:
        return TaskPriority(value)
    except ValueError as exc:
        raise ValueError(
            f"Invalid priority '{value}'. Must be one of: {_PRIORITY_VALUES}."
        ) from exc


def _parse_due_date(value: str | None) -> datetime | None:
    """Best-effort parsing of a due date string (full NL parsing lands in v0.6)."""

    if not value:
        return None
    text = value.strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(
        f"Could not parse due_date '{value}'. Use ISO format, e.g. 2026-06-20 or 2026-06-20T15:00."
    )


def _require_user() -> int:
    """Return the current user id or raise so ``safe_tool`` reports it cleanly."""

    user_id = get_current_user_id()
    if user_id is None:
        raise RuntimeError("No authenticated user is bound to this request.")
    return user_id


@tool
@safe_tool
async def search_tasks(query: str, status: str | None = None, priority: str | None = None) -> str:
    """Search the user's tasks by text across the title and description.

    Args:
        query: Free-text search string. Pass an empty string to list everything.
        status: Optional status filter. One of: todo, in_progress, done.
        priority: Optional priority filter. One of: low, medium, high, urgent.

    Returns:
        JSON with the match ``count`` and a ``tasks`` array.
    """

    user_id = _require_user()
    try:
        status_enum = _coerce_status(status)
        priority_enum = _coerce_priority(priority)
    except ValueError as exc:
        return _error(str(exc))

    async with session_scope() as session:
        tasks = await task_service.search_tasks(
            session, query or "", user_id=user_id, status=status_enum, priority=priority_enum
        )
        return json.dumps(
            {"count": len(tasks), "tasks": [t.to_dict() for t in tasks]},
            default=str,
        )


@tool
@safe_tool
async def create_task(
    title: str,
    description: str | None = None,
    priority: str = "medium",
    due_date: str | None = None,
) -> str:
    """Create a new task for the user.

    Args:
        title: Short title of the task (required).
        description: Optional longer description.
        priority: One of: low, medium, high, urgent. Defaults to medium.
        due_date: Optional ISO date/datetime, e.g. 2026-06-20 or 2026-06-20T15:00.

    Returns:
        JSON containing the created ``task`` and a confirmation ``message``.
    """

    user_id = _require_user()
    try:
        priority_enum = _coerce_priority(priority) or TaskPriority.medium
        due = _parse_due_date(due_date)
    except ValueError as exc:
        return _error(str(exc))

    async with session_scope() as session:
        data = TaskCreate(
            title=title,
            description=description,
            priority=priority_enum,
            due_date=due,
        )
        task = await task_service.create_task(session, data, user_id=user_id)
        return json.dumps(
            {"task": task.to_dict(), "message": f"Created task #{task.id}."},
            default=str,
        )


@tool
@safe_tool
async def update_task(
    task_id: int,
    status: str | None = None,
    priority: str | None = None,
    title: str | None = None,
    description: str | None = None,
    due_date: str | None = None,
    tags: list[str] | None = None,
) -> str:
    """Update fields on an existing task.

    Args:
        task_id: The id of the task to update (required).
        status: New status. One of: todo, in_progress, done.
        priority: New priority. One of: low, medium, high, urgent.
        title: New title.
        description: New description text. Pass an empty string to clear it.
        due_date: New due date in ISO format, e.g. 2026-06-20 or 2026-06-20T15:00.
        tags: Replacement tag list. Pass an empty list to remove all tags.

    Returns:
        JSON containing the updated ``task``, or an ``error`` message.
    """

    user_id = _require_user()
    try:
        status_enum = _coerce_status(status)
        priority_enum = _coerce_priority(priority)
        due = _parse_due_date(due_date)
    except ValueError as exc:
        return _error(str(exc))

    updates: dict[str, object] = {}
    if status_enum is not None:
        updates["status"] = status_enum
    if priority_enum is not None:
        updates["priority"] = priority_enum
    if title is not None:
        updates["title"] = title
    if description is not None:
        updates["description"] = description
    if due_date is not None:
        updates["due_date"] = due
    if tags is not None:
        updates["tags"] = tags

    if not updates:
        return _error("No fields to update were provided.")

    async with session_scope() as session:
        task = await task_service.update_task(
            session, task_id, TaskUpdate(**updates), user_id=user_id
        )
        if task is None:
            return _error(f"Task #{task_id} not found.")
        return json.dumps(
            {"task": task.to_dict(), "message": f"Updated task #{task_id}."},
            default=str,
        )


@tool
@safe_tool
async def delete_task(task_id: int) -> str:
    """Permanently delete a task from the database.

    Args:
        task_id: The id of the task to delete (required).

    Returns:
        JSON confirming deletion with the deleted task's ``id`` and ``title``,
        or an ``error`` message if the task was not found.
    """

    user_id = _require_user()
    async with session_scope() as session:
        task = await task_service.get_task(session, task_id, user_id=user_id)
        if task is None:
            return _error(f"Task #{task_id} not found.")
        title = task.title
        await task_service.delete_task(session, task_id, user_id=user_id)
        return json.dumps(
            {
                "deleted": True,
                "task_id": task_id,
                "title": title,
                "message": f"Deleted task #{task_id}: \"{title}\".",
            }
        )


@tool
@safe_tool
async def prioritize_tasks(by: str = "due_date", limit: int = 10) -> str:
    """Rank the user's incomplete tasks and return the most important ones.

    Args:
        by: Ranking criterion. One of: due_date (soonest first), priority
            (most urgent first), created_at (oldest first). Defaults to due_date.
        limit: Maximum number of tasks to return (1-10, defaults to 10).

    Returns:
        JSON with the ranking field ``by``, the ``count`` and a ``tasks`` array
        of at most 10 incomplete tasks in priority order.
    """

    user_id = _require_user()
    criterion = by if by in _PRIORITIZE_FIELDS else "due_date"
    try:
        capped = max(1, min(int(limit), 10))
    except (TypeError, ValueError):
        capped = 10

    async with session_scope() as session:
        tasks = await task_service.prioritize_tasks(
            session, user_id=user_id, by=criterion, limit=capped
        )
        return json.dumps(
            {"by": criterion, "count": len(tasks), "tasks": [t.to_dict() for t in tasks]},
            default=str,
        )


@tool
@safe_tool
async def summarize_tasks() -> str:
    """Summarize the user's tasks.

    Returns:
        JSON with the ``total`` count, counts ``by_status`` and ``by_priority``,
        and the next three open tasks by due date under ``upcoming``.
    """

    user_id = _require_user()
    async with session_scope() as session:
        summary = await task_service.summarize(session, user_id=user_id)
        return json.dumps(summary, default=str)


# Registered tool set, bound to the LLM and used by the LangGraph ToolNode.
TOOLS = [search_tasks, create_task, update_task, delete_task, prioritize_tasks, summarize_tasks]
