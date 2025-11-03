"""Pydantic schemas related to authentication."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.views.schools import SchoolResponse


class LoginRequest(BaseModel):
    """Credentials submitted to obtain an access token."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    """Standard access token response body."""

    access_token: str = Field(serialization_alias="accessToken")
    token_type: str = Field(default="bearer", serialization_alias="tokenType")
    expires_in: int = Field(
        default=0,
        serialization_alias="expiresIn",
        description="Seconds until the token expires",
    )
    account_type: str = Field(serialization_alias="accountType")
    name: str = Field(serialization_alias="name")
    school: SchoolResponse | None = Field(
        default=None,
        serialization_alias="school",
    )

class ForgotPasswordRequest(BaseModel):
    """Request payload for password recovery."""

    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    """Response payload for password recovery attempts."""

    exists: bool
    message: str

__all__ = [
    "LoginRequest",
    "TokenResponse",
    "ForgotPasswordRequest",
    "ForgotPasswordResponse",
]
