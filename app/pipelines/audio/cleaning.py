"""ASR Transcription cleaning stage.

This module provides a specialized function to "clean" raw ASR transcripts
using a lightweight LLM. It focuses on correcting number formatting (e.g.,
"10" -> "uno cero") and standardizing aviation phraseology.
"""

from __future__ import annotations

import logging

from app.config.settings import settings
from app.services.llm_client import BedrockLlmClient

logger = logging.getLogger("app.services.audio_pipeline")

_LLM_CLIENT = BedrockLlmClient()

_CLEANING_SYSTEM_PROMPT = """Eres un experto en fraseología aeronáutica. Tu única tarea es corregir la transcripción de audio de un piloto o controlador.

REGLAS:
1. Convierte números a dígitos individuales escritos en palabras (ej: "10" -> "uno cero", "3000" -> "tres mil").
2. Corrige términos aeronáuticos mal interpretados.
3. NO agregues puntuación, saludos ni explicaciones.
4. Devuelve SOLAMENTE el texto corregido.

Ejemplos:
Input: "ascender a 10 mil pies"
Output: "ascender a uno cero mil pies"

Input: "pista 10"
Output: "pista uno cero"

Input: "rumbo 3 6 0"
Output: "rumbo tres seis cero"

Input: "al.de espera"
Output: "al punto de espera"
"""


async def clean_transcription(transcript: str) -> str:
    """Correct ASR errors and format numbers using a fast LLM."""
    
    if not transcript or not transcript.strip():
        return transcript

    try:
        cleaned = await _LLM_CLIENT.invoke(
            system_prompt=_CLEANING_SYSTEM_PROMPT,
            user_prompt=transcript,
            model_id=settings.bedrock.cleaning_model_id,
            max_tokens=settings.bedrock.cleaning_max_tokens,
            temperature=0.0,
        )
        return cleaned.strip() if cleaned else transcript
    except Exception as exc:
        logger.warning("Fallo en limpieza de transcripción: %s", exc)
        return transcript
