"""SQLAlchemy model representing educational institutions."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.models.base import Base


class School(Base):
    __tablename__ = "schools"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False, unique=True, index=True)
    value = Column(String(20), nullable=False, unique=True, index=True)
    location = Column(String(120), nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    users = relationship("User", back_populates="school")
    groups = relationship(
        "Group",
        back_populates="school",
        cascade="all, delete-orphan",
    )


__all__ = ["School"]
