"""Pydantic models for validating LLM JSON responses."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError, model_validator


class SlotsPayload(BaseModel):
    callsign: Optional[str] = Field(default=None)
    callsign_spelled: Optional[str] = Field(default=None)
    runway: Optional[str] = Field(default=None)
    runway_human: Optional[str] = Field(default=None)
    instruction_code: Optional[str] = Field(default=None)
    instruction: Optional[str] = Field(default=None)
    heading: Optional[int] = Field(default=None)
    altitude_ft: Optional[int] = Field(default=None, alias="altitudeFt")

    model_config = {"populate_by_name": True, "extra": "allow"}


class NotesPayload(BaseModel):
    observations: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(
        default_factory=list, alias="missingInformation"
    )
    frequency_group: Optional[str] = Field(default=None, alias="frequencyGroup")

    model_config = {"populate_by_name": True, "extra": "allow"}


class StructuredLlmResponse(BaseModel):
    intent: str
    confidence: Optional[float] = None
    slots: SlotsPayload
    notes: Optional[NotesPayload] = None

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
