from typing import Optional

from pydantic import BaseModel
from datetime import datetime
from enum import Enum


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class User(BaseModel):
    """Domain model for User entity"""

    id: Optional[int] = None
    email: str
    username: str
    full_name: str
    status: UserStatus = UserStatus.ACTIVE
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

