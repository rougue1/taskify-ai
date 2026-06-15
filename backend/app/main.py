"""FastAPI application entry point for Taskify."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import settings
from app.errors import register_exception_handlers
from app.routers import agent as agent_router
from app.routers import auth as auth_router
from app.routers import tasks as tasks_router

logging.basicConfig(level=logging.DEBUG if settings.DEBUG else logging.INFO)
logger = logging.getLogger("taskify")

# backend/ directory — used to locate alembic config independent of CWD.
BASE_DIR = Path(__file__).resolve().parent.parent


def _run_migrations() -> None:
    """Apply Alembic migrations up to ``head`` using a synchronous driver."""

    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BASE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BASE_DIR / "alembic"))
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run database migrations on startup before serving traffic."""

    logger.info("Applying database migrations...")
    try:
        # Run in a worker thread so Alembic's own engine does not collide with
        # the running event loop.
        await asyncio.to_thread(_run_migrations)
        logger.info("Database migrations applied.")
    except Exception:
        logger.exception("Database migration failed during startup")
        raise
    yield


app = FastAPI(
    title="Taskify API",
    version=__version__,
    description=(
        "Local AI-powered task manager with agentic tool calling. "
        "REST CRUD plus a LangGraph agent backed by Ollama."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(auth_router.router, prefix="/api/v1")
app.include_router(tasks_router.router, prefix="/api/v1")
app.include_router(agent_router.router, prefix="/api/v1")


async def _check_ollama() -> dict:
    """Probe the configured Ollama server and report connectivity."""

    url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            models = [m.get("name") for m in response.json().get("models", [])]
        return {
            "connected": True,
            "base_url": settings.OLLAMA_BASE_URL,
            "tool_model": settings.OLLAMA_TOOL_MODEL,
            "tool_model_available": settings.OLLAMA_TOOL_MODEL in models,
            "models": models,
        }
    except Exception as exc:  # noqa: BLE001 - connectivity probe must not raise
        return {
            "connected": False,
            "base_url": settings.OLLAMA_BASE_URL,
            "error": str(exc),
        }


@app.get("/health", tags=["health"], summary="Health check")
async def health() -> dict:
    """Return service status, version and live Ollama connectivity."""

    return {
        "status": "ok",
        "version": __version__,
        "environment": settings.APP_ENV,
        "ollama": await _check_ollama(),
    }


@app.get("/", include_in_schema=False)
async def root() -> dict:
    """Root landing payload pointing at the docs and health endpoints."""

    return {
        "name": "Taskify API",
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
    }
