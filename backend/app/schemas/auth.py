"""Pydantic schemas for authentication.

Email validation is done with a light, dependency-free regex (avoids pulling in
``email-validator``); it is intentionally permissive but rejects obviously
malformed addresses.
"""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserRegister(BaseModel):
    """Registration payload."""

    email: str = Field(..., max_length=320)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _EMAIL_RE.match(normalized):
            raise ValueError("Invalid email address.")
        return normalized


class UserLogin(BaseModel):
    """Login payload."""

    email: str = Field(..., max_length=320)
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class UserRead(BaseModel):
    """Public representation of a user (never includes the password hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    is_active: bool
    created_at: datetime


class TokenPair(BaseModel):
    """Access + refresh token pair returned on register/login/refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Body for ``POST /api/v1/auth/refresh``."""

    refresh_token: str = Field(..., min_length=1)
