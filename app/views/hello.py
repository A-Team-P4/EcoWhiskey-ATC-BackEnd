"""Pydantic schemas for hello-world messages."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HelloMessageCreate(BaseModel):
    message: str


class HelloMessageRead(BaseModel):
    id: int
    message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
