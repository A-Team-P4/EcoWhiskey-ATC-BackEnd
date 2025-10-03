"""SQLAlchemy model for training contexts."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base


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
        JSONB,  # JSON if you’re storing structured context data; switch to String if it’s plain text
        nullable=False,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        server_default="NOW()",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default="NOW()",
        onupdate=datetime.utcnow,
    )

    # relationships
    user = relationship("User", backref="training_contexts")
