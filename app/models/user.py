"""SQLAlchemy model for application users."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SqlEnum, Integer, String

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
    school = Column(String(100), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


__all__ = ["User", "UserStatus", "AccountType"]
