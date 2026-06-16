# Taskify

> A local, AI-powered task manager with a **Kanban board** and an **agentic
> assistant**. A locally-running model (via [Ollama](https://ollama.com)) understands
> natural language and calls real tools — backed by a
> [LangGraph](https://langchain-ai.github.io/langgraph/) agent — to create, update,
> prioritize, bulk-edit and **semantically search** your tasks.

![Taskify screenshot placeholder](./docs/screenshot.png)

> _Screenshot placeholder — add `docs/screenshot.png` once the UI is captured._

---

## Features

- ✅ **Kanban board** — three columns (To Do / In Progress / Done) with drag &
  drop (`@dnd-kit`), live drop placeholders, per-column counts, and hover quick
  actions (✓ complete, edit, delete) on each card.
- ✅ **Task detail panel** — click a card to slide in a side panel with inline
  status / priority / due-date / tag editing (saved on change), timestamps, and
  edit/delete actions. Closes on backdrop click or `Esc`.
- ✅ **AI chat agent** — LangGraph + Ollama assistant that calls real,
  DB-backed tools, with SSE token streaming, a live reasoning panel, and
  per-session conversation memory.
- ✅ **Natural-language due dates** — "tomorrow", "next Friday", "in 3 days",
  "end of next week", "next Monday at 9am".
- ✅ **Bulk operations via the agent** — "mark all urgent tasks done", "set all
  overdue tasks to urgent", "delete all completed tasks".
- ✅ **Semantic search (RAG)** — pgvector + `nomic-embed-text` embeddings let
  the agent find tasks by meaning, not just keywords.
- ✅ **Auth & isolation** — JWT access/refresh tokens; every task and tool is
  scoped to the current user.
- ✅ **Dockerized** — one command brings up Postgres (pgvector), Ollama, the API
  and the web app, with health checks and migrations on startup.
- ✅ **Dark mode** across the whole UI.

---

## Tech stack

| Layer     | Technology |
|-----------|------------|
| Frontend  | Next.js 15 (App Router, TypeScript), Tailwind CSS v4, shadcn/ui, Zustand, `@dnd-kit` |
| Backend   | FastAPI (async), SQLAlchemy 2.0 (async), Alembic, Pydantic v2 |
| Database  | PostgreSQL 16 + `pgvector` (production) · SQLite (zero-dependency local) |
| AI        | Ollama, LangGraph (ToolNode agent), `langchain-ollama`, `nomic-embed-text` embeddings, `dateparser` |
| Infra     | Docker Compose (postgres · ollama · backend · frontend), Makefile |

### Two-model strategy

| Setting              | Default            | Purpose |
|----------------------|--------------------|---------|
| `OLLAMA_TOOL_MODEL`  | `qwen3.5:9b`       | The **agent** model — structured tool calling for the chat assistant. |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | **Embeddings** for semantic search over tasks. |
| `OLLAMA_CODE_MODEL`  | `qwen2.5-coder:14b`| Reserved for code/reasoning tasks. |

---

## Architecture

```
                         ┌─────────────────────────────┐
   Browser  ────────────▶│  frontend (Next.js :3000)   │
   localhost:3000        │  • Kanban board + detail UI │
                         │  • /api/v1/* proxy ─────────┼────────┐
                         │  • /api/agent/stream (SSE)  │        │
                         └─────────────────────────────┘        │
                                                                ▼
                         ┌─────────────────────────────┐   ┌──────────────────┐
                         │  backend (FastAPI :8000)     │──▶│ ollama  :11434   │
                         │  • REST CRUD + bulk + search │   │ qwen3.5 / nomic  │
                         │  • LangGraph agent + tools   │◀──│ chat + embeddings│
                         │  • JWT auth, migrations      │   └──────────────────┘
                         └───────────────┬─────────────┘
                                         │ asyncpg
                                         ▼
                         ┌─────────────────────────────┐
                         │  postgres :5432 (pgvector)   │
                         │  tasks.embedding vector(768) │
                         └─────────────────────────────┘
```

The browser only ever talks to the Next.js origin: `/api/v1/*` is **proxied** to
the backend and the SSE chat stream goes through a dedicated route handler (so
events aren't buffered). The agent's tools call the **same service layer** as the
REST API, so task logic lives in exactly one place.

---

## Prerequisites

- **[Docker](https://docs.docker.com/get-docker/)** + Docker Compose v2
  (recommended path — brings up everything).
- Optional: an **NVIDIA GPU** with `nvidia-container-toolkit` for faster Ollama
  (uncomment the GPU block in `docker-compose.yml`). CPU-only works too.

For local development without Docker you'll also want **Python 3.12**,
**Node.js 20+**, and a locally-running **Ollama**.

---

## Quick start (Docker)

```bash
git clone <your-fork-url> taskify && cd taskify

cp .env.example .env          # adjust secrets / models if you like

make dev                      # build + start postgres, ollama, backend, frontend
make pull-models              # (first run) pull the tool + embedding models
make migrate                  # apply DB migrations (also runs on startup)

# open http://localhost:3000
```

`make dev` streams all logs; `Ctrl+C` stops the stack. `make pull-models` can
take a while the first time (it downloads the Ollama models into a volume).

---

## Local development (no Docker, SQLite)

The backend falls back to SQLite, so you can run everything without Postgres —
only semantic search is disabled (it degrades gracefully to an "unavailable"
message).

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # then set DATABASE_URL to the SQLite line for local
uvicorn app.main:app --reload --port 8000

# Frontend (second terminal)
cd frontend
npm install
npm run dev                   # http://localhost:3000
```

Or use the convenience launcher from the repo root: `./start.sh` (starts both,
tails logs, stops both on `Ctrl+C`).

---

## Make targets

| Target             | Description |
|--------------------|-------------|
| `make dev`         | Build and start the full stack with Docker Compose. |
| `make pull-models` | Pull the Ollama tool + embedding models into the `ollama` container. |
| `make migrate`     | Run Alembic migrations inside the backend container. |
| `make logs`        | Tail logs from all services. |
| `make down`        | Stop and remove the stack's containers. |
| `make clean`       | Stop the stack and delete its volumes (**destroys data**). |

---

## Environment variables

The root **`.env`** (see [`.env.example`](./.env.example)) feeds Docker Compose:

| Variable             | Default                  | Description |
|----------------------|--------------------------|-------------|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `taskuser` / `taskpass` / `taskdb` | Postgres credentials; the backend's `DATABASE_URL` is built from these. |
| `JWT_SECRET_KEY`     | `dev-insecure-…`         | JWT signing secret (`openssl rand -hex 32` for real use). |
| `OLLAMA_TOOL_MODEL`  | `qwen3.5:9b`             | Tool-calling agent model. |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text`       | Embedding model for semantic search. |
| `CORS_ORIGINS`       | `["http://localhost:3000"]` | Allowed browser origins. |

For non-Docker runs, the backend reads **`backend/.env`** (see
[`backend/.env.example`](./backend/.env.example)); set `DATABASE_URL` to either
the PostgreSQL or the SQLite line there.

---

## API reference (highlights)

Base URL: `http://localhost:8000`

| Method   | Path                          | Description |
|----------|-------------------------------|-------------|
| `GET`    | `/health`                     | Status plus live `db` and `ollama` connectivity. |
| `GET`    | `/api/v1/tasks`               | List tasks (filter / sort / paginate). |
| `POST`   | `/api/v1/tasks`               | Create a task. |
| `PATCH`  | `/api/v1/tasks/{id}`          | Update a task. |
| `PATCH`  | `/api/v1/tasks/bulk`          | Bulk update a list of task ids. |
| `POST`   | `/api/v1/tasks/semantic-search` | Vector search over the user's tasks. |
| `DELETE` | `/api/v1/tasks/{id}`          | Delete a task. |
| `POST`   | `/api/v1/agent/chat`          | Chat with the agent. |
| `POST`   | `/api/v1/agent/stream`        | Stream a chat turn (SSE). |

Interactive OpenAPI docs: **http://localhost:8000/docs**.

### Agent tools

`search_tasks` · `create_task` · `update_task` · `delete_task` ·
`prioritize_tasks` · `summarize_tasks` · `bulk_update_tasks` ·
`semantic_search_tasks` — all DB-backed and scoped to the current user. Tasks are
referred to by a stable **per-user number** in chat ("Task 1", "Task 2"), never
the global row id.

---

## Testing & quality

```bash
# Backend
cd backend
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q          # CRUD, agent tools, dates, bulk, RAG fallback

# Frontend
cd frontend
npm run lint
npm run build
```

CI runs lint + tests on every push / PR (see `.github/workflows/ci.yml`). See
[MILESTONES.md](./MILESTONES.md) for the development roadmap.
