#!/usr/bin/env bash
#
# Taskify dev launcher — starts the FastAPI backend (:8000) and the Next.js
# frontend (:3000) together, tails both logs, and shuts both down cleanly on
# Ctrl+C.
#
#   ./start.sh
#
# This is the lightweight local path: the backend defaults to SQLite, so
# everything works EXCEPT semantic search (which needs PostgreSQL + pgvector).
# For the full stack with Postgres, pgvector and Ollama in containers, use:
#
#   cp .env.example .env && make dev && make pull-models && make migrate
#
# New backend deps (dateparser, asyncpg, pgvector, psycopg2-binary) are in
# backend/requirements.txt — re-run `pip install -r requirements.txt` in the
# venv if the backend fails to import them.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
BACKEND_LOG="$ROOT/backend.log"
FRONTEND_LOG="$ROOT/frontend.log"

# Prefer the backend virtualenv interpreter if it exists.
if [ -x "$BACKEND_DIR/.venv/bin/python" ]; then
  PY="$BACKEND_DIR/.venv/bin/python"
else
  PY="python3"
fi

BACKEND_PID=""
FRONTEND_PID=""
TAIL_PID=""

cleanup() {
  echo
  echo "Stopping Taskify..."
  # Kill the frontend's child processes (next dev workers) as well as the roots.
  [ -n "$FRONTEND_PID" ] && pkill -P "$FRONTEND_PID" 2>/dev/null || true
  [ -n "$BACKEND_PID" ] && pkill -P "$BACKEND_PID" 2>/dev/null || true
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null || true
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null || true
  [ -n "$TAIL_PID" ] && kill "$TAIL_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

# Fresh logs so the tail only shows this run.
: > "$BACKEND_LOG"
: > "$FRONTEND_LOG"

echo "Starting Taskify backend (uvicorn :8000)..."
( cd "$BACKEND_DIR" && exec "$PY" -m uvicorn app.main:app --reload --port 8000 ) \
  > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

echo "Starting Taskify frontend (next dev :3000)..."
( cd "$FRONTEND_DIR" && exec npm run dev ) > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

echo
echo "  ➜  Frontend:  http://localhost:3000"
echo "  ➜  Backend:   http://localhost:8000"
echo "  ➜  API docs:  http://localhost:8000/docs"
echo
echo "Tailing backend.log + frontend.log — press Ctrl+C to stop both."
echo

# Stream both logs to the terminal.
tail -n +1 -F "$BACKEND_LOG" "$FRONTEND_LOG" &
TAIL_PID=$!

# Stay up until either service exits, then tear everything down.
wait -n "$BACKEND_PID" "$FRONTEND_PID"
cleanup
