"""SQLAlchemy model for group memberships."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.models.base import Base


class GroupRole(str, Enum):
    """Role the member plays inside the group."""

    INSTRUCTOR = "instructor"
    STUDENT = "student"


class GroupMembershipStatus(str, Enum):
    """Lifecycle of a membership/invitation."""

    INVITED = "invited"
    ACTIVE = "active"


class GroupMembership(Base):
    """Association table between users and groups."""

    __tablename__ = "group_memberships"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(
        Integer,
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(
        SqlEnum(GroupRole, name="group_role"),
        nullable=False,
    )
    status = Column(
        SqlEnum(GroupMembershipStatus, name="group_membership_status"),
        nullable=False,
        default=GroupMembershipStatus.ACTIVE,
    )
    invited_by_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(
        DateTime,
        nullable=False,
        server_default="NOW()",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default="NOW()",
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        UniqueConstraint(
            "group_id",
            "user_id",
            name="uq_group_memberships_group_user",
        ),
    )

    group = relationship("Group", back_populates="memberships")
    user = relationship("User", back_populates="group_memberships", foreign_keys=[user_id])
    invited_by = relationship("User", foreign_keys=[invited_by_id])


__all__ = ["GroupMembership", "GroupRole", "GroupMembershipStatus"]
