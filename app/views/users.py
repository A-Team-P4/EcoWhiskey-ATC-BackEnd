"""Pydantic schemas for user interactions."""

from __future__ import annotations

import base64
import binascii
import re
from datetime import datetime
from typing import Optional

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.models.user import AccountType, UserStatus
from app.views.schools import SchoolResponse


def _validate_base64_payload(value: str) -> str:
    """Validate that the provided string is Base64-encoded (data URI accepted)."""

    data = value.strip()
    if not data:
        raise ValueError("Photo cannot be empty")

    payload = data.split(",", 1)[1] if "," in data else data
    try:
        base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Photo must be a valid base64-encoded string") from exc

    return data


class User(BaseModel):
    """Domain model for User entity."""

    id: Optional[int] = None
    email: EmailStr
    firstName: str = Field(
        ...,
        validation_alias=AliasChoices("firstName", "first_name"),
        serialization_alias="firstName",
    )
    lastName: str = Field(
        ...,
        validation_alias=AliasChoices("lastName", "last_name"),
        serialization_alias="lastName",
    )
    password: str
    status: UserStatus = UserStatus.ACTIVE
    accountType: AccountType = Field(
        ...,
        validation_alias=AliasChoices("accountType", "account_type"),
        serialization_alias="accountType",
    )
    schoolId: Optional[int] = Field(
        None,
        ge=1,
        validation_alias=AliasChoices("schoolId", "school_id"),
        serialization_alias="schoolId",
    )
    school: Optional[SchoolResponse] = None
    photo: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("photo", "photo_base64"),
        serialization_alias="photo",
    )
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_validator("photo")
    @classmethod
    def validate_photo(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return _validate_base64_payload(value)


class UserRegistrationRequest(BaseModel):
    """Request model for user registration."""

    email: EmailStr
    firstName: str = Field(
        ...,
        min_length=1,
        max_length=50,
        validation_alias=AliasChoices("firstName", "first_name"),
        serialization_alias="firstName",
    )
    lastName: str = Field(
        ...,
        min_length=1,
        max_length=50,
        validation_alias=AliasChoices("lastName", "last_name"),
        serialization_alias="lastName",
    )
    password: str = Field(..., min_length=8, max_length=128)
    accountType: AccountType = Field(
        ...,
        validation_alias=AliasChoices("accountType", "account_type"),
        serialization_alias="accountType",
    )
    schoolId: Optional[int] = Field(
        None,
        ge=1,
        validation_alias=AliasChoices("schoolId", "school_id"),
        serialization_alias="schoolId",
    )
    photo: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("photo", "photo_base64"),
        serialization_alias="photo",
    )

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", value):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", value):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", value):
            raise ValueError("Password must contain at least one digit")
        return value

    @field_validator("firstName", "lastName")
    @classmethod
    def validate_names(cls, value: str) -> str:
        if not re.match(r"^[a-zA-Z\s\-']+$", value):
            raise ValueError(
                "Name can only contain letters, spaces, hyphens, and apostrophes"
            )
        return value.strip()

    @model_validator(mode="after")
    def validate_school_requirement(self) -> "UserRegistrationRequest":
        """Validate that instructors must provide a school."""
        if self.accountType == AccountType.INSTRUCTOR:
            if not self.schoolId:
                raise ValueError("School is required for instructor accounts")
        return self

    @field_validator("photo")
    @classmethod
    def validate_photo(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return _validate_base64_payload(value)

    @field_validator("photo")
    @classmethod
    def validate_photo(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return _validate_base64_payload(value)


class UserRegistrationResponse(BaseModel):
    """Response model for successful user registration."""

    id: int
    email: EmailStr
    firstName: str = Field(
        ...,
        validation_alias=AliasChoices("firstName", "first_name"),
        serialization_alias="firstName",
    )
    lastName: str = Field(
        ...,
        validation_alias=AliasChoices("lastName", "last_name"),
        serialization_alias="lastName",
    )
    status: UserStatus
    accountType: AccountType = Field(
        ...,
        validation_alias=AliasChoices("accountType", "account_type"),
        serialization_alias="accountType",
    )
    school: Optional[SchoolResponse] = None
    photo: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("photo", "photo_base64"),
        serialization_alias="photo",
    )
    created_at: datetime
    message: str

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class UserResponse(BaseModel):
    """General user response model."""

    id: int
    email: EmailStr
    firstName: str = Field(
        ...,
        validation_alias=AliasChoices("firstName", "first_name"),
        serialization_alias="firstName",
    )
    lastName: str = Field(
        ...,
        validation_alias=AliasChoices("lastName", "last_name"),
        serialization_alias="lastName",
    )
    status: UserStatus
    accountType: AccountType = Field(
        ...,
        validation_alias=AliasChoices("accountType", "account_type"),
        serialization_alias="accountType",
    )
    school: Optional[SchoolResponse] = None
    photo: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("photo", "photo_base64"),
        serialization_alias="photo",
    )
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class UserUpdateRequest(BaseModel):
    """Request model for updating user details."""

    firstName: Optional[str] = Field(
        None,
        min_length=1,
        max_length=50,
        validation_alias=AliasChoices("firstName", "first_name"),
        serialization_alias="firstName",
    )
    lastName: Optional[str] = Field(
        None,
        min_length=1,
        max_length=50,
        validation_alias=AliasChoices("lastName", "last_name"),
        serialization_alias="lastName",
    )
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    status: Optional[UserStatus] = None
    accountType: Optional[AccountType] = Field(
        None,
        validation_alias=AliasChoices("accountType", "account_type"),
        serialization_alias="accountType",
    )
    schoolId: Optional[int] = Field(
        None,
        ge=1,
        validation_alias=AliasChoices("schoolId", "school_id"),
        serialization_alias="schoolId",
    )
    photo: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("photo", "photo_base64"),
        serialization_alias="photo",
    )

    @field_validator("password")
    @classmethod
    def validate_optional_password(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", value):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", value):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", value):
            raise ValueError("Password must contain at least one digit")
        return value

    @field_validator("firstName", "lastName")
    @classmethod
    def validate_optional_names(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if not re.match(r"^[a-zA-Z\s\-']+$", value):
            raise ValueError(
                "Name can only contain letters, spaces, hyphens, and apostrophes"
            )
        return value.strip()

    @field_validator("photo")
    @classmethod
    def validate_optional_photo(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return _validate_base64_payload(value)


class UserChangeSchoolRequest(BaseModel):
    """Request model to update a user's school."""

    schoolId: int = Field(
        ...,
        ge=1,
        validation_alias=AliasChoices("schoolId", "school_id"),
        serialization_alias="schoolId",
    )


class UserChangePasswordRequest(BaseModel):
    """Request model for user password changes."""

    currentPassword: str = Field(
        ...,
        min_length=8,
        max_length=128,
        validation_alias=AliasChoices("currentPassword", "current_password"),
        serialization_alias="currentPassword",
    )
    newPassword: str = Field(
        ...,
        min_length=8,
        max_length=128,
        validation_alias=AliasChoices("newPassword", "new_password"),
        serialization_alias="newPassword",
    )

    @field_validator("newPassword")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", value):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", value):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", value):
            raise ValueError("Password must contain at least one digit")
        return value

    @model_validator(mode="after")
    def ensure_new_differs(self) -> "UserChangePasswordRequest":
        if self.currentPassword == self.newPassword:
            raise ValueError("New password must be different from the current one")
        return self

