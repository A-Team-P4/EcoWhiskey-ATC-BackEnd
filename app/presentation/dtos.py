from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from app.domain.models import UserStatus


class UserCreateRequest(BaseModel):
    """Request DTO for creating a user"""
    email: EmailStr
    full_name: str
    username: Optional[str] = None


class UserUpdateRequest(BaseModel):
    """Request DTO for updating a user"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    username: Optional[str] = None
    status: Optional[UserStatus] = None


class UserResponse(BaseModel):
    """Response DTO for user"""
    id: int
    email: str
    username: str
    full_name: str
    status: str
    created_at: datetime
    updated_at: datetime


class AircraftCreateRequest(BaseModel):
    """Request DTO for creating an aircraft"""
    registration: str
    model: str
    manufacturer: str
    year: int
    capacity: int


class AircraftResponse(BaseModel):
    """Response DTO for aircraft"""
    id: int
    registration: str
    model: str
    manufacturer: str
    year: int
    capacity: int
    status: str
    created_at: datetime
    updated_at: datetime


class FlightCreateRequest(BaseModel):
    """Request DTO for creating a flight"""
    aircraft_id: int
    origin: str
    destination: str
    departure_time: datetime
    arrival_time: datetime
    flight_number: Optional[str] = None


class FlightUpdateRequest(BaseModel):
    """Request DTO for updating a flight"""
    status: str


class FlightResponse(BaseModel):
    """Response DTO for flight"""
    id: int
    flight_number: str
    aircraft_id: int
    origin: str
    destination: str
    departure_time: datetime
    arrival_time: datetime
    status: str
    created_at: datetime
    updated_at: datetime


class ErrorResponse(BaseModel):
    """Response DTO for errors"""
    detail: str
    code: Optional[str] = None


class SuccessResponse(BaseModel):
    """Response DTO for success messages"""
    message: str
    data: Optional[dict] = None