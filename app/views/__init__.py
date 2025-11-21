"""Pydantic schemas used as views in the MVC architecture."""

from .auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    TokenResponse,
)
from .common import ErrorResponse, SuccessResponse
from .hello import HelloMessageCreate, HelloMessageRead
from .groups import (
    GroupCreateRequest,
    GroupMemberResponse,
    GroupMembershipCreateRequest,
    GroupMembershipResponse,
    GroupResponse,
    GroupUpdateRequest,
)
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
    "ForgotPasswordRequest",
    "ForgotPasswordResponse",
    "HelloMessageCreate",
    "HelloMessageRead",
    "TextToSpeechRequest",
    "SchoolCreateRequest",
    "SchoolResponse",
    "SchoolUpdateRequest",
    "TrainingContextHistoryItem",
    "TrainingContextRequest",
    "TrainingContextResponse",
    "GroupCreateRequest",
    "GroupUpdateRequest",
    "GroupResponse",
    "GroupMembershipCreateRequest",
    "GroupMembershipResponse",
    "GroupMemberResponse",
    "ErrorResponse",
    "SuccessResponse",
    "LoginRequest",
    "TokenResponse",
]
