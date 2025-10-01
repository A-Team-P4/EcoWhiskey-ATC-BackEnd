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
from .hello import HelloMessageCreate, HelloMessageRead
from .tts import TextToSpeechRequest
from .common import ErrorResponse, SuccessResponse
from .auth import LoginRequest, TokenResponse

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
    "LoginRequest",
    "TokenResponse",
]
