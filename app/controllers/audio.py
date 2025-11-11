"""Audio analysis endpoints.

For a stage-by-stage map see `app.pipelines.audio.flow.AudioAnalysisPipeline`
or the documentation in `docs/audio_pipeline_overview.md`. The POST
`/audio/analyze` pipeline performs:

1. Validation + transcription of the uploaded recording.
2. Session context refresh (scenario, turns, phase) pulled from the repository.
3. Frequency validation and LLM call to craft controller+feedback text.
4. Phase transition bookkeeping, turn persistence, logging, and readback TTS upload.
"""

import logging
from typing import Any, Mapping
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.controllers.dependencies import CurrentUserDep, SessionDep
from app.models.phase_score import PhaseScore
from app.pipelines.audio import (
    AudioAnalysisPipeline,
    LlmOutcome,
    build_llm_request,
    classify_intent,
    call_conversation_llm,
    context_base,
    fetch_session_context,
    normalize_frequency,
    read_audio_bytes,
    resolve_content_type,
    synthesize_controller_audio,
    transcribe_audio,
)
from app.services.context_repository import MAX_TURNS_STORED, append_turn

router = APIRouter(prefix="/audio", tags=["audio"])

logger = logging.getLogger(__name__)
transcript_logger = logging.getLogger("app.logs.transcript")


RECENT_TURNS_LIMIT = 8  # Keep a short tail of turns for LLM context and storage replay.
PIPELINE_STAGES = tuple(AudioAnalysisPipeline.describe())
"""Ordered pipeline metadata used for quick reference and debugging."""

_SESSION_ID_FORM = Form(...)
_FREQUENCY_FORM = Form(...)
_AUDIO_FILE_UPLOAD = File(...)


