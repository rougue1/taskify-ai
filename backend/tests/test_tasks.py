"""CRUD, pagination, sorting and error-shape tests for the tasks API."""

from __future__ import annotations


async def test_create_and_get_task(auth_client):
    response = await auth_client.post(
        "/api/v1/tasks", json={"title": "Test task", "priority": "urgent"}
    )
    assert response.status_code == 201
    created = response.json()
    assert created["id"]
    assert created["title"] == "Test task"
    assert created["priority"] == "urgent"
    assert created["status"] == "todo"
    assert created["created_at"]
    assert created["user_id"]

    fetched = await auth_client.get(f"/api/v1/tasks/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Test task"


async def test_list_and_filter_tasks(auth_client):
    await auth_client.post("/api/v1/tasks", json={"title": "A", "status": "todo", "priority": "low"})
    await auth_client.post(
        "/api/v1/tasks", json={"title": "B", "status": "done", "priority": "high"}
    )

    all_tasks = await auth_client.get("/api/v1/tasks")
    assert all_tasks.status_code == 200
    body = all_tasks.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["pages"] == 1

    done = await auth_client.get("/api/v1/tasks", params={"status": "done"})
    assert done.json()["total"] == 1
    assert done.json()["items"][0]["title"] == "B"

    high = await auth_client.get("/api/v1/tasks", params={"priority": "high"})
    assert high.json()["total"] == 1
    assert high.json()["items"][0]["title"] == "B"


async def test_partial_update_task(auth_client):
    created = await auth_client.post("/api/v1/tasks", json={"title": "Old title"})
    task_id = created.json()["id"]

    patched = await auth_client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"status": "in_progress", "title": "New title"},
    )
    assert patched.status_code == 200
    updated = patched.json()
    assert updated["status"] == "in_progress"
    assert updated["title"] == "New title"


async def test_delete_task(auth_client):
    created = await auth_client.post("/api/v1/tasks", json={"title": "Delete me"})
    task_id = created.json()["id"]

    deleted = await auth_client.delete(f"/api/v1/tasks/{task_id}")
    assert deleted.status_code == 204

    missing = await auth_client.get(f"/api/v1/tasks/{task_id}")
    assert missing.status_code == 404


async def test_create_validation_rejects_empty_title(auth_client):
    response = await auth_client.post("/api/v1/tasks", json={"title": ""})
    assert response.status_code == 422


async def test_get_missing_task_returns_404(auth_client):
    response = await auth_client.get("/api/v1/tasks/999999")
    assert response.status_code == 404


async def test_update_missing_task_returns_404(auth_client):
    response = await auth_client.patch("/api/v1/tasks/999999", json={"status": "done"})
    assert response.status_code == 404


# --- Tags ---------------------------------------------------------------------


async def test_tags_persist_on_create_and_update(auth_client):
    created = await auth_client.post(
        "/api/v1/tasks", json={"title": "Tagged", "tags": ["work", "urgent"]}
    )
    assert created.status_code == 201
    assert created.json()["tags"] == ["work", "urgent"]

    task_id = created.json()["id"]
    fetched = await auth_client.get(f"/api/v1/tasks/{task_id}")
    assert fetched.json()["tags"] == ["work", "urgent"]

    patched = await auth_client.patch(f"/api/v1/tasks/{task_id}", json={"tags": ["home"]})
    assert patched.json()["tags"] == ["home"]


async def test_missing_tags_serialize_as_empty_array(auth_client):
    created = await auth_client.post("/api/v1/tasks", json={"title": "No tags"})
    assert created.json()["tags"] == []


# --- Pagination ---------------------------------------------------------------


async def test_pagination_pages_and_metadata(auth_client):
    for index in range(5):
        await auth_client.post("/api/v1/tasks", json={"title": f"Task {index}"})

    first = await auth_client.get("/api/v1/tasks", params={"page": 1, "page_size": 2})
    body = first.json()
    assert body["total"] == 5
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["pages"] == 3
    assert len(body["items"]) == 2

    last = await auth_client.get("/api/v1/tasks", params={"page": 3, "page_size": 2})
    assert len(last.json()["items"]) == 1


async def test_pagination_rejects_invalid_params(auth_client):
    assert (await auth_client.get("/api/v1/tasks", params={"page": 0})).status_code == 422
    assert (await auth_client.get("/api/v1/tasks", params={"page_size": 0})).status_code == 422
    assert (await auth_client.get("/api/v1/tasks", params={"page_size": 9999})).status_code == 422


# --- Sorting ------------------------------------------------------------------


async def test_sort_by_title_ascending(auth_client):
    for title in ("Banana", "apple", "Cherry"):
        await auth_client.post("/api/v1/tasks", json={"title": title})

    response = await auth_client.get(
        "/api/v1/tasks", params={"sort_by": "title", "sort_order": "asc"}
    )
    titles = [item["title"] for item in response.json()["items"]]
    assert titles == ["apple", "Banana", "Cherry"]  # case-insensitive ordering


async def test_sort_by_priority_is_semantic_not_alphabetical(auth_client):
    for priority in ("low", "urgent", "medium", "high"):
        await auth_client.post("/api/v1/tasks", json={"title": priority, "priority": priority})

    response = await auth_client.get(
        "/api/v1/tasks", params={"sort_by": "priority", "sort_order": "desc"}
    )
    priorities = [item["priority"] for item in response.json()["items"]]
    assert priorities == ["urgent", "high", "medium", "low"]


async def test_sort_rejects_unknown_field(auth_client):
    response = await auth_client.get("/api/v1/tasks", params={"sort_by": "bogus"})
    assert response.status_code == 422


# --- Error shapes -------------------------------------------------------------


async def test_404_has_structured_error_envelope(auth_client):
    response = await auth_client.get("/api/v1/tasks/999999")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "Task not found"


async def test_validation_error_has_field_details(auth_client):
    response = await auth_client.post("/api/v1/tasks", json={"title": ""})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert isinstance(body["error"]["details"], list)
    assert any(detail["field"] == "title" for detail in body["error"]["details"])
