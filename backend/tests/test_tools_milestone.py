"""Tests for the v0.6/v0.7 milestone: per-user task numbering, natural-language
due dates, bulk operations, and graceful semantic-search degradation.

Tool tests drive the ``@tool`` callables directly (no LLM); REST tests exercise
the new ``/tasks/bulk`` and ``/tasks/semantic-search`` endpoints. Everything runs
on the in-memory SQLite database, where semantic search reports itself
unavailable (it requires PostgreSQL + pgvector).
"""

from __future__ import annotations

import json
from datetime import datetime

from app.agent.context import user_context
from app.agent.tools import (
    bulk_update_tasks,
    create_task,
    search_tasks,
    semantic_search_tasks,
)
from tests.conftest import auth_header, register_user

# --- Per-user task numbering (the bug fix) -----------------------------------


async def test_tasks_are_numbered_per_user_not_by_global_id(agent_user, session_factory):
    """Numbers reflect each user's own task order (1,2,3…), never the row id."""

    with user_context(agent_user):
        await create_task.ainvoke({"title": "First"})
        await create_task.ainvoke({"title": "Second"})
        await create_task.ainvoke({"title": "Third"})
        listing = json.loads(await search_tasks.ainvoke({"query": ""}))

    by_title = {t["title"]: t for t in listing["tasks"]}
    assert by_title["First"]["number"] == 1
    assert by_title["Second"]["number"] == 2
    assert by_title["Third"]["number"] == 3


async def test_create_reports_the_per_user_number(agent_user, session_factory):
    with user_context(agent_user):
        first = json.loads(await create_task.ainvoke({"title": "Alpha"}))
        second = json.loads(await create_task.ainvoke({"title": "Beta"}))
    assert first["task"]["number"] == 1
    assert second["task"]["number"] == 2
    assert "task 2" in second["message"].lower()


async def test_numbering_is_independent_across_users(session_factory):
    """A second user's first task is 'Task 1' even though its global id is higher."""

    with user_context(1):
        await create_task.ainvoke({"title": "U1 task A"})
        await create_task.ainvoke({"title": "U1 task B"})
    with user_context(2):
        created = json.loads(await create_task.ainvoke({"title": "U2 first"}))
        listing = json.loads(await search_tasks.ainvoke({"query": ""}))

    # Global id is 3 (after user 1's two rows) but the per-user number is 1.
    assert created["task"]["id"] == 3
    assert created["task"]["number"] == 1
    assert listing["count"] == 1
    assert listing["tasks"][0]["number"] == 1


# --- Natural-language due dates ----------------------------------------------


async def test_create_task_parses_natural_language_due_date(agent_user, session_factory):
    with user_context(agent_user):
        result = json.loads(
            await create_task.ainvoke({"title": "Plan trip", "due_date": "next Monday"})
        )
    due = result["task"]["due_date"]
    assert due is not None
    assert datetime.fromisoformat(due).weekday() == 0  # Monday


async def test_create_task_still_accepts_iso_due_date(agent_user, session_factory):
    with user_context(agent_user):
        result = json.loads(
            await create_task.ainvoke({"title": "Exact", "due_date": "2026-06-20"})
        )
    assert result["task"]["due_date"].startswith("2026-06-20")


async def test_create_task_unparseable_due_date_errors(agent_user, session_factory):
    with user_context(agent_user):
        result = json.loads(
            await create_task.ainvoke({"title": "Bad date", "due_date": "definitely not a date"})
        )
    assert "error" in result


# --- Bulk operations ----------------------------------------------------------


async def test_bulk_set_status_by_priority(agent_user, session_factory):
    with user_context(agent_user):
        await create_task.ainvoke({"title": "u1", "priority": "urgent"})
        await create_task.ainvoke({"title": "u2", "priority": "urgent"})
        await create_task.ainvoke({"title": "low1", "priority": "low"})

        result = json.loads(
            await bulk_update_tasks.ainvoke(
                {
                    "filter": "priority",
                    "filter_value": "urgent",
                    "action": "set_status",
                    "value": "done",
                }
            )
        )
        assert result["count"] == 2
        assert all(t["status"] == "done" for t in result["tasks"])

        # The low-priority task is untouched.
        remaining = json.loads(await search_tasks.ainvoke({"query": "", "status": "todo"}))
        assert remaining["count"] == 1
        assert remaining["tasks"][0]["title"] == "low1"


