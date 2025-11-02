"""Audio analysis endpoints."""

import logging
import mimetypes
from typing import Any, Final, Mapping, Sequence
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
    LlmOutcome,
)
from app.services.context_repository import append_turn, MAX_TURNS_STORED

router = APIRouter(prefix="/audio", tags=["audio"])

logger = logging.getLogger(__name__)
transcript_logger = logging.getLogger("app.logs.transcript")


def _build_storage_context(
    session_context: Mapping[str, Any],
    turn_history: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    base: dict[str, Any] = {}
    context_base = session_context.get("context_base")
    if isinstance(context_base, Mapping):
        base.update(context_base)

    for key in (
        "scenario_id",
        "scenario",
        "meteo",
        "route",
        "objectives",
        "default_frequency_group",
        "frequencies",
        "transponder",
        "squawk",
        "phase_id",
    ):
        if key in session_context and session_context[key] is not None:
            value = session_context[key]
            if key == "scenario" and isinstance(value, Mapping):
                scenario_copy = dict(value)
                scenario_copy.pop("_phase_map", None)
                base[key] = scenario_copy
            else:
                base[key] = value

    base["turns"] = [
        dict(turn) if isinstance(turn, Mapping) else turn
        for turn in turn_history
    ]
    return base


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
    _current_user: CurrentUserDep,
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
    turn_history = list(session_context.get("turn_history", []))
    turn_history = turn_history[-MAX_TURNS_STORED:]
    session_context["turn_history"] = turn_history
    base_context_before_student = _build_storage_context(session_context, turn_history)

    student_turn = {
        "role": "student",
        "text": transcript_text,
        "frequency": frequency,
    }
    if session_context.get("meteo") and "meteo" not in student_turn:
        student_turn["meteo"] = session_context["meteo"]
    if session_context.get("route"):
        student_turn["route"] = session_context["route"]
    turn_history.append(student_turn)
    turn_history = turn_history[-MAX_TURNS_STORED:]
    session_context = dict(session_context)
    session_context["turn_history"] = turn_history
    recent_turns = turn_history[-8:]
    session_context["recent_turns"] = recent_turns
    await append_turn(
        session_id,
        student_turn,
        user_id=_current_user.id,
        base_context=base_context_before_student,
    )
    session_context["context_base"] = _build_storage_context(
        session_context,
        turn_history,
    )
    normalized_frequency = frequency.strip()
    frequency_map = session_context.get("frequency_map") or {}
    observed_frequency_group = None
    if isinstance(frequency_map, dict) and normalized_frequency:
        observed_frequency_group = frequency_map.get(normalized_frequency)
        if not observed_frequency_group:
            try:
                freq_float = float(normalized_frequency)
            except (TypeError, ValueError):
                freq_float = None
            if freq_float is not None:
                for decimals in (1, 2, 3):
                    variant = f"{freq_float:.{decimals}f}"
                    observed_frequency_group = frequency_map.get(variant)
                    if observed_frequency_group:
                        break
    if observed_frequency_group:
        session_context["active_frequency_group"] = observed_frequency_group

    current_phase = session_context.get("phase")
    if not isinstance(current_phase, Mapping):
        logger.error("No hay fase activa para session=%s", session_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No hay fase activa configurada para la sesión.",
        )

    phase_intent = current_phase.get("intent")
    if not phase_intent:
        logger.error("Fase sin intent definido session=%s phase=%s", session_id, current_phase)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La fase activa no tiene un intent configurado.",
        )

    phase_frequency_group = (
        current_phase.get("frequency")
        or session_context.get("active_frequency_group")
        or session_context.get("default_frequency_group")
    )
    if not phase_frequency_group:
        phase_frequency_group = observed_frequency_group or "tower"
    session_context["active_frequency_group"] = phase_frequency_group

    frequencies = session_context.get("frequencies")
    expected_frequency_value = None
    if isinstance(frequencies, Mapping):
        expected_frequency_value = frequencies.get(phase_frequency_group)

    logger.info(
        "Fase activa session=%s phase_id=%s intent=%s freq=%s",
        session_id,
        session_context.get("phase_id"),
        phase_intent,
        phase_frequency_group,
    )

    phase_payload: dict[str, Any] = (
        dict(current_phase) if isinstance(current_phase, Mapping) else {}
    )
    if expected_frequency_value:
        phase_payload.setdefault("expected_frequency", expected_frequency_value)
    if normalized_frequency:
        phase_payload.setdefault("received_frequency", normalized_frequency)
    if observed_frequency_group and observed_frequency_group != phase_frequency_group:
        phase_payload.setdefault("observed_frequency_group", observed_frequency_group)

    allow_response = False
    controller_text = ""
    feedback_text = "Colación recibida."
    response_intent = phase_intent
    response_confidence = None
    response_metadata: dict[str, Any] = {}
    llm_outcome: LlmOutcome | None = None

    try:
        llm_request = await build_llm_request(
            transcript=transcript_text,
            context=session_context,
            phase=phase_payload,
            intent=phase_intent,
            frequency=frequency,
            frequency_group=phase_frequency_group,
        )
        llm_outcome = await call_conversation_llm(llm_request)
        structured = llm_outcome.response
        allow_response = bool(structured.allow_response)
        controller_text = (structured.controller_text or "").strip()
        feedback_text = structured.feedback_text.strip() or "Colación recibida."
        response_intent = structured.intent or phase_intent
        response_confidence = structured.confidence
        response_metadata = structured.metadata or {}
    except Exception as exc:
        logger.exception("Fallo en pipeline LLM", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo generar la respuesta del controlador",
        ) from exc

    transitions = current_phase.get("transitions") if isinstance(current_phase, Mapping) else None
    next_phase_id = None
    if isinstance(response_metadata, Mapping):
        next_phase_id = response_metadata.get("nextPhase") or response_metadata.get("next_phase")
    if not next_phase_id and allow_response and isinstance(transitions, Mapping):
        auto_success = (
            transitions.get("onSuccess")
            or transitions.get("success")
        )
        if isinstance(auto_success, str) and auto_success.strip():
            next_phase_id = auto_success.strip()
    if next_phase_id:
        phase_map = session_context.get("phase_map")
        if isinstance(phase_map, Mapping):
            next_phase = phase_map.get(next_phase_id)
            if next_phase:
                logger.info(
                    "Transición automática de fase session=%s de=%s a=%s",
                    session_id,
                    current_phase.get("id") if isinstance(current_phase, Mapping) else None,
                    next_phase_id,
                )
                session_context["phase_id"] = next_phase_id
                session_context["phase"] = next_phase
                next_frequency = next_phase.get("frequency")
                if next_frequency:
                    session_context["default_frequency_group"] = next_frequency
                    session_context["active_frequency_group"] = next_frequency

    base_context_before_controller = _build_storage_context(
        session_context,
        turn_history,
    )

    controller_turn = {
        "role": "controller",
        "text": controller_text,
        "feedback": feedback_text,
        "allow_response": allow_response,
        "phase_id": session_context.get("phase_id"),
    }
    if response_intent:
        controller_turn["intent"] = response_intent
    if response_confidence is not None:
        controller_turn["confidence"] = response_confidence
    if response_metadata:
        controller_turn["metadata"] = response_metadata
    if llm_outcome is not None:
        controller_turn["llm_raw"] = llm_outcome.raw_response
    turn_history.append(controller_turn)
    turn_history = turn_history[-MAX_TURNS_STORED:]
    session_context["turn_history"] = turn_history
    session_context["recent_turns"] = turn_history[-8:]
    session_context["context_base"] = _build_storage_context(
        session_context,
        turn_history,
    )
    await append_turn(
        session_id,
        controller_turn,
        user_id=_current_user.id,
        base_context=base_context_before_controller,
    )
    transcript_logger.info(
        "controller | session=%s | frequency=%s | intent=%s | phase=%s | allow_response=%s | text=%s",
        session_id,
        frequency,
        controller_turn.get("intent"),
        controller_turn.get("phase_id"),
        allow_response,
        controller_text,
    )

    audio_url: str | None = None
    if allow_response and controller_text.strip():
        try:
            readback = await _radio_tts_service.synthesize_readback(controller_text)
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
        "controller_text": controller_text if allow_response and controller_text else None,
        "feedback": feedback_text,
    }
