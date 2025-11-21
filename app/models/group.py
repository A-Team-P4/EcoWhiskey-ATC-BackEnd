"""SQLAlchemy model defining student groups."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base


class Group(Base):
    """Represents an instructor-managed group scoped to an academy."""

    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    school_id = Column(
        Integer,
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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

    __table_args__ = (
        UniqueConstraint(
            "school_id",
            "name",
            name="uq_groups_school_name",
        ),
    )

    school = relationship("School", back_populates="groups")
    owner = relationship(
        "User",
        back_populates="owned_groups",
        foreign_keys=[owner_id],
    )
    memberships = relationship(
        "GroupMembership",
        back_populates="group",
        cascade="all, delete-orphan",
    )


__all__ = ["Group"]
