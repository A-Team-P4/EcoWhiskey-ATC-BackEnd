"""TTS synthesis stage (Stage 08) of the audio pipeline."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import HTTPException, status

from app.services import (
    RadioTtsError,
    StorageError,
    get_radio_tts_service,
    upload_readback_audio,
)

logger = logging.getLogger("app.services.audio_pipeline")

_RADIO_TTS_SERVICE = get_radio_tts_service()


async def synthesize_controller_audio(
    session_id: UUID,
    controller_text: str,
    allow_response: bool,
) -> str | None:
    """Generate controller audio via Polly/Radio TTS and upload it."""

    text = controller_text.strip()
    if not allow_response or not text:
        return None

    try:
        readback = await _RADIO_TTS_SERVICE.synthesize_readback(text)
    except RadioTtsError as exc:  # pragma: no cover - integration failure
        logger.exception("Fallo en Radio TTS", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    try:
        _, audio_url = await upload_readback_audio(
            session_id,
            readback.audio_bytes,
            content_type=readback.media_type,
            extension="wav",
        )
    except StorageError as exc:  # pragma: no cover - integration failure
        logger.exception("Fallo al subir audio sintetizado", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return audio_url


__all__ = ["synthesize_controller_audio"]
