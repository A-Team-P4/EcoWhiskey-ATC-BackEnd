from uuid import UUID
from typing import Any, Dict

from pydantic import BaseModel, Field


class TrainingContextRequest(BaseModel):
    """Request schema for creating a training context."""

    context: Dict[str, Any] = Field(
        ..., description="Structured training context provided by the user"
    )


class TrainingContextResponse(BaseModel):
    """Response schema for training context creation."""

    trainingSessionId: UUID = Field(
        ..., description="Unique training session identifier", alias="trainingSessionId"
    )
    context: Dict[str, Any] = Field(
        ..., description="The structured training context data"
    )

    class Config:
        populate_by_name = True
