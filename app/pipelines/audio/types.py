"""Typed containers shared across the audio analysis pipeline.

These dataclasses intentionally live in their own module so the other
stages (`context`, `prompts`, `llm`, `flow`) can import them without
creating circular dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from app.services.response_contract import StructuredLlmResponse


@dataclass(frozen=True)
class LlmRequest:
    """Normalized payload handed to the conversational LLM client."""

    transcript: str
    context: Mapping[str, Any]
    intent: str
    frequency: str
    frequency_group: str
    system_prompt: str
    user_prompt: str


@dataclass(frozen=True)
class LlmOutcome:
    """Structured result produced by the LLM stage of the pipeline."""

    response: StructuredLlmResponse
    raw_response: str
