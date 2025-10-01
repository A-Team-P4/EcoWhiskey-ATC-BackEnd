"""Pydantic schemas used as views in the MVC architecture."""

from .common import ErrorResponse, SuccessResponse
from .hello import HelloMessageCreate, HelloMessageRead
from .tts import TextToSpeechRequest
from .users import (
    User,
    UserRegistrationRequest,
    UserRegistrationResponse,
    UserResponse,
    UserUpdateRequest,
)

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
