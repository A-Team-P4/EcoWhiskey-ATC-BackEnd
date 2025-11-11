"""SQLAlchemy model for training contexts."""

from __future__ import annotations

import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base


def get_costa_rica_now():
    """Get current time in Costa Rica timezone."""
    return datetime.now(ZoneInfo("America/Costa_Rica"))


class TrainingContext(Base):
    __tablename__ = "training_contexts"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    training_session_id = Column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        default=uuid.uuid4,
    )
    user_id = Column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    context = Column(
        JSONB,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=get_costa_rica_now,
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=get_costa_rica_now,
        onupdate=get_costa_rica_now,
    )

    # relationships
    user = relationship("User", backref="training_contexts")
