from datetime import datetime
from typing import Any, Dict
from uuid import UUID

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
        ..., description="Structured training context payload as persisted"
    )

    class Config:
        populate_by_name = True


class TrainingContextHistoryItem(BaseModel):
    """History entry describing a persisted training context."""

    trainingSessionId: UUID = Field(
        ..., description="Unique training session identifier", alias="trainingSessionId"
    )
    context: Dict[str, Any] = Field(
        ..., description="Structured training context payload as persisted"
    )
    createdAt: datetime = Field(
        ..., description="Timestamp when the context was created", alias="createdAt"
    )
    updatedAt: datetime = Field(
        ..., description="Timestamp when the context was last updated", alias="updatedAt"
    )

    class Config:
        populate_by_name = True
