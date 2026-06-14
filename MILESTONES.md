# Taskify — Development Roadmap

Taskify ships in small, verifiable milestones. Each milestone has a version tag,
a focused goal, a checklist of work, and the **git tag** cut on completion.

> Status legend: ✅ done · 🚧 in progress · ⬜ planned

---

## ✅ v0.1 — Scaffold

**Goal:** A production-shaped, end-to-end foundation that runs locally.

- Backend: FastAPI app, async SQLAlchemy 2.0, Alembic migration for the `tasks`
  table, Pydantic v2 schemas, service layer.
- REST CRUD endpoints under `/api/v1/tasks` with status/priority filters.
- LangGraph agent (`agent` + `ToolNode`) wired to Ollama with four real,
  DB-backed tools and the `/api/v1/agent/chat` endpoint.
- `/health` endpoint with live Ollama connectivity check.
- Frontend: Next.js 15 (App Router) + Tailwind v4 + shadcn/ui, Zustand store,
  typed API client, task dashboard (list / card / form / filters), collapsible
  AI chat panel, header with theme toggle + connectivity dot.
- Tests (pytest) for CRUD + agent tools; ruff + ESLint; GitHub Actions CI.

**Tag:** `git tag v0.1-scaffold`

---

## ⬜ v0.2 — Core CRUD UI + REST API

**Goal:** Harden the CRUD experience into a polished, complete product surface.

- Optimistic updates and toast notifications for every mutation.
- Inline editing, sorting, and combined status + priority filtering in the UI.
- Pagination / infinite scroll on the list endpoint.
- Tags and due-date editing in the task form.
- Expanded endpoint validation and error responses; richer test coverage.

**Tag:** `git tag v0.2-crud`

---

## ⬜ v0.3 — LangGraph Agent + Tool Calling

**Goal:** Deepen the agent so it reliably searches, creates and prioritizes tasks.

- Robust tool schemas and argument validation; graceful tool-error recovery.
- Prioritization tool and smarter multi-step tool plans.
- Conversation memory within a session; recursion/step limits.
- Agent evaluation harness (golden prompts → expected tool calls).

**Tag:** `git tag v0.3-agent`

---

## ⬜ v0.4 — SSE Streaming

**Goal:** Stream agent tokens to the chat UI in real time.

- Convert `/api/v1/agent/chat` to Server-Sent Events (see the `TODO v0.4`
  markers in `routers/agent.py` and the frontend store/`ChatPanel`).
- Stream tokens + tool-call events; render progressive output.
- Cancellation / abort support from the client.

**Tag:** `git tag v0.4-streaming`

---

## ⬜ v0.5 — JWT Authentication + User-Scoped Tasks

**Goal:** Multi-user support with secure, per-user data.

- User model, registration/login, hashed passwords.
- JWT access/refresh tokens; auth dependency on protected routes.
- `user_id` foreign key on tasks; all queries + tools scoped to the current user.
- Frontend auth flow and protected routes.

**Tag:** `git tag v0.5-auth`

---

## ⬜ v0.6 — Richer Tools

**Goal:** More capable, real-world task operations.

- Natural-language due-date parsing (replacing the v0.1 best-effort parser).
- Bulk operations (complete/delete/retag many tasks at once).
- Calendar view and recurring tasks.
- Additional agent tools exposing the above.

**Tag:** `git tag v0.6-tools`

---

## ⬜ v0.7 — RAG over Tasks

**Goal:** Semantic search and retrieval-augmented answers about tasks.

- Migrate to PostgreSQL + `pgvector`.
- Embed tasks with `nomic-embed-text`; store and index vectors.
- Retrieval tool so the agent can answer questions grounded in task content.

**Tag:** `git tag v0.7-rag`

---

## ⬜ v0.8 — Docker Compose + Production Deployment

**Goal:** One-command, production-ready deployment.

- Dockerfiles for backend and frontend; `docker compose` for app + Postgres + Ollama.
- Production configuration, healthchecks, and migrations on deploy.
- Reverse proxy, environment hardening, and deployment docs.

**Tag:** `git tag v0.8-deploy`
