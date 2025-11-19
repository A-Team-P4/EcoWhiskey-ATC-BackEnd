"""Conversational LLM stage for the audio analysis pipeline (Stage 04)."""

from __future__ import annotations

import logging

from pydantic import ValidationError

from app.services.llm_client import BedrockLlmClient
from app.services.response_contract import ResponseContractError, StructuredLlmResponse

from .types import LlmOutcome, LlmRequest

logger = logging.getLogger("app.services.audio_pipeline")

_LLM_CLIENT = BedrockLlmClient()
_MAX_JSON_RETRIES = 2  # Re-intentos cuando el LLM devuelve JSON inválido.


def _truncate(value: str, max_length: int = 500) -> str:
    if len(value) <= max_length:
        return value
    return value[: max_length - 3] + "..."


async def call_conversation_llm(request: LlmRequest) -> LlmOutcome:
    """Invoke the LLM, validate the response contract, and render the phrase."""

    last_error: ValidationError | None = None
    for attempt in range(_MAX_JSON_RETRIES + 1):
        raw_response = await _LLM_CLIENT.invoke(
            system_prompt=request.system_prompt,
            user_prompt=request.user_prompt,
        )
        if not raw_response:
            raise ResponseContractError("LLM devolvió una respuesta vacía.")

        logger.info(
            "Respuesta LLM cruda intent=%s intento=%s: %s",
            request.intent,
            attempt + 1,
            _truncate(raw_response, 500),
        )

        try:
            structured = StructuredLlmResponse.from_json(raw_response)
        except ValidationError as exc:
            last_error = exc
            logger.warning(
                "LLM produjo JSON inválido intent=%s intento=%s: %s",
                request.intent,
                attempt + 1,
                exc,
            )
            if attempt < _MAX_JSON_RETRIES:
                continue
            raise ResponseContractError(
                "El LLM devolvió un JSON inválido incluso tras reintentar."
            ) from exc

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

    # This point should be unreachable because the loop either returns or raises.
    raise ResponseContractError("No se pudo obtener una respuesta válida.") from last_error


__all__ = ["call_conversation_llm"]
