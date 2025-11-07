"""Conversational LLM stage for the audio analysis pipeline (Stage 04)."""

from __future__ import annotations

import logging

from app.services.llm_client import BedrockLlmClient
from app.services.response_contract import ResponseContractError, StructuredLlmResponse

from .types import LlmOutcome, LlmRequest

logger = logging.getLogger("app.services.audio_pipeline")

_LLM_CLIENT = BedrockLlmClient()


def _truncate(value: str, max_length: int = 500) -> str:
    if len(value) <= max_length:
        return value
    return value[: max_length - 3] + "..."


async def call_conversation_llm(request: LlmRequest) -> LlmOutcome:
    """Invoke the LLM, validate the response contract, and render the phrase."""

    raw_response = await _LLM_CLIENT.invoke(
        system_prompt=request.system_prompt,
        user_prompt=request.user_prompt,
    )
    if not raw_response:
        raise ResponseContractError("LLM devolvió una respuesta vacía.")

    logger.info(
        "Respuesta LLM cruda intent=%s: %s",
        request.intent,
        _truncate(raw_response, 500),
    )

    structured = StructuredLlmResponse.from_json(raw_response)
    if structured.intent and structured.intent != request.intent:
        logger.info(
            "Intent devuelto por el LLM (%s) difiere del esperado (%s)",
            structured.intent,
            request.intent,
        )
    return LlmOutcome(
        response=structured,
        raw_response=raw_response,
    )


__all__ = ["call_conversation_llm"]
