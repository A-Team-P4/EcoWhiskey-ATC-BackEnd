"""SQLAlchemy model for application users."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, Text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.models.base import Base


class UserStatus(str, Enum):
    """Enumeration of valid user lifecycle states."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class AccountType(str, Enum):
    """Enumeration of supported user account types."""

    STUDENT = "student"
    INSTRUCTOR = "instructor"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    password_hash = Column(String(256), nullable=False)
    status = Column(
        SqlEnum(UserStatus, name="user_status"),
        nullable=False,
        default=UserStatus.ACTIVE,
    )
    account_type = Column(
        SqlEnum(AccountType, name="account_type"),
        nullable=False,
    )
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="SET NULL"), nullable=True)
    school = relationship("School", back_populates="users", lazy="joined")
    owned_groups = relationship(
        "Group",
        back_populates="owner",
        cascade="all, delete-orphan",
        foreign_keys="Group.owner_id",
    )
    group_memberships = relationship(
        "GroupMembership",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="GroupMembership.user_id",
    )
    photo = Column(Text, nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        server_default="NOW()",  # Use PostgreSQL's NOW() function
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default="NOW()",  # Use PostgreSQL's NOW() function
        onupdate=datetime.utcnow,  # Keep this for updates
    )


__all__ = ["User", "UserStatus", "AccountType"]
