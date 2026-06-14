"""LangGraph tools the agent can call.

Each tool is a real, async ``@tool`` that performs database work through the
shared service layer. Tools return JSON strings so that the value placed on the
resulting ``ToolMessage`` is always clean, unambiguous text for the model.
"""

from __future__ import annotations

import json
from datetime import datetime

from langchain_core.tools import tool

from app.database import session_scope
from app.models.task import TaskPriority, TaskStatus
from app.schemas.task import TaskCreate, TaskUpdate
from app.services import task_service

_STATUS_VALUES = [s.value for s in TaskStatus]
_PRIORITY_VALUES = [p.value for p in TaskPriority]


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


@tool
async def search_tasks(query: str, status: str | None = None, priority: str | None = None) -> str:
    """Search the user's tasks by text across the title and description.

    Args:
        query: Free-text search string. Pass an empty string to list everything.
        status: Optional status filter. One of: todo, in_progress, done.
        priority: Optional priority filter. One of: low, medium, high, urgent.

    Returns:
        JSON with the match ``count`` and a ``tasks`` array.
    """

    try:
        status_enum = _coerce_status(status)
        priority_enum = _coerce_priority(priority)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    async with session_scope() as session:
        tasks = await task_service.search_tasks(
            session, query or "", status=status_enum, priority=priority_enum
        )
        return json.dumps(
            {"count": len(tasks), "tasks": [t.to_dict() for t in tasks]},
            default=str,
        )


@tool
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

    try:
        priority_enum = _coerce_priority(priority) or TaskPriority.medium
        due = _parse_due_date(due_date)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    async with session_scope() as session:
        data = TaskCreate(
            title=title,
            description=description,
            priority=priority_enum,
            due_date=due,
        )
        task = await task_service.create_task(session, data)
        return json.dumps(
            {"task": task.to_dict(), "message": f"Created task #{task.id}."},
            default=str,
        )


@tool
async def update_task(
    task_id: int,
    status: str | None = None,
    priority: str | None = None,
    title: str | None = None,
) -> str:
    """Update fields on an existing task.

    Args:
        task_id: The id of the task to update (required).
        status: New status. One of: todo, in_progress, done.
        priority: New priority. One of: low, medium, high, urgent.
        title: New title.

    Returns:
        JSON containing the updated ``task``, or an ``error`` message.
    """

    try:
        status_enum = _coerce_status(status)
        priority_enum = _coerce_priority(priority)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    updates: dict[str, object] = {}
    if status_enum is not None:
        updates["status"] = status_enum
    if priority_enum is not None:
        updates["priority"] = priority_enum
    if title is not None:
        updates["title"] = title

    if not updates:
        return json.dumps({"error": "No fields to update were provided."})

    async with session_scope() as session:
        task = await task_service.update_task(session, task_id, TaskUpdate(**updates))
        if task is None:
            return json.dumps({"error": f"Task #{task_id} not found."})
        return json.dumps(
            {"task": task.to_dict(), "message": f"Updated task #{task_id}."},
            default=str,
        )


@tool
async def summarize_tasks() -> str:
    """Summarize the user's tasks.

    Returns:
        JSON with the ``total`` count, counts ``by_status`` and ``by_priority``,
        and the next three open tasks by due date under ``upcoming``.
    """

    async with session_scope() as session:
        summary = await task_service.summarize(session)
        return json.dumps(summary, default=str)


# Registered tool set, bound to the LLM and used by the LangGraph ToolNode.
TOOLS = [search_tasks, create_task, update_task, summarize_tasks]
