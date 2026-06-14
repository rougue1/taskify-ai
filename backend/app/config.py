"""Application configuration loaded from environment variables.

Uses pydantic-settings so every value can be overridden via the environment
or a local ``.env`` file. Defaults are tuned for local development and the
schema is intentionally driver-agnostic so the move from SQLite (v0.1) to
PostgreSQL (v0.7) only requires changing ``DATABASE_URL``.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Database -----------------------------------------------------------
    DATABASE_URL: str = "sqlite+aiosqlite:///./taskify.db"

    # --- Ollama / AI layer --------------------------------------------------
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_TOOL_MODEL: str = "qwen3:8b"
    OLLAMA_CODE_MODEL: str = "qwen2.5-coder:14b"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"

    # --- HTTP / CORS --------------------------------------------------------
    # Accepts a JSON array (``["http://a", "http://b"]``) or a comma separated
    # string (``http://a,http://b``) from the environment.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    # --- Runtime ------------------------------------------------------------
    APP_ENV: str = "development"
    DEBUG: bool = True

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> object:
        if value is None or value == "":
            return ["http://localhost:3000"]
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                return json.loads(stripped)
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance."""

    return Settings()


# Importable singleton for convenience across the codebase.
settings = get_settings()
