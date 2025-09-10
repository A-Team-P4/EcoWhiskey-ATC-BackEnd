from typing import Optional, List
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


class Aircraft(BaseModel):
    """Domain model for Aircraft entity"""
    id: Optional[int] = None
    registration: str
    model: str
    manufacturer: str
    year: int
    capacity: int
    status: str = "available"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Flight(BaseModel):
    """Domain model for Flight entity"""
    id: Optional[int] = None
    flight_number: str
    aircraft_id: int
    origin: str
    destination: str
    departure_time: datetime
    arrival_time: datetime
    status: str = "scheduled"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True