@router.post("/analyze")
async def analyze_audio(
    _current_user: CurrentUserDep,
    db_session: SessionDep,
    session_id: UUID = _SESSION_ID_FORM,
    frequency: str = _FREQUENCY_FORM,
    audio_file: UploadFile = _AUDIO_FILE_UPLOAD,
) -> dict[str, Any]:
    """Transcribe an uploaded MP3 or M4A file and generate a Polly readback."""
    content_type = resolve_content_type(audio_file)
    audio_bytes = await read_audio_bytes(audio_file)
    transcript_text = await transcribe_audio(session_id, audio_bytes, content_type)

    # Log both for observability and to capture audio transcripts in the dedicated logger.
    logger.info("Transcripción recibida session=%s: %s", session_id, transcript_text)
    transcript_logger.info("student | session=%s | frequency=%s | text=%s", session_id, frequency, transcript_text)

    raw_context = await fetch_session_context(session_id)
    session_context = dict(raw_context) if isinstance(raw_context, Mapping) else {}
    history = [dict(turn) for turn in session_context.get("turn_history", []) if isinstance(turn, Mapping)][-MAX_TURNS_STORED:]
    session_context.update(turn_history=list(history), recent_turns=list(history[-RECENT_TURNS_LIMIT:]), context_base=context_base(session_context, history))

    async def save_turn(turn: Mapping[str, Any]) -> None:
        """Append a turn to both storage and local context helpers."""
        payload = dict(turn)
        await append_turn(session_id, payload, user_id=_current_user.id, base_context=context_base(session_context, history))
        history.append(payload)
        history[:] = history[-MAX_TURNS_STORED:]
        session_context.update(turn_history=list(history), recent_turns=list(history[-RECENT_TURNS_LIMIT:]), context_base=context_base(session_context, history))

    # Seed the conversation with the student's transmission plus any relevant context snapshots.
    student_turn = {"role": "student", "text": transcript_text, "frequency": frequency}
    meteo, route = session_context.get("meteo"), session_context.get("route")
    if meteo: student_turn["meteo"] = meteo
    if route: student_turn["route"] = route

    intent_classification = await classify_intent(transcript_text, session_context)
    classifier_intent = None
    classifier_frequency_group = None
    classifier_confidence = None
    if intent_classification:
        classifier_intent = (intent_classification.intent or "").strip() or None
        classifier_frequency_group = (intent_classification.frequency_group or "").strip() or None
        classifier_confidence = intent_classification.confidence
        if classifier_intent:
            student_turn["intent"] = classifier_intent
        if classifier_frequency_group:
            student_turn["frequency_group"] = classifier_frequency_group
        if classifier_confidence is not None:
            student_turn["intent_confidence"] = classifier_confidence

    await save_turn(student_turn)

    current_phase = session_context.get("phase")
    if not isinstance(current_phase, Mapping):
        logger.error("No hay fase activa para session=%s", session_id); raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No hay fase activa configurada para la sesión.")

    scenario_intent = current_phase.get("intent")
    phase_intent = classifier_intent or scenario_intent
    if not phase_intent:
        logger.error("Fase sin intent definido session=%s phase=%s", session_id, current_phase); raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La fase activa no tiene un intent configurado.")

    # Figure out which frequency bucket should be active and whether the incoming one aligns.
    scenario_group = (
        current_phase.get("frequency")
        or session_context.get("active_frequency_group")
        or session_context.get("default_frequency_group")
        or "tower"
    )
    active_group = scenario_group
    if classifier_frequency_group:
        if not scenario_group or scenario_group == "unknown":
            active_group = classifier_frequency_group
        elif classifier_frequency_group != scenario_group:
            logger.info(
                "Intent detector frequency mismatch session=%s detected=%s scenario=%s",
                session_id,
                classifier_frequency_group,
                scenario_group,
            )
        else:
            active_group = scenario_group
    frequencies = session_context.get("frequencies")
    expected_frequency = frequencies.get(active_group) if isinstance(frequencies, Mapping) else None
    normalized_frequency = frequency.strip()
    expected_frequency_normalized = normalize_frequency(expected_frequency)
    received_frequency_normalized = normalize_frequency(normalized_frequency)
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
    if scenario_intent and scenario_intent != phase_intent:
        phase_payload.setdefault("scenario_intent", scenario_intent)
    if classifier_intent:
        phase_payload.setdefault("detected_intent", classifier_intent)
    if classifier_frequency_group:
        phase_payload.setdefault("detected_frequency_group", classifier_frequency_group)
    if classifier_confidence is not None:
        phase_payload.setdefault("intent_confidence", classifier_confidence)

    logger.info("Fase activa session=%s phase_id=%s intent=%s freq=%s", session_id, session_context.get("phase_id"), phase_intent, active_group)

    allow_response = False; controller_text = ""; feedback_text = "Colación recibida."
    response_intent = phase_intent; response_confidence = None; response_score = None; response_metadata: dict[str, Any] = {}; llm_outcome: LlmOutcome | None = None
    if classifier_intent:
        response_metadata["detected_intent"] = classifier_intent
    if classifier_frequency_group:
        response_metadata["detected_frequency_group"] = classifier_frequency_group
    if classifier_confidence is not None:
        response_metadata["intent_confidence"] = classifier_confidence
    if scenario_intent and scenario_intent != phase_intent:
        response_metadata["scenario_intent"] = scenario_intent

    if is_valid_frequency:
        # Happy path: enrich the transcript with context and delegate phrasing to the LLM.
        try:
            request = build_llm_request(
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
            response_score = structured.score
            if structured.metadata:
                response_metadata.update(dict(structured.metadata))
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
        response_score = 0.0
        response_metadata.update({"frequency_valid": False})
        if expected_frequency:
            response_metadata["expected_frequency"] = display_expected
        response_metadata["received_frequency"] = display_received
        response_metadata["expected_frequency_group"] = active_group
        if classifier_frequency_group and classifier_frequency_group != active_group:
            response_metadata["classifier_frequency_group"] = classifier_frequency_group
        if scenario_group and scenario_group != active_group:
            response_metadata["scenario_frequency_group"] = scenario_group

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

    # Record what the "controller" said and keep the turn history bounded.
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
    if response_score is not None:
        controller_turn["score"] = response_score
    if response_metadata:
        controller_turn["metadata"] = response_metadata
    if llm_outcome is not None:
        controller_turn["llm_raw"] = llm_outcome.raw_response

    await save_turn(controller_turn)

    # Save phase score to database if available
    if response_score is not None:
        current_phase_id = session_context.get("phase_id") or "unknown"

        # If frequency was incorrect, only track the frequency error (don't penalize the phase)
        if not is_valid_frequency:
            frequency_error_score = PhaseScore(
                training_session_id=session_id,
                user_id=_current_user.id,
                phase_id="frequency_usage_error",
                score=0.0,
                feedback=feedback_text,
            )
            db_session.add(frequency_error_score)
            await db_session.commit()
            logger.info("Error de frecuencia registrado session=%s phase_id=%s", session_id, current_phase_id)
        else:
            # Valid frequency: save the actual phase score
            phase_score = PhaseScore(
                training_session_id=session_id,
                user_id=_current_user.id,
                phase_id=current_phase_id,
                score=response_score,
                feedback=feedback_text,
            )
            db_session.add(phase_score)
            await db_session.commit()
            logger.info("Puntuación guardada session=%s phase_id=%s score=%.2f", session_id, current_phase_id, response_score)

    # Mirror what will be sent to the UI and Polly into logs for support.
    transcript_logger.info("controller | session=%s | frequency=%s | intent=%s | phase=%s | allow_response=%s | text=%s", session_id, frequency, controller_turn.get("intent"), controller_turn.get("phase_id"), allow_response, controller_text)

    audio_url = await synthesize_controller_audio(session_id, controller_text, allow_response)

    return {
        "session_id": str(session_id),
        "frequency": frequency,
        "audio_url": audio_url,
        "controller_text": controller_text if allow_response and controller_text else None,
        "feedback": feedback_text,
    }
