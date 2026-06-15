"""Password hashing and JWT helpers.

Password hashing uses ``bcrypt`` directly (no passlib) and JWTs use ``PyJWT``
with HS256. Tokens carry a ``type`` claim (``access`` or ``refresh``) so a
refresh token can never be used to authorize an API call and vice versa.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
import jwt

from app.config import settings

# bcrypt only considers the first 72 bytes of a password; encode + truncate
# explicitly so longer inputs hash deterministically instead of raising.
_BCRYPT_MAX_BYTES = 72

TokenType = Literal["access", "refresh"]


def hash_password(password: str) -> str:
    """Return a salted bcrypt hash of ``password``."""

    pw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Return ``True`` if ``password`` matches ``hashed``.

    Never raises: a malformed stored hash (e.g. the placeholder used for the
    migration's system user) simply fails verification.
    """

    try:
        pw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
        return bcrypt.checkpw(pw, hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _create_token(subject: str, token_type: TokenType, expires_delta: timedelta) -> str:
    """Encode a signed JWT for ``subject`` with an expiry and a ``type`` claim."""

    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str | int) -> str:
    """Create a short-lived access token for the given user id."""

    return _create_token(
        str(subject),
        "access",
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(subject: str | int) -> str:
    """Create a long-lived refresh token for the given user id."""

    return _create_token(
        str(subject),
        "refresh",
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str, *, expected_type: TokenType) -> dict[str, Any]:
    """Decode and validate a JWT, enforcing signature, expiry and token type.

    Raises ``jwt.InvalidTokenError`` (or a subclass) on any failure.
    """

    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(
            f"Expected a {expected_type} token, got {payload.get('type')!r}."
        )
    return payload
