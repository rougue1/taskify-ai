"""CRUD endpoint tests for the tasks API."""

from __future__ import annotations


async def test_create_and_get_task(client):
    response = await client.post("/api/v1/tasks", json={"title": "Test task", "priority": "urgent"})
    assert response.status_code == 201
    created = response.json()
    assert created["id"]
    assert created["title"] == "Test task"
    assert created["priority"] == "urgent"
    assert created["status"] == "todo"
    assert created["created_at"]

    fetched = await client.get(f"/api/v1/tasks/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Test task"


async def test_list_and_filter_tasks(client):
    await client.post("/api/v1/tasks", json={"title": "A", "status": "todo", "priority": "low"})
    await client.post("/api/v1/tasks", json={"title": "B", "status": "done", "priority": "high"})

    all_tasks = await client.get("/api/v1/tasks")
    assert all_tasks.status_code == 200
    assert len(all_tasks.json()) == 2

    done = await client.get("/api/v1/tasks", params={"status": "done"})
    assert len(done.json()) == 1
    assert done.json()[0]["title"] == "B"

    high = await client.get("/api/v1/tasks", params={"priority": "high"})
    assert len(high.json()) == 1
    assert high.json()[0]["title"] == "B"


async def test_partial_update_task(client):
    created = await client.post("/api/v1/tasks", json={"title": "Old title"})
    task_id = created.json()["id"]

    patched = await client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"status": "in_progress", "title": "New title"},
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["status"] == "in_progress"
    assert body["title"] == "New title"


async def test_delete_task(client):
    created = await client.post("/api/v1/tasks", json={"title": "Delete me"})
    task_id = created.json()["id"]

    deleted = await client.delete(f"/api/v1/tasks/{task_id}")
    assert deleted.status_code == 204

    missing = await client.get(f"/api/v1/tasks/{task_id}")
    assert missing.status_code == 404


async def test_create_validation_rejects_empty_title(client):
    response = await client.post("/api/v1/tasks", json={"title": ""})
    assert response.status_code == 422


async def test_get_missing_task_returns_404(client):
    response = await client.get("/api/v1/tasks/999999")
    assert response.status_code == 404


async def test_update_missing_task_returns_404(client):
    response = await client.patch("/api/v1/tasks/999999", json={"status": "done"})
    assert response.status_code == 404
