"""Common response schemas."""

from typing import Optional

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None


class SuccessResponse(BaseModel):
    message: str
    data: Optional[dict] = None
