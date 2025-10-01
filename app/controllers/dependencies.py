"""Common FastAPI dependencies reused across controllers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.user import User as UserModel
from app.utils import AuthenticationError, decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: SessionDep,
) -> UserModel:
    """Resolve and validate the user referenced by the bearer token."""

    try:
        payload = decode_access_token(token)
        user_id = int(payload.sub)
    except (AuthenticationError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        ) from None

    result = await session.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


CurrentUserDep = Annotated[UserModel, Depends(get_current_user)]


__all__ = ["get_current_user", "oauth2_scheme", "SessionDep", "CurrentUserDep"]