async def test_bulk_delete_completed(agent_user, session_factory):
    with user_context(agent_user):
        created = json.loads(await create_task.ainvoke({"title": "finish me"}))
        await create_task.ainvoke({"title": "keep me"})
        # Mark the first done, then bulk-delete everything that is done.
        from app.agent.tools import update_task

        await update_task.ainvoke({"task_id": created["task"]["id"], "status": "done"})

        result = json.loads(
            await bulk_update_tasks.ainvoke(
                {"filter": "status", "filter_value": "done", "action": "delete"}
            )
        )
        assert result["count"] == 1
        leftover = json.loads(await search_tasks.ainvoke({"query": ""}))
        assert leftover["count"] == 1
        assert leftover["tasks"][0]["title"] == "keep me"


async def test_bulk_all_set_priority(agent_user, session_factory):
    with user_context(agent_user):
        await create_task.ainvoke({"title": "a"})
        await create_task.ainvoke({"title": "b"})
        result = json.loads(
            await bulk_update_tasks.ainvoke(
                {"filter": "all", "action": "set_priority", "value": "high"}
            )
        )
    assert result["count"] == 2
    assert all(t["priority"] == "high" for t in result["tasks"])


async def test_bulk_invalid_action_errors(agent_user, session_factory):
    with user_context(agent_user):
        result = json.loads(
            await bulk_update_tasks.ainvoke({"filter": "all", "action": "nuke"})
        )
    assert "error" in result


async def test_bulk_is_scoped_to_current_user(session_factory):
    with user_context(1):
        await create_task.ainvoke({"title": "mine", "priority": "urgent"})
    with user_context(2):
        result = json.loads(
            await bulk_update_tasks.ainvoke(
                {"filter": "all", "action": "set_status", "value": "done"}
            )
        )
    # User 2 has no tasks, so nothing is affected — user 1's task is safe.
    assert result["count"] == 0


# --- Semantic search degrades gracefully on SQLite ---------------------------


async def test_semantic_search_unavailable_on_sqlite(agent_user, session_factory):
    with user_context(agent_user):
        await create_task.ainvoke({"title": "Book flights to Tokyo"})
        result = json.loads(await semantic_search_tasks.ainvoke({"query": "travel"}))
    assert result["available"] is False
    assert result["tasks"] == []


# --- REST endpoints -----------------------------------------------------------


async def test_rest_bulk_update_endpoint(auth_client):
    ids = []
    for title in ("one", "two", "three"):
        resp = await auth_client.post("/api/v1/tasks", json={"title": title})
        ids.append(resp.json()["id"])

    resp = await auth_client.patch(
        "/api/v1/tasks/bulk", json={"ids": ids, "update": {"status": "done"}}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 3
    assert all(task["status"] == "done" for task in body["updated"])


async def test_rest_bulk_only_touches_owned_tasks(client):
    # Two separate users; user B must not be able to bulk-update user A's task.
    a_tokens = await register_user(client, email="a@test.local")
    b_tokens = await register_user(client, email="b@test.local")

    client.headers.update(auth_header(a_tokens["access_token"]))
    a_task = (await client.post("/api/v1/tasks", json={"title": "A owns this"})).json()

    client.headers.update(auth_header(b_tokens["access_token"]))
    resp = await client.patch(
        "/api/v1/tasks/bulk", json={"ids": [a_task["id"]], "update": {"status": "done"}}
    )
    assert resp.status_code == 200
    assert resp.json()["count"] == 0  # nothing of B's matched

    # A's task is unchanged.
    client.headers.update(auth_header(a_tokens["access_token"]))
    fetched = (await client.get(f"/api/v1/tasks/{a_task['id']}")).json()
    assert fetched["status"] == "todo"


async def test_rest_semantic_search_unavailable_on_sqlite(auth_client):
    resp = await auth_client.post(
        "/api/v1/tasks/semantic-search", json={"query": "anything"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["available"] is False
    assert body["items"] == []
