"""Audio analysis endpoints."""

import logging
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
from app.services.audio_pipeline import (
    build_llm_request,
    call_conversation_llm,
    fetch_session_context,
    render_response_text,
    validate_frequency_intent,
)
from app.services.context_repository import append_turn

router = APIRouter(prefix="/audio", tags=["audio"])

logger = logging.getLogger(__name__)

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
_FREQUENCY_FORM = Form(...)
_AUDIO_FILE_UPLOAD = File(...)


@router.post("/analyze")
async def analyze_audio(
    #_current_user: CurrentUserDep,
    session_id: UUID = _SESSION_ID_FORM,
    frequency: str = _FREQUENCY_FORM,
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

    transcript_text = result.transcript
    logger.info("Transcripción recibida session=%s: %s", session_id, transcript_text)

    session_context = await fetch_session_context(session_id)
    student_turn = {
        "role": "student",
        "text": transcript_text,
        "frequency": frequency,
    }
    await append_turn(session_id, student_turn)

    # Actualizamos el contexto in-memory para incluir el turno recién agregado.
    recent_turns = list(session_context.get("recent_turns", []))
    recent_turns.append(student_turn)
    session_context = dict(session_context)
    session_context["recent_turns"] = recent_turns[-8:]
    frequency_check = await validate_frequency_intent(
        transcript=transcript_text,
        frequency=frequency,
    )
    speech_text = transcript_text
    llm_request = None
    llm_outcome = None
    if frequency_check.intent and frequency_check.frequency_group:
        try:
            llm_request = await build_llm_request(
                transcript=transcript_text,
                context=session_context,
                intent=frequency_check.intent,
                frequency=frequency,
                frequency_group=frequency_check.frequency_group,
            )
            llm_outcome = await call_conversation_llm(llm_request)
            speech_text = await render_response_text(
                llm_outcome,
                fallback_transcript=transcript_text,
            )
            logger.info(
                "Frase final para Polly session=%s intent=%s fallback=%s: %s",
                session_id,
                llm_request.intent,
                llm_outcome.used_fallback,
                speech_text,
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("Fallo en pipeline LLM, usando transcripción original: %s", exc)

    controller_turn = {
        "role": "controller",
        "text": speech_text,
    }
    if llm_request and llm_outcome:
        controller_turn.update(
            {
                "intent": llm_request.intent,
                "used_fallback": llm_outcome.used_fallback,
                "fallback_reason": llm_outcome.fallback_reason,
            }
        )
    await append_turn(session_id, controller_turn)

    try:
        readback = await _radio_tts_service.synthesize_readback(speech_text)
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
        "frequency": frequency,
        "audio_url": audio_url,
        "feedback": speech_text,
    }
