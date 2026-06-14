# Taskify

> A local, AI-powered task manager with **agentic tool calling**. A locally-running
> assistant (via [Ollama](https://ollama.com)) understands natural language and calls
> real tools — backed by a [LangGraph](https://langchain-ai.github.io/langgraph/)
> agent — to create, read, update, search and summarize your tasks.

This repository is **v0.1 (scaffold)** of a multi-milestone project. See
[MILESTONES.md](./MILESTONES.md) for the full roadmap.

![Taskify screenshot placeholder](./docs/screenshot.png)

> _Screenshot placeholder — add `docs/screenshot.png` once the UI is captured._

---

## Stack

| Layer    | Technology |
|----------|------------|
| Frontend | Next.js 15 (App Router, TypeScript), Tailwind CSS v4, shadcn/ui, Zustand |
| Backend  | FastAPI (Python 3.12, async), SQLAlchemy 2.0 (async), Alembic, Pydantic v2 |
| Database | SQLite (v0.1) — schema designed to migrate to PostgreSQL |
| AI       | Ollama, LangGraph (ToolNode agent), `langchain-ollama` |

### Two-model strategy

Taskify is configured for two local models, each suited to a different job:

| Setting             | Default              | Purpose |
|---------------------|----------------------|---------|
| `OLLAMA_TOOL_MODEL` | `qwen3:8b`           | The **agent** model — strong, fast structured **tool calling** for the chat assistant. |
| `OLLAMA_CODE_MODEL` | `qwen2.5-coder:14b`  | Reserved for **code/reasoning** tasks in later milestones. |
| `OLLAMA_EMBED_MODEL`| `nomic-embed-text`   | Reserved for **embeddings / RAG** over tasks (v0.7). |

Keeping these as separate settings means each capability can be tuned or swapped
independently without touching application code.

---

## Architecture

```
taskify/
├── backend/    FastAPI + SQLAlchemy + Alembic + LangGraph agent
│   └── app/
│       ├── routers/    HTTP endpoints (tasks, agent)
│       ├── services/   business logic (task_service, agent_service)
│       ├── agent/      LangGraph graph, tools, prompts
│       ├── models/     SQLAlchemy ORM models
│       └── schemas/    Pydantic request/response models
└── frontend/   Next.js 15 App Router UI
    └── src/
        ├── app/        pages + /api/health route
        ├── components/ TaskList, TaskCard, TaskForm, ChatPanel, Header
        ├── store/      Zustand store
        └── lib/        typed API client
```

The browser only ever talks to the Next.js origin: requests to `/api/v1/*` are
**proxied** to the backend (see `frontend/next.config.ts`), and connectivity is
checked through the `/api/health` route handler.

The agent's tools call the **same service layer** as the REST API, so task logic
lives in exactly one place.

---

## Prerequisites

- **Python 3.12**
- **Node.js 24** (and npm)
- **[Ollama](https://ollama.com)** running locally at `http://localhost:11434`
- The two models pulled:

  ```bash
  ollama pull qwen3:8b
  ollama pull qwen2.5-coder:14b
  # optional, for v0.7 RAG:
  ollama pull nomic-embed-text
  ```

---

## Setup

### 1. Backend

```bash
cd backend

# create + activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

# install dependencies (use requirements-dev.txt for tests + linting)
pip install -r requirements-dev.txt

# configure environment
cp .env.example .env

# apply database migrations (also runs automatically on startup)
alembic upgrade head

# run the API (http://localhost:8000, docs at /docs)
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend

In a second terminal:

```bash
cd frontend

# configure environment (optional; defaults to http://localhost:8000)
cp .env.local.example .env.local

npm install
npm run dev                          # http://localhost:3000
```

Open **http://localhost:3000** and start adding tasks — or open the chat panel
and ask the assistant to do it for you.

---

## Environment variables

### Backend (`backend/.env`)

| Variable             | Default                              | Description |
|----------------------|--------------------------------------|-------------|
| `DATABASE_URL`       | `sqlite+aiosqlite:///./taskify.db`   | Async SQLAlchemy database URL. |
| `OLLAMA_BASE_URL`    | `http://localhost:11434`             | Ollama server URL. |
| `OLLAMA_TOOL_MODEL`  | `qwen3:8b`                           | Tool-calling agent model. |
| `OLLAMA_CODE_MODEL`  | `qwen2.5-coder:14b`                  | Code/reasoning model (future use). |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text`                   | Embedding model (future RAG). |
| `CORS_ORIGINS`       | `["http://localhost:3000"]`          | Allowed origins (JSON array or comma-separated). |
| `APP_ENV`            | `development`                        | Environment name. |
| `DEBUG`              | `true`                               | Enables SQL echo + verbose logging. |

### Frontend (`frontend/.env.local`)

| Variable      | Default                  | Description |
|---------------|--------------------------|-------------|
| `BACKEND_URL` | `http://localhost:8000`  | Backend base URL used by the proxy + health route. |

---

## API reference

Base URL: `http://localhost:8000`

| Method   | Path                      | Description |
|----------|---------------------------|-------------|
| `GET`    | `/health`                 | Service status, version, and live Ollama connectivity. |
| `GET`    | `/api/v1/tasks`           | List tasks. Supports `?status=` and `?priority=` filters. |
| `POST`   | `/api/v1/tasks`           | Create a task. |
| `GET`    | `/api/v1/tasks/{id}`      | Get a single task. |
| `PATCH`  | `/api/v1/tasks/{id}`      | Partially update a task. |
| `DELETE` | `/api/v1/tasks/{id}`      | Delete a task (`204 No Content`). |
| `POST`   | `/api/v1/agent/chat`      | Chat with the agent. Body: `{ "message": str, "history": [] }`. Returns `{ response, tool_calls, tokens_used }`. |

Interactive OpenAPI docs are available at **http://localhost:8000/docs**.

### Agent tools

The LangGraph agent can call these tools (all backed by real DB queries):

- `search_tasks(query, status?, priority?)`
- `create_task(title, description?, priority?, due_date?)`
- `update_task(task_id, status?, priority?, title?)`
- `summarize_tasks()`

Example:

```bash
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"How many tasks do I have?","history":[]}'
```

---

## Testing & quality

```bash
# Backend
cd backend
ruff check .       # lint
pytest -q          # unit tests (CRUD + agent tools, no LLM required)

# Frontend
cd frontend
npm run lint
npm run build
```

CI runs all of the above on every push / PR to `main` (see
`.github/workflows/ci.yml`).

---

## Contributing

Development is organized into milestones. Before starting work, read
[MILESTONES.md](./MILESTONES.md) to see what belongs in each version and which
git tag is cut on completion. Keep task business-logic in the **service layer**
so it stays shared between the REST API and the agent tools.
