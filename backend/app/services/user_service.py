"""Business logic for users and authentication."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.security import hash_password, verify_password


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    """Return the user with this email (case-insensitive), or ``None``."""

    result = await session.execute(select(User).where(User.email == email.strip().lower()))
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    """Return the user with this id, or ``None``."""

    return await session.get(User, user_id)


async def create_user(session: AsyncSession, email: str, password: str) -> User:
    """Create and persist a new user with a hashed password."""

    user = User(email=email.strip().lower(), hashed_password=hash_password(password))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def authenticate(session: AsyncSession, email: str, password: str) -> User | None:
    """Return the user if the email exists, is active and the password matches."""

    user = await get_user_by_email(session, email)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
