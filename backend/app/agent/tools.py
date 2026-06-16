"""LangGraph tools the agent can call.

Each tool is a real, async ``@tool`` that performs database work through the
shared service layer, scoped to the authenticated user (resolved from the
request context — never an LLM-visible argument). Tools return JSON strings so
the value on the resulting ``ToolMessage`` is always clean, unambiguous text.

Robustness: tools **never raise**. Any failure (validation, missing user,
database error) is caught and returned as a structured ``{"error": ...}`` object
so the agent can read what went wrong and recover instead of crashing the graph.

Task numbering: every task returned to the agent carries a per-user ``number``
(its 1-based position within *this* user's task list, oldest first) in addition
to its global ``id``. The agent refers to tasks by ``number`` when talking to the
user ("Task 1", "Task 2") and uses ``id`` when calling tools — see the system
prompt. This keeps the friendly numbering stable and private to each account.
"""

from __future__ import annotations

import functools
import json
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context import get_current_user_id
from app.agent.dates import parse_due_date
from app.database import session_scope
from app.models.task import Task, TaskPriority, TaskStatus
from app.schemas.task import TaskCreate, TaskUpdate
from app.services import embedding, task_service

_STATUS_VALUES = [s.value for s in TaskStatus]
_PRIORITY_VALUES = [p.value for p in TaskPriority]
_PRIORITIZE_FIELDS = {"due_date", "priority", "created_at"}
_BULK_FILTERS = {"all", "status", "priority", "tag", "overdue"}
_BULK_ACTIONS = {"set_status", "set_priority", "delete"}


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


def _require_user() -> int:
    """Return the current user id or raise so ``safe_tool`` reports it cleanly."""

    user_id = get_current_user_id()
    if user_id is None:
        raise RuntimeError("No authenticated user is bound to this request.")
    return user_id


async def _serialize(
    session: AsyncSession, user_id: int, tasks: Sequence[Task]
) -> list[dict[str, Any]]:
    """Serialize tasks for the agent, tagging each with its per-user ``number``."""

    numbers = await task_service.user_task_numbers(session, user_id=user_id)
    return [{**task.to_dict(), "number": numbers.get(task.id)} for task in tasks]


