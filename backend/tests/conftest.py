"""Pytest fixtures.

Each test runs against a fresh in-memory SQLite database. The module-level
``AsyncSessionLocal`` in :mod:`app.database` is rebound to the test factory so
that the agent tools (which create their own sessions via ``session_scope``)
operate on the same throwaway database as the API client.
"""

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

import app.database as database
import app.models  # noqa: F401 - ensure models register on Base.metadata
from app.database import Base, get_session
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite://"


@pytest_asyncio.fixture
async def engine():
    test_engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    # Rebind the global used by the agent tools' session_scope().
    original = database.AsyncSessionLocal
    database.AsyncSessionLocal = factory
    try:
        yield factory
    finally:
        database.AsyncSessionLocal = original


@pytest_asyncio.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(session_factory):
    async def _get_session_override():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _get_session_override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
