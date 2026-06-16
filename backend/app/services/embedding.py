"""Task embeddings + semantic search via Ollama and pgvector.

Embeddings are produced by the ``nomic-embed-text`` model through Ollama's
``/api/embeddings`` endpoint and stored in the ``tasks.embedding`` pgvector
column (768-dim). The embedded text is ``"{title}. {description}"``.

Every operation degrades gracefully: on a non-PostgreSQL database, or when Ollama
or pgvector is unavailable, storage becomes a safe no-op and search returns
``None``. Callers (the REST endpoint and the ``semantic_search_tasks`` tool) turn
a ``None`` result into a friendly "semantic search unavailable" response instead
of crashing — so the rest of the app works fine without the RAG stack running.

The vector is passed to PostgreSQL as a text literal cast to ``vector`` (e.g.
``CAST(:vec AS vector)``), which avoids any asyncpg type registration and keeps
the ORM model portable to SQLite (the ``embedding`` column lives only in the
PostgreSQL schema, added by an Alembic migration).
"""

from __future__ import annotations

import logging

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.task import Task

logger = logging.getLogger("taskify.embedding")

# nomic-embed-text produces 768-dimensional vectors.
EMBED_DIM = 768
# Ollama embedding calls are best-effort; keep a bounded timeout so a slow or
# missing model never blocks task creation for long.
_TIMEOUT = 30.0


def is_vector_db() -> bool:
    """True when the configured database is PostgreSQL (so pgvector is in play)."""

    return settings.DATABASE_URL.startswith("postgresql")


def task_embedding_text(task: Task) -> str:
    """Build the combined text embedded for a task."""

    return f"{task.title}. {task.description or ''}".strip()


def _vector_literal(vector: list[float]) -> str:
    """Render a float list as a pgvector text literal, e.g. ``[0.1,0.2,...]``."""

    return "[" + ",".join(f"{value:.6f}" for value in vector) + "]"


async def embed_text(value: str) -> list[float] | None:
    """Return the embedding for ``value``, or ``None`` if Ollama is unreachable."""

    cleaned = (value or "").strip()
    if not cleaned:
        return None
    url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/embeddings"
    payload = {"model": settings.OLLAMA_EMBED_MODEL, "prompt": cleaned}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
        vector = data.get("embedding")
        if not vector:
            return None
        return [float(value) for value in vector]
    except Exception as exc:  # noqa: BLE001 - embeddings are best-effort
        logger.warning("Embedding request failed: %s", exc)
        return None


async def store_task_embedding(session: AsyncSession, task: Task) -> bool:
    """Generate and persist a task's embedding. No-op unless on PostgreSQL.

    Returns ``True`` when an embedding was stored. Safe to call from any task
    create/update path: failures (no Ollama, SQLite, DB error) are swallowed so
    the surrounding write still succeeds.
    """

    if not is_vector_db():
        return False
    vector = await embed_text(task_embedding_text(task))
    if vector is None:
        return False
    try:
        await session.execute(
            text("UPDATE tasks SET embedding = CAST(:vec AS vector) WHERE id = :id"),
            {"vec": _vector_literal(vector), "id": task.id},
        )
        await session.commit()
        return True
    except Exception as exc:  # noqa: BLE001 - never break the originating write
        logger.warning("Storing embedding for task %s failed: %s", task.id, exc)
        await session.rollback()
        return False


async def semantic_search(
    session: AsyncSession, *, user_id: int, query: str, limit: int = 5
) -> list[Task] | None:
    """Return the ``limit`` most semantically similar tasks for ``user_id``.

    Returns ``None`` when semantic search is unavailable (not PostgreSQL, Ollama
    down, or a query error), and ``[]`` when it ran but matched nothing.
    """

    if not is_vector_db():
        return None
    vector = await embed_text(query)
    if vector is None:
        return None
    try:
        rows = await session.execute(
            text(
                "SELECT id FROM tasks "
                "WHERE user_id = :uid AND embedding IS NOT NULL "
                "ORDER BY embedding <=> CAST(:q AS vector) ASC "
                "LIMIT :limit"
            ),
            {"uid": user_id, "q": _vector_literal(vector), "limit": limit},
        )
        ids = [row[0] for row in rows]
        if not ids:
            return []
        tasks = (await session.execute(select(Task).where(Task.id.in_(ids)))).scalars().all()
        by_id = {task.id: task for task in tasks}
        # Preserve the similarity order returned by the vector query.
        return [by_id[task_id] for task_id in ids if task_id in by_id]
    except Exception as exc:  # noqa: BLE001 - report unavailability, don't crash
        logger.warning("Semantic search failed: %s", exc)
        return None
