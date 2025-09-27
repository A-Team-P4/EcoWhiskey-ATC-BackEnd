"""SQLAlchemy model for hello-world demo messages."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, Text

from app.models.base import Base


class HelloMessage(Base):
    __tablename__ = "hello_messages"

    id = Column(Integer, primary_key=True, index=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
