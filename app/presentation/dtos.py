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


class HelloMessageCreateRequest(BaseModel):
    """Request DTO for hello-world message creation"""

    message: str


class HelloMessageResponse(BaseModel):
    """Response DTO for hello-world messages"""

    id: int
    message: str
    created_at: datetime


class TtsRequest(BaseModel):
    """Request DTO for text-to-speech conversion"""

    text: str
    voice_id: Optional[str] = None
