"""Shared FastAPI dependencies (authentication)."""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.user import User
from app.security import decode_token
from app.services import user_service

# auto_error=False so we can emit our own consistent 401 envelope (and the
# proper WWW-Authenticate header) rather than FastAPI's default.
_bearer_scheme = HTTPBearer(auto_error=False, description="JWT access token")

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """Resolve and return the authenticated user from the Bearer access token.

    Raises ``401`` for a missing, malformed, expired or non-access token, or
    when the referenced user no longer exists or is inactive.
    """

    if credentials is None or not credentials.credentials:
        raise _UNAUTHENTICATED

    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError, TypeError) as exc:
        raise _UNAUTHENTICATED from exc

    user = await user_service.get_user_by_id(session, user_id)
    if user is None or not user.is_active:
        raise _UNAUTHENTICATED
    return user


# Convenience alias for route signatures: `user: CurrentUser`.
CurrentUser = Annotated[User, Depends(get_current_user)]
