"""Unit tests for the LangGraph agent tools.

These exercise the tools directly (no LLM involved) to prove they perform real
database work against the patched test session, scoped to the user bound in the
request context.
"""

from __future__ import annotations

import json

from app.agent.context import user_context
from app.agent.tools import (
    create_task,
    prioritize_tasks,
    search_tasks,
    summarize_tasks,
    update_task,
)


async def test_create_task_tool(agent_user, session_factory):
    with user_context(agent_user):
        result = json.loads(await create_task.ainvoke({"title": "Write tests", "priority": "high"}))
    assert result["task"]["title"] == "Write tests"
    assert result["task"]["priority"] == "high"
    assert result["task"]["status"] == "todo"
    assert result["task"]["user_id"] == agent_user


async def test_create_task_tool_invalid_priority(agent_user, session_factory):
    with user_context(agent_user):
        result = json.loads(await create_task.ainvoke({"title": "Bad", "priority": "nope"}))
    assert "error" in result


async def test_search_tasks_tool(agent_user, session_factory):
    with user_context(agent_user):
        await create_task.ainvoke({"title": "Buy milk", "description": "from the store"})
        await create_task.ainvoke({"title": "Call dentist"})

        found = json.loads(await search_tasks.ainvoke({"query": "milk"}))
        assert found["count"] == 1
        assert found["tasks"][0]["title"] == "Buy milk"

        everything = json.loads(await search_tasks.ainvoke({"query": ""}))
        assert everything["count"] == 2


async def test_update_task_tool(agent_user, session_factory):
    with user_context(agent_user):
        created = json.loads(await create_task.ainvoke({"title": "Draft"}))
        task_id = created["task"]["id"]

        updated = json.loads(await update_task.ainvoke({"task_id": task_id, "status": "done"}))
    assert updated["task"]["status"] == "done"


async def test_update_task_tool_invalid_status(agent_user, session_factory):
    with user_context(agent_user):
        created = json.loads(await create_task.ainvoke({"title": "X"}))
        task_id = created["task"]["id"]
        result = json.loads(await update_task.ainvoke({"task_id": task_id, "status": "nope"}))
    assert "error" in result


async def test_update_task_tool_missing(agent_user, session_factory):
    with user_context(agent_user):
        result = json.loads(await update_task.ainvoke({"task_id": 123456, "status": "done"}))
    assert "error" in result


async def test_update_task_tool_no_fields_returns_error(agent_user, session_factory):
    with user_context(agent_user):
        created = json.loads(await create_task.ainvoke({"title": "Y"}))
        task_id = created["task"]["id"]
        result = json.loads(await update_task.ainvoke({"task_id": task_id}))
    assert "error" in result


async def test_summarize_tasks_tool(agent_user, session_factory):
    with user_context(agent_user):
        await create_task.ainvoke({"title": "T1", "priority": "low"})
        await create_task.ainvoke({"title": "T2", "priority": "urgent"})
        summary = json.loads(await summarize_tasks.ainvoke({}))
    assert summary["total"] == 2
    assert summary["by_priority"]["urgent"] == 1
    assert summary["by_priority"]["low"] == 1
    assert summary["by_status"]["todo"] == 2


async def test_prioritize_tasks_tool_by_due_date(agent_user, session_factory):
    with user_context(agent_user):
        await create_task.ainvoke({"title": "Later", "due_date": "2026-12-31"})
        await create_task.ainvoke({"title": "Sooner", "due_date": "2026-06-20"})
        await create_task.ainvoke({"title": "Undated"})
        result = json.loads(await prioritize_tasks.ainvoke({"by": "due_date"}))

    titles = [task["title"] for task in result["tasks"]]
    assert result["by"] == "due_date"
    assert titles[0] == "Sooner"
    assert titles[1] == "Later"
    assert titles[-1] == "Undated"  # undated tasks rank last


async def test_prioritize_tasks_tool_excludes_done(agent_user, session_factory):
    with user_context(agent_user):
        created = json.loads(await create_task.ainvoke({"title": "Finished"}))
        await update_task.ainvoke({"task_id": created["task"]["id"], "status": "done"})
        await create_task.ainvoke({"title": "Open"})
        result = json.loads(await prioritize_tasks.ainvoke({"by": "priority"}))

    titles = [task["title"] for task in result["tasks"]]
    assert "Finished" not in titles
    assert "Open" in titles


async def test_prioritize_tasks_tool_caps_at_ten(agent_user, session_factory):
    with user_context(agent_user):
        for index in range(15):
            await create_task.ainvoke({"title": f"Task {index}"})
        result = json.loads(await prioritize_tasks.ainvoke({"by": "created_at", "limit": 50}))
    assert result["count"] == 10


async def test_tool_without_user_context_returns_error(session_factory):
    """A tool invoked with no bound user must report an error, not raise."""

    result = json.loads(await create_task.ainvoke({"title": "Orphan"}))
    assert "error" in result


async def test_tools_are_scoped_to_the_current_user(session_factory):
    """Tasks created under one user are invisible to another."""

    with user_context(1):
        await create_task.ainvoke({"title": "User one task"})
        mine = json.loads(await search_tasks.ainvoke({"query": ""}))
        assert mine["count"] == 1

    with user_context(2):
        theirs = json.loads(await search_tasks.ainvoke({"query": ""}))
        assert theirs["count"] == 0
