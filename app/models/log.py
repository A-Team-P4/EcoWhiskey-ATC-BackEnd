"""Application logging model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String

from .base import Base


class RequestLog(Base):
    """Persisted application request log entry."""

    __tablename__ = "request_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    method = Column(String(10), nullable=False)
    url = Column(String(2048), nullable=False)
    status_code = Column(Integer, nullable=False)
    client_ip = Column(String(64), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    user = Column(JSON, nullable=True)

__all__ = ["RequestLog"]

