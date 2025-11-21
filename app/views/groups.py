"""Pydantic schemas for group management."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field

from app.models.group_membership import GroupMembershipStatus, GroupRole


class GroupCreateRequest(BaseModel):
    """Payload to create a group."""

    name: str = Field(..., min_length=3, max_length=120)
    description: Optional[str] = Field(None, max_length=500)


class GroupUpdateRequest(BaseModel):
    """Payload to rename/update a group."""

    name: Optional[str] = Field(None, min_length=3, max_length=120)
    description: Optional[str] = Field(None, max_length=500)


class GroupResponse(BaseModel):
    """Information about a group relative to the current user."""

    id: int
    name: str
    description: Optional[str] = None
    schoolId: int = Field(
        ...,
        validation_alias=AliasChoices("schoolId", "school_id"),
        serialization_alias="schoolId",
    )
    ownerId: int = Field(
        ...,
        validation_alias=AliasChoices("ownerId", "owner_id"),
        serialization_alias="ownerId",
    )
    membershipRole: Optional[GroupRole] = Field(
        None,
        validation_alias=AliasChoices("membershipRole", "membership_role"),
        serialization_alias="membershipRole",
    )
    membershipStatus: Optional[GroupMembershipStatus] = Field(
        None,
        validation_alias=AliasChoices("membershipStatus", "membership_status"),
        serialization_alias="membershipStatus",
    )
    createdAt: datetime = Field(
        ...,
        validation_alias=AliasChoices("createdAt", "created_at"),
        serialization_alias="createdAt",
    )
    updatedAt: datetime = Field(
        ...,
        validation_alias=AliasChoices("updatedAt", "updated_at"),
        serialization_alias="updatedAt",
    )

    class Config:
        populate_by_name = True
        from_attributes = True


class GroupMembershipCreateRequest(BaseModel):
    """Payload for instructors to add a student."""

    userId: int = Field(
        ...,
        ge=1,
        validation_alias=AliasChoices("userId", "user_id"),
        serialization_alias="userId",
    )

    class Config:
        populate_by_name = True


class GroupMembershipResponse(BaseModel):
    """Serialized membership/invitation data."""

    id: int
    groupId: int = Field(
        ...,
        validation_alias=AliasChoices("groupId", "group_id"),
        serialization_alias="groupId",
    )
    userId: int = Field(
        ...,
        validation_alias=AliasChoices("userId", "user_id"),
        serialization_alias="userId",
    )
    role: GroupRole
    status: GroupMembershipStatus
    invitedById: Optional[int] = Field(
        None,
        validation_alias=AliasChoices("invitedById", "invited_by_id"),
        serialization_alias="invitedById",
    )
    createdAt: datetime = Field(
        ...,
        validation_alias=AliasChoices("createdAt", "created_at"),
        serialization_alias="createdAt",
    )
    updatedAt: datetime = Field(
        ...,
        validation_alias=AliasChoices("updatedAt", "updated_at"),
        serialization_alias="updatedAt",
    )

    class Config:
        populate_by_name = True
        from_attributes = True


class GroupMemberResponse(GroupMembershipResponse):
    """Membership enriched with basic profile data."""

    email: Optional[str] = None
    firstName: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("firstName", "first_name"),
        serialization_alias="firstName",
    )
    lastName: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("lastName", "last_name"),
        serialization_alias="lastName",
    )
