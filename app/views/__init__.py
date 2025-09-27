"""Pydantic schemas used as views in the MVC architecture."""

from .users import (
    User,
    UserRegistrationRequest,
    UserRegistrationResponse,
    UserResponse,
    UserUpdateRequest,
)
from .hello import HelloMessageCreate, HelloMessageRead
from .tts import TextToSpeechRequest
from .common import ErrorResponse, SuccessResponse

__all__ = [
    "User",
    "UserRegistrationRequest",
    "UserRegistrationResponse",
    "UserResponse",
    "UserUpdateRequest",
    "HelloMessageCreate",
    "HelloMessageRead",
    "TextToSpeechRequest",
    "ErrorResponse",
    "SuccessResponse",
]
