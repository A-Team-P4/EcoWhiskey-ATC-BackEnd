"""Pydantic models for validating LLM JSON responses.

Both the conversational pipeline and any future classifiers run through these
schemas so that downstream code receives normalized, type-safe objects.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, ValidationError, model_validator


class StructuredLlmResponse(BaseModel):
    intent: str
    allow_response: bool = Field(alias="allowResponse")
    controller_text: Optional[str] = Field(default=None, alias="controllerText")
    feedback_text: str = Field(alias="feedback")
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True, "extra": "allow"}

    @model_validator(mode="after")
    def normalize_confidence(cls, values: "StructuredLlmResponse") -> "StructuredLlmResponse":
        if values.confidence is not None:
            values.confidence = max(0.0, min(1.0, float(values.confidence)))
        return values

    @classmethod
    def from_json(cls, payload: str) -> "StructuredLlmResponse":
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValidationError.from_exception_data(
                "StructuredLlmResponse",
                excs=[{"type": "json_decode_error", "loc": ("__root__",), "msg": str(exc), "input": payload}],
            )
        return cls.model_validate(data)


class ResponseContractError(RuntimeError):
    """Raised when the LLM response contract cannot be validated."""


class IntentClassificationResponse(BaseModel):
    intent: str
    confidence: Optional[float] = None
    frequency_group: Optional[str] = Field(default=None, alias="frequencyGroup")

    @model_validator(mode="after")
    def normalize_confidence(cls, values: "IntentClassificationResponse") -> "IntentClassificationResponse":
        if values.confidence is not None:
            values.confidence = max(0.0, min(1.0, float(values.confidence)))
        return values

    @classmethod
    def from_json(cls, payload: str) -> "IntentClassificationResponse":
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValidationError.from_exception_data(
                "IntentClassificationResponse",
                excs=[{"type": "json_decode_error", "loc": ("__root__",), "msg": str(exc), "input": payload}],
            )
        return cls.model_validate(data)


__all__ = [
    "StructuredLlmResponse",
    "IntentClassificationResponse",
    "ResponseContractError",
]
