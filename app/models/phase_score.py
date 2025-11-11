"""SQLAlchemy model for phase scores."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class PhaseScore(Base):
    __tablename__ = "phase_scores"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    training_session_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    user_id = Column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    phase_id = Column(
        String,
        nullable=False,
        index=True,
    )
    score = Column(
        Float,
        nullable=False,
    )
    feedback = Column(
        String,
        nullable=True,
    )
    created_at = Column(
        DateTime,
        nullable=False,
        server_default="NOW()",
    )

    # relationships
    user = relationship("User", backref="phase_scores")
