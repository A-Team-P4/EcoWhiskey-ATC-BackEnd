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
    FrequencyValidationResult,
    LlmOutcome,
)
from app.services.context_repository import append_turn

router = APIRouter(prefix="/audio", tags=["audio"])

logger = logging.getLogger(__name__)
transcript_logger = logging.getLogger("app.logs.transcript")


def _derive_feedback_message(outcome: LlmOutcome) -> str:
    warnings = set(outcome.warnings or [])
    slots = outcome.rendered.slots or {}

    if "readback_incomplete" in warnings:
        missing = slots.get("missing_readback_items") or ""
        missing_clean = str(missing).strip().strip(",")
        if missing_clean:
            return f"Colación incompleta. Incluya: {missing_clean}."
        return "Colación incompleta. Repita la instrucción completa."

    if "readback_confirmed" in warnings:
        return "Colación correcta. Continúe."

    if outcome.used_fallback:
        reason = outcome.fallback_reason or "respuesta segura"
        return f"Respuesta generada en modo fallback ({reason}). Repita con mayor claridad."

    return "Colación recibida."


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
    transcript_logger.info(
        "student | session=%s | frequency=%s | text=%s",
        session_id,
        frequency,
        transcript_text,
    )

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
    normalized_frequency = frequency.strip()
    frequency_map = session_context.get("frequency_map") or {}
    scenario_frequency_group = None
    if isinstance(frequency_map, dict):
        scenario_frequency_group = frequency_map.get(normalized_frequency)
        if not scenario_frequency_group:
            try:
                freq_float = float(normalized_frequency)
            except (TypeError, ValueError):
                freq_float = None
            if freq_float is not None:
                for decimals in (1, 2, 3):
                    variant = f"{freq_float:.{decimals}f}"
                    scenario_frequency_group = frequency_map.get(variant)
                    if scenario_frequency_group:
                        break
    if scenario_frequency_group:
        session_context["active_frequency_group"] = scenario_frequency_group
    frequency_check = await validate_frequency_intent(
        transcript=transcript_text,
        frequency=frequency,
    )
    frequency_intents = session_context.get("frequency_intents") or {}
    fallback_intent = None
    if scenario_frequency_group:
        fallback_intent = frequency_intents.get(scenario_frequency_group)
    if scenario_frequency_group and fallback_intent:
        if not frequency_check.is_valid:
            logger.info(
                "Intent detectado %s no coincide con frecuencia %s; aplicando fallback %s",
                frequency_check.intent,
                normalized_frequency,
                fallback_intent,
            )
            frequency_check = FrequencyValidationResult(
                is_valid=True,
                intent=fallback_intent,
                frequency_group=scenario_frequency_group,
                confidence=frequency_check.confidence,
            )
        elif frequency_check.intent is None:
            logger.info(
                "Intent no detectado; usando intent por escenario %s para frecuencia %s",
                fallback_intent,
                normalized_frequency,
            )
            frequency_check = FrequencyValidationResult(
                is_valid=True,
                intent=fallback_intent,
                frequency_group=scenario_frequency_group,
            )
        elif (
            frequency_check.frequency_group is None
            and scenario_frequency_group
        ):
            frequency_check = FrequencyValidationResult(
                is_valid=frequency_check.is_valid,
                intent=frequency_check.intent,
                frequency_group=scenario_frequency_group,
                reason=frequency_check.reason,
                confidence=frequency_check.confidence,
                matched_tokens=frequency_check.matched_tokens,
            )
    speech_text = transcript_text
    llm_request = None
    llm_outcome = None
    feedback_text = "Colación recibida."
    if not frequency_check.is_valid:
        speech_text = frequency_check.reason or transcript_text
        logger.info(
            "Frecuencia inválida session=%s intent=%s freq=%s reason=%s",
            session_id,
            frequency_check.intent,
            frequency,
            frequency_check.reason,
        )
        feedback_text = frequency_check.reason or "Frecuencia incorrecta para esta solicitud."
    elif frequency_check.intent and frequency_check.frequency_group:
        try:
            session_context["active_frequency_group"] = frequency_check.frequency_group
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
            feedback_text = _derive_feedback_message(llm_outcome)
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("Fallo en pipeline LLM, usando transcripción original: %s", exc)
            feedback_text = "No se pudo generar retroalimentación; intente nuevamente."
    else:
        feedback_text = "Colación recibida."

    controller_turn = {
        "role": "controller",
        "text": speech_text,
        "feedback": feedback_text,
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
    transcript_logger.info(
        "controller | session=%s | frequency=%s | intent=%s | fallback=%s | text=%s",
        session_id,
        frequency,
        controller_turn.get("intent") or frequency_check.intent,
        controller_turn.get("fallback_reason") if controller_turn.get("used_fallback") else None,
        speech_text,
    )

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
        "controller_text": speech_text,
        "feedback": feedback_text,
    }
