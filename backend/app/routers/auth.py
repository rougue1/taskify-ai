"""Authentication endpoints, mounted under ``/api/v1/auth``.

These routes are public (no token required) except ``/me``. Registration and
login both return an access + refresh token pair.
"""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import CurrentUser
from app.schemas.auth import RefreshRequest, TokenPair, UserLogin, UserRead, UserRegister
from app.security import create_access_token, create_refresh_token, decode_token
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["auth"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _token_pair_for(user_id: int) -> TokenPair:
    """Mint a fresh access + refresh token pair for a user id."""

    return TokenPair(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.post(
    "/register",
    response_model=TokenPair,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account",
)
async def register(payload: UserRegister, session: SessionDep) -> TokenPair:
    """Create an account and return an access/refresh token pair.

    Returns ``409`` if the email is already registered.
    """

    existing = await user_service.get_user_by_email(session, payload.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )
    user = await user_service.create_user(session, payload.email, payload.password)
    return _token_pair_for(user.id)


@router.post("/login", response_model=TokenPair, summary="Log in")
async def login(payload: UserLogin, session: SessionDep) -> TokenPair:
    """Authenticate and return an access/refresh token pair.

    Returns ``401`` for an unknown email or an incorrect password.
    """

    user = await user_service.authenticate(session, payload.email, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    return _token_pair_for(user.id)


@router.post("/refresh", response_model=TokenPair, summary="Refresh tokens")
async def refresh(payload: RefreshRequest, session: SessionDep) -> TokenPair:
    """Exchange a valid refresh token for a new access/refresh token pair."""

    try:
        claims = decode_token(payload.refresh_token, expected_type="refresh")
        user_id = int(claims["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        ) from exc

    user = await user_service.get_user_by_id(session, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )
    return _token_pair_for(user.id)


@router.get("/me", response_model=UserRead, summary="Current user")
async def me(current_user: CurrentUser) -> UserRead:
    """Return the currently authenticated user."""

    return current_user
