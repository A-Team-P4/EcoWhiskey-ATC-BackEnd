from datetime import datetime
from typing import Any, Dict, Optional
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


class LastControllerTurnResponse(BaseModel):
    """Response schema for the last controller turn in a training session."""

    session_id: UUID = Field(
        ..., description="Training session identifier", alias="session_id"
    )
    frequency: Optional[str] = Field(
        None, description="Frequency from the previous turn"
    )
    controller_text: Optional[str] = Field(
        None, description="Controller text from the last controller turn", alias="controller_text"
    )
    feedback: Optional[str] = Field(
        None, description="Feedback from the last controller turn"
    )
    session_completed: bool = Field(
        False, description="Whether the session is completed", alias="session_completed"
    )

    class Config:
        populate_by_name = True
