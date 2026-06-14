"""Unit tests for the LangGraph agent tools.

These exercise the tools directly (no LLM involved) to prove they perform real
database work against the patched test session.
"""

from __future__ import annotations

import json

from app.agent.tools import (
    create_task,
    search_tasks,
    summarize_tasks,
    update_task,
)


async def test_create_task_tool(session_factory):
    result = json.loads(await create_task.ainvoke({"title": "Write tests", "priority": "high"}))
    assert result["task"]["title"] == "Write tests"
    assert result["task"]["priority"] == "high"
    assert result["task"]["status"] == "todo"


async def test_create_task_tool_invalid_priority(session_factory):
    result = json.loads(await create_task.ainvoke({"title": "Bad", "priority": "nope"}))
    assert "error" in result


async def test_search_tasks_tool(session_factory):
    await create_task.ainvoke({"title": "Buy milk", "description": "from the store"})
    await create_task.ainvoke({"title": "Call dentist"})

    found = json.loads(await search_tasks.ainvoke({"query": "milk"}))
    assert found["count"] == 1
    assert found["tasks"][0]["title"] == "Buy milk"

    everything = json.loads(await search_tasks.ainvoke({"query": ""}))
    assert everything["count"] == 2


async def test_update_task_tool(session_factory):
    created = json.loads(await create_task.ainvoke({"title": "Draft"}))
    task_id = created["task"]["id"]

    updated = json.loads(await update_task.ainvoke({"task_id": task_id, "status": "done"}))
    assert updated["task"]["status"] == "done"


async def test_update_task_tool_invalid_status(session_factory):
    created = json.loads(await create_task.ainvoke({"title": "X"}))
    task_id = created["task"]["id"]

    result = json.loads(await update_task.ainvoke({"task_id": task_id, "status": "nope"}))
    assert "error" in result


async def test_update_task_tool_missing(session_factory):
    result = json.loads(await update_task.ainvoke({"task_id": 123456, "status": "done"}))
    assert "error" in result


async def test_summarize_tasks_tool(session_factory):
    await create_task.ainvoke({"title": "T1", "priority": "low"})
    await create_task.ainvoke({"title": "T2", "priority": "urgent"})

    summary = json.loads(await summarize_tasks.ainvoke({}))
    assert summary["total"] == 2
    assert summary["by_priority"]["urgent"] == 1
    assert summary["by_priority"]["low"] == 1
    assert summary["by_status"]["todo"] == 2
