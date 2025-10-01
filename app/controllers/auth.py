"""Authentication controller providing login endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.database import get_session
from app.models.user import User as UserModel
from app.utils import create_access_token, verify_password
from app.views import LoginRequest, TokenResponse


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Validate credentials and issue a JWT access token."""

    result = await session.execute(
            select(UserModel).where(UserModel.email == payload.email)
        )
    user = result.scalar_one_or_none()

    if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = create_access_token(subject=str(user.id))
    expires_in = settings.security.access_token_expires_minutes * 60

    return TokenResponse(access_token=access_token, expires_in=expires_in)
