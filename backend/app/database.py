"""Async SQLAlchemy engine, session factory and helpers.

The engine is driver-agnostic: it runs on SQLite (``sqlite+aiosqlite``) for local
dev and tests, and on PostgreSQL (``postgresql+asyncpg``) in Docker/production —
switching is purely a matter of ``DATABASE_URL``. Semantic search (pgvector) is
only available on PostgreSQL; the ``tasks.embedding`` column is added by a
PostgreSQL-only migration and the embedding service degrades gracefully
elsewhere (see :mod:`app.services.embedding`).

The session machinery is exposed in two ways:

* :func:`get_session` — a FastAPI dependency that yields a request-scoped
  session.
* :func:`session_scope` — a standalone async context manager used outside of
  the request lifecycle (e.g. by the LangGraph agent tools) that commits on
  success and rolls back on error.

Both reference the module-level :data:`AsyncSessionLocal`, which the test suite
rebinds to point at a throwaway database.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session per request."""

    async with AsyncSessionLocal() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional session for use outside of FastAPI.

    Commits when the block exits cleanly and rolls back on exception. Used by
    the agent tools which run independently of the HTTP request lifecycle.
    """

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
