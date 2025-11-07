"""Intent detection helpers for the audio pipeline (Stage 04 pre-check)."""

from __future__ import annotations

import logging
from typing import Any, Mapping

from app.services.llm_client import BedrockLlmClient, LlmInvocationError
from app.services.response_contract import IntentClassificationResponse

logger = logging.getLogger("app.services.audio_pipeline")

_CLASSIFIER_CLIENT = BedrockLlmClient()
_SYSTEM_PROMPT = (
    "Eres un instructor de control de tránsito aéreo en Costa Rica (MRPV). "
    "Analiza transmisiones del alumno y clasifica la intención. "
    "Responde únicamente en JSON con los campos intent, confidence y frequencyGroup "
    "(ground, tower, approach o radar)."
)


async def classify_intent(
    transcript: str,
    session_context: Mapping[str, Any],
) -> IntentClassificationResponse | None:
    """Use the conversational LLM to guess the student's intent + frequency group."""

    if not transcript.strip():
        return None

    frequency_map = session_context.get("frequencies")
    frequency_lines = ""
    if isinstance(frequency_map, Mapping) and frequency_map:
        hints = [f"- {key}: {value}" for key, value in frequency_map.items()]
        frequency_lines = "\nFrecuencias conocidas:\n" + "\n".join(hints)

    user_prompt = (
        "Transcripción del alumno:\n"
        f"{transcript.strip()}\n\n"
        "Indica la intención en snake_case (por ejemplo: tower_takeoff_clearance, ground_taxi_clearance) "
        "y el grupo de frecuencia adecuado.\n"
        "Devuelve exclusivamente JSON con la forma "
        '{"intent": "...", "confidence": 0-1, "frequencyGroup": "tower|ground|approach|radar"}.\n'
        f"{frequency_lines}"
    )

    try:
        raw_response = await _CLASSIFIER_CLIENT.invoke(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
    except LlmInvocationError as exc:  # pragma: no cover - transport failure
        logger.warning("Intent detector invocation failed: %s", exc)
        return None

    if not raw_response:
        return None

    try:
        return IntentClassificationResponse.from_json(raw_response)
    except Exception as exc:  # pragma: no cover - validation issues
        logger.warning("Intent detector invalid JSON: %s raw=%s", exc, raw_response)
        return None


__all__ = ["classify_intent"]