@tool
@safe_tool
async def search_tasks(query: str, status: str | None = None, priority: str | None = None) -> str:
    """Search the user's tasks by text across the title and description.

    Args:
        query: Free-text search string. Pass an empty string to list everything.
        status: Optional status filter. One of: todo, in_progress, done.
        priority: Optional priority filter. One of: low, medium, high, urgent.

    Returns:
        JSON with the match ``count`` and a ``tasks`` array. Each task includes a
        per-user ``number`` (use it when referring to the task to the user) and a
        global ``id`` (use it when calling other tools).
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
        serialized = await _serialize(session, user_id, tasks)
        return json.dumps({"count": len(serialized), "tasks": serialized}, default=str)


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
        due_date: Optional due date. Accepts ISO (2026-06-20 or 2026-06-20T15:00)
            or natural language like "tomorrow", "next Friday" or "in 3 days".

    Returns:
        JSON containing the created ``task`` (with its per-user ``number``) and a
        confirmation ``message``.
    """

    user_id = _require_user()
    try:
        priority_enum = _coerce_priority(priority) or TaskPriority.medium
        due = parse_due_date(due_date)
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
        numbers = await task_service.user_task_numbers(session, user_id=user_id)
        number = numbers.get(task.id)
        return json.dumps(
            {
                "task": {**task.to_dict(), "number": number},
                "message": f"Created task {number}: \"{task.title}\".",
            },
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

    ``task_id`` is the task's global ``id`` (from a prior tool result), not its
    per-user display number.

    Args:
        task_id: The id of the task to update (required).
        status: New status. One of: todo, in_progress, done.
        priority: New priority. One of: low, medium, high, urgent.
        title: New title.
        description: New description text. Pass an empty string to clear it.
        due_date: New due date. ISO or natural language (e.g. "next Monday at 9am").
        tags: Replacement tag list. Pass an empty list to remove all tags.

    Returns:
        JSON containing the updated ``task`` (with its per-user ``number``), or an
        ``error`` message.
    """

    user_id = _require_user()
    try:
        status_enum = _coerce_status(status)
        priority_enum = _coerce_priority(priority)
        due = parse_due_date(due_date)
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
        numbers = await task_service.user_task_numbers(session, user_id=user_id)
        number = numbers.get(task.id)
        return json.dumps(
            {
                "task": {**task.to_dict(), "number": number},
                "message": f"Updated task {number}.",
            },
            default=str,
        )


@tool
@safe_tool
async def delete_task(task_id: int) -> str:
    """Permanently delete a task from the database.

    ``task_id`` is the task's global ``id`` (from a prior tool result), not its
    per-user display number.

    Args:
        task_id: The id of the task to delete (required).

    Returns:
        JSON confirming deletion with the deleted task's ``id``, per-user
        ``number`` and ``title``, or an ``error`` message if it was not found.
    """

    user_id = _require_user()
    async with session_scope() as session:
        task = await task_service.get_task(session, task_id, user_id=user_id)
        if task is None:
            return _error(f"Task #{task_id} not found.")
        title = task.title
        # Capture the per-user number *before* deletion shifts the positions.
        numbers = await task_service.user_task_numbers(session, user_id=user_id)
        number = numbers.get(task_id)
        await task_service.delete_task(session, task_id, user_id=user_id)
        return json.dumps(
            {
                "deleted": True,
                "task_id": task_id,
                "number": number,
                "title": title,
                "message": f"Deleted task {number}: \"{title}\".",
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
        (each with its per-user ``number``) of at most 10 incomplete tasks in
        priority order.
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
        serialized = await _serialize(session, user_id, tasks)
        return json.dumps(
            {"by": criterion, "count": len(serialized), "tasks": serialized},
            default=str,
        )


@tool
@safe_tool
async def summarize_tasks() -> str:
    """Summarize the user's tasks.

    Returns:
        JSON with the ``total`` count, counts ``by_status`` and ``by_priority``,
        and the next three open tasks by due date under ``upcoming`` (each with
        its per-user ``number``).
    """

    user_id = _require_user()
    async with session_scope() as session:
        summary = await task_service.summarize(session, user_id=user_id)
        return json.dumps(summary, default=str)


@tool
@safe_tool
async def bulk_update_tasks(
    filter: str,
    action: str,
    filter_value: str | None = None,
    value: str | None = None,
) -> str:
    """Apply one action to many of the user's tasks at once.

    Use this for requests like "mark all urgent tasks as done", "set all overdue
    tasks to urgent priority" or "delete all completed tasks".

    Args:
        filter: Which tasks to act on. One of:
            - "all": every task the user owns.
            - "status": tasks whose status equals ``filter_value`` (todo,
              in_progress, done).
            - "priority": tasks whose priority equals ``filter_value`` (low,
              medium, high, urgent).
            - "tag": tasks carrying the tag named in ``filter_value``.
            - "overdue": open tasks whose due date is in the past.
        action: What to do. One of: set_status, set_priority, delete.
        filter_value: The value the filter matches on (required for status,
            priority and tag filters; ignored for all/overdue).
        value: The new value for the action — a status for set_status, a priority
            for set_priority. Ignored for delete.

    Returns:
        JSON describing the affected tasks (by per-user ``number``) and a
        confirmation ``message``, or an ``error``.
    """

    user_id = _require_user()
    filter_key = (filter or "").strip().lower()
    action_key = (action or "").strip().lower()

    if filter_key not in _BULK_FILTERS:
        return _error(f"Invalid filter '{filter}'. Must be one of: {sorted(_BULK_FILTERS)}.")
    if action_key not in _BULK_ACTIONS:
        return _error(f"Invalid action '{action}'. Must be one of: {sorted(_BULK_ACTIONS)}.")
    if filter_key in {"status", "priority", "tag"} and not filter_value:
        return _error(f"The '{filter_key}' filter requires a filter_value.")

    try:
        if filter_key == "status":
            _coerce_status(filter_value)  # validate the filter value
        elif filter_key == "priority":
            _coerce_priority(filter_value)
        new_status = _coerce_status(value) if action_key == "set_status" else None
        new_priority = _coerce_priority(value) if action_key == "set_priority" else None
    except ValueError as exc:
        return _error(str(exc))

    if action_key == "set_status" and new_status is None:
        return _error("set_status requires a 'value' of: todo, in_progress, or done.")
    if action_key == "set_priority" and new_priority is None:
        return _error("set_priority requires a 'value' of: low, medium, high, or urgent.")

    async with session_scope() as session:
        targets = await task_service.select_for_bulk(
            session, user_id=user_id, filter=filter_key, filter_value=filter_value
        )
        if not targets:
            return json.dumps(
                {"count": 0, "tasks": [], "message": "No tasks matched that filter."}
            )

        # Capture numbers before any deletion renumbers the remaining tasks.
        numbers = await task_service.user_task_numbers(session, user_id=user_id)
        affected_numbers = sorted(n for n in (numbers.get(t.id) for t in targets) if n)
        ids = [t.id for t in targets]

        if action_key == "delete":
            count = await task_service.bulk_delete(session, ids, user_id=user_id)
            return json.dumps(
                {
                    "action": "delete",
                    "count": count,
                    "task_numbers": affected_numbers,
                    "message": f"Deleted {count} task{'s' if count != 1 else ''}.",
                }
            )

        update = TaskUpdate(status=new_status) if new_status else TaskUpdate(priority=new_priority)
        updated = await task_service.bulk_update(session, ids, update, user_id=user_id)
        serialized = await _serialize(session, user_id, updated)
        changed = new_status.value if new_status else new_priority.value  # type: ignore[union-attr]
        field = "status" if new_status else "priority"
        return json.dumps(
            {
                "action": action_key,
                "count": len(updated),
                "tasks": serialized,
                "message": f"Set {field} to {changed} on {len(updated)} task"
                f"{'s' if len(updated) != 1 else ''}.",
            },
            default=str,
        )


@tool
@safe_tool
async def semantic_search_tasks(query: str) -> str:
    """Find the user's tasks by meaning, not just keywords.

    Embeds the query and returns the up to 5 most semantically similar tasks via
    a pgvector cosine-distance search. Prefer this over ``search_tasks`` when the
    user describes a concept ("anything about travel") rather than exact words.

    Returns:
        JSON with the ``tasks`` array (each with its per-user ``number``). If
        semantic search is not configured (no PostgreSQL/pgvector or the embedding
        model is unavailable), returns ``available: false`` with a message — fall
        back to ``search_tasks`` in that case.
    """

    user_id = _require_user()
    async with session_scope() as session:
        results = await embedding.semantic_search(session, user_id=user_id, query=query, limit=5)
        if results is None:
            return json.dumps(
                {
                    "available": False,
                    "tasks": [],
                    "message": (
                        "Semantic search is unavailable (it needs PostgreSQL with "
                        "pgvector and the embedding model). Use search_tasks instead."
                    ),
                }
            )
        serialized = await _serialize(session, user_id, results)
        return json.dumps(
            {"available": True, "count": len(serialized), "tasks": serialized},
            default=str,
        )


# Registered tool set, bound to the LLM and used by the LangGraph ToolNode.
TOOLS = [
    search_tasks,
    create_task,
    update_task,
    delete_task,
    prioritize_tasks,
    summarize_tasks,
    bulk_update_tasks,
    semantic_search_tasks,
]
