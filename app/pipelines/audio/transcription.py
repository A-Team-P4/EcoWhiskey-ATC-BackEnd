"""Transcription stage (Stage 02) of the audio pipeline."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import HTTPException, status

from app.services import TranscriptionError, get_transcribe_service

logger = logging.getLogger("app.services.audio_pipeline")

_TRANSCRIBE_SERVICE = get_transcribe_service()


async def transcribe_audio(
    session_id: UUID,
    audio_bytes: bytes,
    content_type: str,
) -> str:
    """Delegate to the transcription microservice and surface FastAPI-friendly errors."""

    try:
        result = await _TRANSCRIBE_SERVICE.transcribe_session_audio(
            session_id=session_id,
            audio_bytes=audio_bytes,
            content_type=content_type,
        )
    except TranscriptionError as exc:  # pragma: no cover - integration failure
        logger.exception("Fallo en transcripción", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    
    return result.transcript


__all__ = ["transcribe_audio"]
