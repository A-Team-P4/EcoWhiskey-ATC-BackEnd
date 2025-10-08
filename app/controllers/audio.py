"""Audio analysis endpoints."""

import mimetypes
from typing import Any, Final
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.controllers.dependencies import CurrentUserDep
from app.services import (
    RadioTtsError,
    StorageError,
    TranscriptionError,
    get_radio_tts_service,
    get_transcribe_service,
    upload_readback_audio,
)

router = APIRouter(prefix="/audio", tags=["audio"])

_ALLOWED_CONTENT_TYPES: Final[set[str]] = {
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/x-m4a",
    "audio/m4a",
}

_transcribe_service = get_transcribe_service()
_radio_tts_service = get_radio_tts_service()

_SESSION_ID_FORM = Form(...)
_AUDIO_FILE_UPLOAD = File(...)


@router.post("/analyze")
async def analyze_audio(
    _current_user: CurrentUserDep,
    session_id: UUID = _SESSION_ID_FORM,
    audio_file: UploadFile = _AUDIO_FILE_UPLOAD,
) -> dict[str, Any]:
    """Transcribe an uploaded MP3 or M4A file and generate a Polly readback."""

    content_type = audio_file.content_type
    if not content_type and audio_file.filename:
        guessed_type, _ = mimetypes.guess_type(audio_file.filename)
        content_type = guessed_type

    if not content_type:
        content_type = "audio/mpeg"

    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only MP3 or M4A audio files are supported",
        )

    audio_bytes = await audio_file.read()
    await audio_file.close()

    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded audio file is empty",
        )

    try:
        result = await _transcribe_service.transcribe_session_audio(
            session_id=session_id,
            audio_bytes=audio_bytes,
            content_type=content_type,
        )
    except TranscriptionError as exc:  # pragma: no cover - integration failure
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    try:
        readback = await _radio_tts_service.synthesize_readback(result.transcript)
    except RadioTtsError as exc:  # pragma: no cover - integration failure
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    try:
        object_key, audio_url = await upload_readback_audio(
            session_id,
            readback.audio_bytes,
            content_type=readback.media_type,
            extension="wav",
        )
    except StorageError as exc:  # pragma: no cover - integration failure
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return {
        "session_id": str(session_id),
        "audio_url": audio_url,
    }
