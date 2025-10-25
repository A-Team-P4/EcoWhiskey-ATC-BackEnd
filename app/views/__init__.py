"""Pydantic schemas used as views in the MVC architecture."""

from .auth import LoginRequest, TokenResponse
from .common import ErrorResponse, SuccessResponse
from .hello import HelloMessageCreate, HelloMessageRead
from .schools import SchoolCreateRequest, SchoolResponse, SchoolUpdateRequest
from .training_context import (
    TrainingContextHistoryItem,
    TrainingContextRequest,
    TrainingContextResponse,
)
from .tts import TextToSpeechRequest
from .users import (
    User,
    UserRegistrationRequest,
    UserRegistrationResponse,
    UserResponse,
    UserUpdateRequest,
    UserChangeSchoolRequest,
    UserChangePasswordRequest,
)

__all__ = [
    "User",
    "UserRegistrationRequest",
    "UserRegistrationResponse",
    "UserResponse",
    "UserUpdateRequest",
    "UserChangeSchoolRequest",
    "UserChangePasswordRequest",
    "HelloMessageCreate",
    "HelloMessageRead",
    "TextToSpeechRequest",
    "SchoolCreateRequest",
    "SchoolResponse",
    "SchoolUpdateRequest",
    "TrainingContextHistoryItem",
    "TrainingContextRequest",
    "TrainingContextResponse",
    "ErrorResponse",
    "SuccessResponse",
    "LoginRequest",
    "TokenResponse",
]
