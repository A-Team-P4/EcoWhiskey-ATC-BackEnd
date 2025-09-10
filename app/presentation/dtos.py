from typing import Optional
from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.domain.models import UserStatus


class UserCreateRequest(BaseModel):
    """Request DTO for creating a user"""

    email: EmailStr
    full_name: str
    username: Optional[str] = None


class UserUpdateRequest(BaseModel):
    """Request DTO for updating a user"""

    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    username: Optional[str] = None
    status: Optional[UserStatus] = None


class UserResponse(BaseModel):
    """Response DTO for user"""

    id: int
    email: str
    username: str
    full_name: str
    status: str
    created_at: datetime
    updated_at: datetime


class ErrorResponse(BaseModel):
    """Response DTO for errors"""

    detail: str
    code: Optional[str] = None


class SuccessResponse(BaseModel):
    """Response DTO for success messages"""

    message: str
    data: Optional[dict] = None


class TtsRequest(BaseModel):
    """Request DTO for text-to-speech conversion"""

    text: str
    voice_id: Optional[str] = None

