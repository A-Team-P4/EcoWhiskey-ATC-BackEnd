"""Pydantic schemas for user interactions."""

from __future__ import annotations

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
    school: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


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
    school: Optional[str] = None

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

    @field_validator("school")
    @classmethod
    def validate_school_length(cls, value: Optional[str]) -> Optional[str]:
        """Validate school field length when provided."""
        if value is not None and value.strip():
            if len(value.strip()) > 100:
                raise ValueError("School name cannot exceed 100 characters")
            if len(value.strip()) < 1:
                raise ValueError("School name cannot be empty when provided")
            return value.strip()
        return value

    @model_validator(mode="after")
    def validate_school_requirement(self) -> "UserRegistrationRequest":
        """Validate that instructors must provide a school."""
        if self.accountType == AccountType.INSTRUCTOR:
            if not self.school or self.school.strip() == "":
                raise ValueError("School is required for instructor accounts")
        return self


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
    school: Optional[str] = None
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
    school: Optional[str] = None
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
    school: Optional[str] = Field(None, min_length=1, max_length=100)

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
