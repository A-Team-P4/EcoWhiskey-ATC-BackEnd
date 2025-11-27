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
    feedback_text: Optional[str] = Field(default="", alias="feedback")
    confidence: Optional[float] = None
    score: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True, "extra": "allow"}

    @model_validator(mode="after")
    def normalize_confidence(cls, values: "StructuredLlmResponse") -> "StructuredLlmResponse":
        if values.confidence is not None:
            values.confidence = max(0.0, min(1.0, float(values.confidence)))
        if values.score is not None:
            values.score = max(0.0, min(100.0, float(values.score)))
        if values.feedback_text is None:
            values.feedback_text = ""
        return values

    @classmethod
    def from_json(cls, payload: str) -> "StructuredLlmResponse":
        cleaned = _clean_json_payload(payload)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValidationError.from_exception_data(
                "StructuredLlmResponse",
                line_errors=[{"type": "value_error", "loc": ("__root__",), "msg": str(exc), "input": payload}],
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
        cleaned = _clean_json_payload(payload)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValidationError.from_exception_data(
                "IntentClassificationResponse",
                line_errors=[{"type": "value_error", "loc": ("__root__",), "msg": str(exc), "input": payload}],
            )
        return cls.model_validate(data)


def _clean_json_payload(payload: str) -> str:
    """Strip Markdown code blocks and find the first/last brace to extract JSON."""
    if not payload:
        return ""
    
    # Remove markdown code blocks if present
    cleaned = payload.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
        
    cleaned = cleaned.strip()
    
    # Find the first '{' and last '}'
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start : end + 1]
        
    return cleaned


__all__ = [
    "StructuredLlmResponse",
    "IntentClassificationResponse",
    "ResponseContractError",
]
