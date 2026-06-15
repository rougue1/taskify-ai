"""Tests for registration, login, tokens and per-user data isolation."""

from __future__ import annotations

from tests.conftest import auth_header, register_user


async def test_register_returns_token_pair(client):
    response = await client.post(
        "/api/v1/auth/register", json={"email": "new@test.local", "password": "password123"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


async def test_register_duplicate_email_conflicts(client):
    await register_user(client, "dupe@test.local")
    response = await client.post(
        "/api/v1/auth/register", json={"email": "dupe@test.local", "password": "password123"}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


async def test_register_rejects_short_password(client):
    response = await client.post(
        "/api/v1/auth/register", json={"email": "weak@test.local", "password": "short"}
    )
    assert response.status_code == 422


async def test_register_rejects_invalid_email(client):
    response = await client.post(
        "/api/v1/auth/register", json={"email": "not-an-email", "password": "password123"}
    )
    assert response.status_code == 422


async def test_login_succeeds_with_correct_password(client):
    await register_user(client, "login@test.local", "password123")
    response = await client.post(
        "/api/v1/auth/login", json={"email": "login@test.local", "password": "password123"}
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_login_wrong_password_unauthorized(client):
    await register_user(client, "wrong@test.local", "password123")
    response = await client.post(
        "/api/v1/auth/login", json={"email": "wrong@test.local", "password": "nope-wrong"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_login_unknown_email_unauthorized(client):
    response = await client.post(
        "/api/v1/auth/login", json={"email": "ghost@test.local", "password": "password123"}
    )
    assert response.status_code == 401


async def test_email_is_normalized_case_insensitively(client):
    await register_user(client, "Mixed@Test.Local", "password123")
    response = await client.post(
        "/api/v1/auth/login", json={"email": "mixed@test.local", "password": "password123"}
    )
    assert response.status_code == 200


async def test_me_returns_current_user(client):
    tokens = await register_user(client, "me@test.local")
    response = await client.get("/api/v1/auth/me", headers=auth_header(tokens["access_token"]))
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "me@test.local"
    assert "hashed_password" not in body


async def test_refresh_issues_new_tokens(client):
    tokens = await register_user(client, "refresh@test.local")
    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_refresh_rejects_access_token(client):
    """An access token must not be usable where a refresh token is required."""

    tokens = await register_user(client, "swap@test.local")
    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]}
    )
    assert response.status_code == 401


async def test_refresh_rejects_garbage(client):
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": "not.a.jwt"})
    assert response.status_code == 401


# --- Protected routes ---------------------------------------------------------


async def test_tasks_require_authentication(client):
    assert (await client.get("/api/v1/tasks")).status_code == 401
    assert (await client.post("/api/v1/tasks", json={"title": "x"})).status_code == 401


async def test_agent_requires_authentication(client):
    response = await client.post("/api/v1/agent/chat", json={"message": "hi"})
    assert response.status_code == 401


async def test_health_is_public(client):
    assert (await client.get("/health")).status_code == 200


async def test_invalid_token_rejected(client):
    response = await client.get("/api/v1/tasks", headers=auth_header("garbage.token.value"))
    assert response.status_code == 401


# --- Data isolation -----------------------------------------------------------


async def test_users_cannot_see_each_others_tasks(client):
    alice = await register_user(client, "alice@test.local")
    bob = await register_user(client, "bob@test.local")
    alice_headers = auth_header(alice["access_token"])
    bob_headers = auth_header(bob["access_token"])

    created = await client.post(
        "/api/v1/tasks", json={"title": "Alice secret"}, headers=alice_headers
    )
    alice_task_id = created.json()["id"]

    # Bob's list is empty and he cannot read, update or delete Alice's task.
    bob_list = await client.get("/api/v1/tasks", headers=bob_headers)
    assert bob_list.json()["total"] == 0

    assert (await client.get(f"/api/v1/tasks/{alice_task_id}", headers=bob_headers)).status_code == 404
    assert (
        await client.patch(
            f"/api/v1/tasks/{alice_task_id}", json={"title": "hijack"}, headers=bob_headers
        )
    ).status_code == 404
    assert (
        await client.delete(f"/api/v1/tasks/{alice_task_id}", headers=bob_headers)
    ).status_code == 404

    # Alice still sees her own task intact.
    alice_list = await client.get("/api/v1/tasks", headers=alice_headers)
    assert alice_list.json()["total"] == 1
    assert alice_list.json()["items"][0]["title"] == "Alice secret"
