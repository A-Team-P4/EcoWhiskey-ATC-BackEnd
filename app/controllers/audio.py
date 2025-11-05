"""Audio analysis endpoints.

The POST /audio/analyze pipeline performs:
1. Validation + transcription of the uploaded recording.
2. Session context refresh (scenario, turns, phase) pulled from the repository.
3. Frequency validation and LLM call to craft controller+feedback text.
4. Phase transition bookkeeping, turn persistence, logging, and readback TTS upload.
"""

import logging
import mimetypes
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
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
    LlmOutcome,
    build_llm_request,
    call_conversation_llm,
    fetch_session_context,
)
from app.services.context_repository import MAX_TURNS_STORED, append_turn

router = APIRouter(prefix="/audio", tags=["audio"])

logger = logging.getLogger(__name__)
transcript_logger = logging.getLogger("app.logs.transcript")


RECENT_TURNS_LIMIT = 8  # Keep a short tail of turns for LLM context and storage replay.
_CONTEXT_FIELDS = (
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
)


def _context_base(ctx: Mapping[str, Any], history: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Build the payload persisted alongside each turn for audit/debug purposes."""
    base = {k: ctx[k] for k in _CONTEXT_FIELDS if ctx.get(k) is not None}
    scenario = base.get("scenario")
    if isinstance(scenario, Mapping):
        base["scenario"] = {k: v for k, v in scenario.items() if k != "_phase_map"}
    base["turns"] = [dict(t) for t in history]
    return base


def _resolve_content_type(audio_file: UploadFile) -> str:
    """Accept mp3/m4a uploads regardless of whether the client set a content-type."""
    content_type = audio_file.content_type
    if not content_type and audio_file.filename:
        guessed_type, _ = mimetypes.guess_type(audio_file.filename)
        content_type = guessed_type

    content_type = content_type or "audio/mpeg"

    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only MP3 or M4A audio files are supported",
        )
    return content_type


def _normalize_frequency(value: str | None) -> str | None:
    """Normalize frequency strings (e.g., 118.3 → 118.300) for robust comparisons."""
    if value is None:
        return None

    cleaned = str(value).strip()
    if not cleaned:
        return None

    cleaned = cleaned.replace(",", ".")
    try:
        as_decimal = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return cleaned.lower()

    normalized = as_decimal.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    return format(normalized, "f")


async def _read_audio_bytes(audio_file: UploadFile) -> bytes:
    """Load the upload fully into memory, rejecting empty payloads."""
    audio_bytes = await audio_file.read()
    await audio_file.close()

    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded audio file is empty",
        )
    return audio_bytes


async def _transcribe_audio(
    session_id: UUID,
    audio_bytes: bytes,
    content_type: str,
) -> str:
    """Delegate to the transcription microservice and surface fastapi-friendly errors."""
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

    return result.transcript


async def _synthesize_controller_audio(
    session_id: UUID,
    controller_text: str,
    allow_response: bool,
) -> str | None:
    text = controller_text.strip()
    if not allow_response or not text:
        return None

    try:
        readback = await _radio_tts_service.synthesize_readback(text)
    except RadioTtsError as exc:  # pragma: no cover - integration failure
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
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return audio_url


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
    content_type = _resolve_content_type(audio_file)
    audio_bytes = await _read_audio_bytes(audio_file)
    transcript_text = await _transcribe_audio(session_id, audio_bytes, content_type)

    # Log both for observability and to capture audio transcripts in the dedicated logger.
    logger.info("Transcripción recibida session=%s: %s", session_id, transcript_text)
    transcript_logger.info("student | session=%s | frequency=%s | text=%s", session_id, frequency, transcript_text)

    raw_context = await fetch_session_context(session_id)
    session_context = dict(raw_context) if isinstance(raw_context, Mapping) else {}
    history = [dict(turn) for turn in session_context.get("turn_history", []) if isinstance(turn, Mapping)][-MAX_TURNS_STORED:]
    session_context.update(turn_history=list(history), recent_turns=list(history[-RECENT_TURNS_LIMIT:]), context_base=_context_base(session_context, history))

    async def save_turn(turn: Mapping[str, Any]) -> None:
        """Append a turn to both storage and local context helpers."""
        payload = dict(turn)
        await append_turn(session_id, payload, user_id=_current_user.id, base_context=_context_base(session_context, history))
        history.append(payload)
        history[:] = history[-MAX_TURNS_STORED:]
        session_context.update(turn_history=list(history), recent_turns=list(history[-RECENT_TURNS_LIMIT:]), context_base=_context_base(session_context, history))

    # Seed the conversation with the student's transmission plus any relevant context snapshots.
    student_turn = {"role": "student", "text": transcript_text, "frequency": frequency}
    meteo, route = session_context.get("meteo"), session_context.get("route")
    if meteo: student_turn["meteo"] = meteo
    if route: student_turn["route"] = route
    await save_turn(student_turn)

    current_phase = session_context.get("phase")
    if not isinstance(current_phase, Mapping):
        logger.error("No hay fase activa para session=%s", session_id); raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No hay fase activa configurada para la sesión.")
    if not (phase_intent := current_phase.get("intent")):
        logger.error("Fase sin intent definido session=%s phase=%s", session_id, current_phase); raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La fase activa no tiene un intent configurado.")

    # Figure out which frequency bucket should be active and whether the incoming one aligns.
    active_group = (
        current_phase.get("frequency")
        or session_context.get("active_frequency_group")
        or session_context.get("default_frequency_group")
        or "tower"
    )
    frequencies = session_context.get("frequencies")
    expected_frequency = frequencies.get(active_group) if isinstance(frequencies, Mapping) else None
    normalized_frequency = frequency.strip()
    expected_frequency_normalized = _normalize_frequency(expected_frequency)
    received_frequency_normalized = _normalize_frequency(normalized_frequency)
    session_context["active_frequency_group"] = active_group
    is_valid_frequency = (
        not expected_frequency_normalized
        or received_frequency_normalized == expected_frequency_normalized
    )

    phase_payload = dict(current_phase)
    if expected_frequency:
        phase_payload.setdefault(
            "expected_frequency",
            expected_frequency_normalized or expected_frequency,
        )
    if normalized_frequency:
        phase_payload.setdefault(
            "received_frequency",
            received_frequency_normalized or normalized_frequency,
        )

    logger.info("Fase activa session=%s phase_id=%s intent=%s freq=%s", session_id, session_context.get("phase_id"), phase_intent, active_group)

    allow_response = False; controller_text = ""; feedback_text = "Colación recibida."
    response_intent = phase_intent; response_confidence = None; response_metadata: dict[str, Any] = {}; llm_outcome: LlmOutcome | None = None

    if is_valid_frequency:
        # Happy path: enrich the transcript with context and delegate phrasing to the LLM.
        try:
            request = await build_llm_request(
                transcript=transcript_text,
                context=session_context,
                phase=phase_payload,
                intent=phase_intent,
                frequency=frequency,
                frequency_group=active_group,
            )
            llm_outcome = await call_conversation_llm(request)
            structured = llm_outcome.response
            allow_response = bool(structured.allow_response)
            controller_text = (structured.controller_text or "").strip()
            feedback_text = structured.feedback_text.strip() or feedback_text
            response_intent = structured.intent or phase_intent
            response_confidence = structured.confidence
            response_metadata = dict(structured.metadata or {})
        except Exception as exc:  # pragma: no cover - integration failure
            logger.exception("Fallo en pipeline LLM", exc_info=exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="No se pudo generar la respuesta del controlador",
            ) from exc
    else:
        # Frequency mismatch: short-circuit the LLM and send direct feedback.
        display_expected = expected_frequency_normalized or expected_frequency or active_group
        display_received = received_frequency_normalized or normalized_frequency or "<vacía>"
        message = f"La frecuencia esperada para esta solicitud es {display_expected}."
        logger.info("Frecuencia fuera de rango intent=%s freq=%s esperado=%s", phase_intent, display_received, display_expected)
        controller_text = feedback_text = message
        response_metadata = {"frequency_valid": False}
        if expected_frequency:
            response_metadata["expected_frequency"] = display_expected

    # Update session phase automatically if the response (or LLM metadata) says so.
    next_phase_id = (response_metadata.get("nextPhase") or response_metadata.get("next_phase")) if response_metadata else None
    if not next_phase_id and allow_response:
        transitions = current_phase.get("transitions")
        candidate = (transitions.get("onSuccess") or transitions.get("success")) if isinstance(transitions, Mapping) else None
        if isinstance(candidate, str) and candidate.strip():
            next_phase_id = candidate.strip()
    if next_phase_id:
        phase_map = session_context.get("phase_map")
        next_phase = phase_map.get(next_phase_id) if isinstance(phase_map, Mapping) else None
        if isinstance(next_phase, Mapping):
            logger.info("Transición automática de fase session=%s de=%s a=%s", session_id, current_phase.get("id"), next_phase_id)
            session_context["phase_id"] = next_phase_id
            session_context["phase"] = next_phase
            if next_phase.get("frequency"):
                session_context["default_frequency_group"] = session_context["active_frequency_group"] = next_phase["frequency"]

    # Record what the “controller” said and keep the turn history bounded.
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

    await save_turn(controller_turn)

    # Mirror what will be sent to the UI and Polly into logs for support.
    transcript_logger.info("controller | session=%s | frequency=%s | intent=%s | phase=%s | allow_response=%s | text=%s", session_id, frequency, controller_turn.get("intent"), controller_turn.get("phase_id"), allow_response, controller_text)

    audio_url = await _synthesize_controller_audio(session_id, controller_text, allow_response)

    return {
        "session_id": str(session_id),
        "frequency": frequency,
        "audio_url": audio_url,
        "controller_text": controller_text if allow_response and controller_text else None,
        "feedback": feedback_text,
    }
