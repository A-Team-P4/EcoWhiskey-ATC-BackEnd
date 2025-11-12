"""Pydantic schemas for scores endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ScoreRecord(BaseModel):
    """Individual score record."""

    id: str = Field(..., description="Unique score record ID")
    phase_id: str = Field(..., description="Phase identifier")
    score: float = Field(..., description="The score value")
    created_at: str = Field(..., description="ISO 8601 timestamp")
    session_id: str = Field(..., description="Associated training session ID")

    class Config:
        from_attributes = True


class PhaseScoreData(BaseModel):
    """Score data aggregated by phase."""

    phase_id: str = Field(..., description="Phase identifier")
    average_score: float = Field(..., description="Average score for this phase")
    total_scores: int = Field(..., description="Total number of score entries")
    scores: list[ScoreRecord] = Field(..., description="Array of individual score records")

    class Config:
        from_attributes = True


class AllPhasesScoresResponse(BaseModel):
    """Response for /scores/phases endpoint."""

    phases: dict[str, PhaseScoreData] = Field(
        ...,
        description="Dictionary with phase IDs as keys and phase score data as values"
    )

    class Config:
        from_attributes = True
