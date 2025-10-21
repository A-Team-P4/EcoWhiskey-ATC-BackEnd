"""Pydantic schemas for School resources."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SchoolCreateRequest(BaseModel):
    """Payload for creating a new School."""

    name: str = Field(..., min_length=1, max_length=120)
    value: str = Field(..., min_length=1, max_length=20)
    location: str = Field(..., min_length=1, max_length=120)


class SchoolUpdateRequest(BaseModel):
    """Payload for updating an existing School."""

    name: str | None = Field(None, min_length=1, max_length=120)
    value: str | None = Field(None, min_length=1, max_length=20)
    location: str | None = Field(None, min_length=1, max_length=120)


class SchoolResponse(BaseModel):
    """Serialized representation of a School."""

    id: int
    name: str = Field(..., max_length=120)
    value: str = Field(..., max_length=20)
    location: str = Field(..., max_length=120)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


__all__ = ["SchoolCreateRequest", "SchoolUpdateRequest", "SchoolResponse"]
