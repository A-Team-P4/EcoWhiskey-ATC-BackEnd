"""Audio analysis endpoints."""

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

_ALLOWED_CONTENT_TYPES: Final[set[str]] = {"audio/mpeg", "audio/mp3"}

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
    """Transcribe an uploaded MP3 file and generate a Polly readback."""

    if audio_file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only MP3 audio files are supported",
        )

    audio_bytes = await audio_file.read()
    content_type = audio_file.content_type or "audio/mpeg"
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
