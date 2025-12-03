"""Prompt construction stage for the audio analysis pipeline.

Stage **03** transforms the raw transcript + context information into
the system/user prompts consumed by the conversational LLM.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from app.services.prompt_builder import PromptContext, build_prompt

from .types import LlmRequest

logger = logging.getLogger("app.services.audio_pipeline")


def _extract_controller_role(phase: Mapping[str, Any] | None) -> str | None:
    if not isinstance(phase, Mapping):
        return None
    llm_section = phase.get("llm")
    if isinstance(llm_section, Mapping):
        role = llm_section.get("role")
        if isinstance(role, str) and role.strip():
            return role.strip()
    controller = phase.get("controller")
    if isinstance(controller, Mapping):
        role = controller.get("role")
        if isinstance(role, str) and role.strip():
            return role.strip()
    return None


def _truncate(value: str, max_length: int = 240) -> str:
    if len(value) <= max_length:
        return value
    return value[: max_length - 3] + "..."


def build_llm_request(
    transcript: str,
    context: Mapping[str, Any],
    *,
    phase: Mapping[str, Any] | None,
    intent: str,
    frequency: str,
    frequency_group: str,
    difficulty: int = 2,
):
    """Assemble prompts and metadata for the LLM invocation."""

    prompt_context = PromptContext(
        frequency_group=frequency_group,
        airport=context.get("airport", "MRPV"),
        phase_id=phase.get("id") if isinstance(phase, Mapping) else None,
        phase_name=phase.get("name") if isinstance(phase, Mapping) else None,
        controller_role=_extract_controller_role(phase),
        recent_turns=context.get("recent_turns"),
        difficulty=difficulty,
    )

    prompt_bundle = build_prompt(
        intent=intent,
        context=prompt_context,
        transcript=transcript,
        scenario=context.get("scenario"),
        phase=phase,
        turn_history=context.get("turn_history"),
    )

    logger.info(
        "Prompts generados intent=%s freq_group=%s\nSYSTEM> %s\nUSER> %s",
        intent,
        frequency_group,
        _truncate(prompt_bundle.system_prompt, 500),
        _truncate(prompt_bundle.user_prompt, 500),
    )

    return LlmRequest(
        transcript=transcript,
        context=context,
        intent=intent,
        frequency=frequency,
        frequency_group=frequency_group,
        system_prompt=prompt_bundle.system_prompt,
        user_prompt=prompt_bundle.user_prompt,
    )


__all__ = ["build_llm_request"]
