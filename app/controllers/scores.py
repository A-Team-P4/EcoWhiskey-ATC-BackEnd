"""Score retrieval and analytics endpoints."""

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.controllers.dependencies import CurrentUserDep, SessionDep
from app.models.phase_score import PhaseScore
from app.services.llm_client import BedrockLlmClient

router = APIRouter(prefix="/scores", tags=["scores"])

logger = logging.getLogger(__name__)


@router.get("/session/{session_id}")
async def get_session_scores(
    _current_user: CurrentUserDep,
    db_session: SessionDep,
    session_id: UUID,
) -> dict[str, Any]:
    """Get all phase scores and averages for a training session."""

    # Get all scores for this session
    result = await db_session.execute(
        select(PhaseScore)
        .where(PhaseScore.training_session_id == session_id)
        .where(PhaseScore.user_id == _current_user.id)
        .order_by(PhaseScore.created_at)
    )
    scores = result.scalars().all()

    if not scores:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No scores found for this session",
        )

    # Calculate average score per phase
    phase_averages_result = await db_session.execute(
        select(
            PhaseScore.phase_id,
            func.avg(PhaseScore.score).label("average_score"),
            func.count(PhaseScore.id).label("score_count"),
        )
        .where(PhaseScore.training_session_id == session_id)
        .where(PhaseScore.user_id == _current_user.id)
        .group_by(PhaseScore.phase_id)
    )

    phase_averages = {}
    for row in phase_averages_result:
        phase_averages[row.phase_id] = {
            "average_score": round(float(row.average_score), 2),
            "score_count": row.score_count,
        }

    # Calculate overall session average
    all_scores = [float(score.score) for score in scores]
    overall_average = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0.0

    return {
        "session_id": str(session_id),
        "overall_average": overall_average,
        "total_scores": len(scores),
        "phase_averages": phase_averages,
        "scores": [
            {
                "id": str(score.id),
                "phase_id": score.phase_id,
                "score": score.score,
                "feedback": score.feedback,
                "created_at": score.created_at.isoformat(),
            }
            for score in scores
        ],
    }


@router.get("/phase/{phase_id}")
async def get_phase_scores(
    _current_user: CurrentUserDep,
    db_session: SessionDep,
    phase_id: str,
) -> dict[str, Any]:
    """Get all scores for a specific phase across all sessions for the current user."""

    # Get all scores for this phase
    result = await db_session.execute(
        select(PhaseScore)
        .where(PhaseScore.phase_id == phase_id)
        .where(PhaseScore.user_id == _current_user.id)
        .order_by(PhaseScore.created_at.desc())
    )
    scores = result.scalars().all()

    if not scores:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No scores found for this phase",
        )

    # Calculate average
    all_scores = [float(score.score) for score in scores]
    average_score = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0.0

    return {
        "phase_id": phase_id,
        "average_score": average_score,
        "total_scores": len(scores),
        "scores": [
            {
                "id": str(score.id),
                "session_id": str(score.training_session_id),
                "score": score.score,
                "feedback": score.feedback,
                "created_at": score.created_at.isoformat(),
            }
            for score in scores
        ],
    }


@router.get("/session/{session_id}/summary")
async def get_session_summary(
    _current_user: CurrentUserDep,
    db_session: SessionDep,
    session_id: UUID,
) -> dict[str, Any]:
    """Get session scores grouped by phase with LLM-generated summary."""

    # Get all scores for this session
    result = await db_session.execute(
        select(PhaseScore)
        .where(PhaseScore.training_session_id == session_id)
        .where(PhaseScore.user_id == _current_user.id)
        .order_by(PhaseScore.created_at)
    )
    scores = result.scalars().all()

    if not scores:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No scores found for this session",
        )

    # Group scores by phase_id
    phases_data = {}
    for score in scores:
        phase_id = score.phase_id
        if phase_id not in phases_data:
            phases_data[phase_id] = {
                "phase_id": phase_id,
                "scores": [],
                "average_score": 0.0,
            }
        phases_data[phase_id]["scores"].append({
            "score": score.score,
            "feedback": score.feedback,
            "created_at": score.created_at.isoformat(),
        })

    # Calculate averages per phase
    for phase_id, data in phases_data.items():
        phase_scores = [s["score"] for s in data["scores"]]
        data["average_score"] = round(sum(phase_scores) / len(phase_scores), 2)

    # Calculate overall average
    all_scores = [float(score.score) for score in scores]
    overall_average = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0.0

    # Generate LLM summary
    llm_client = BedrockLlmClient()

    # Build context for LLM
    session_context = f"Sesión de entrenamiento ATC - Promedio general: {overall_average}/100\n\n"
    session_context += "Desempeño por fase:\n"
    for phase_id, data in phases_data.items():
        session_context += f"- {phase_id}: {data['average_score']}/100 ({len(data['scores'])} evaluaciones)\n"
        if data["scores"]:
            session_context += "  Retroalimentación reciente:\n"
            for score_data in data["scores"][-3:]:  # Last 3 feedbacks
                if score_data["feedback"]:
                    session_context += f"    • {score_data['feedback']}\n"

    system_prompt = (
        "Eres un instructor de control de tráfico aéreo experto. "
        "Analiza el desempeño del estudiante en la sesión de entrenamiento y proporciona un resumen conciso."
    )

    user_prompt = (
        f"{session_context}\n\n"
        "Proporciona un resumen breve (máximo 3 párrafos) que incluya:\n"
        "1. Lo que el estudiante hizo bien en esta sesión\n"
        "2. Las áreas que necesitan mejora\n"
        "3. Recomendaciones específicas para la próxima sesión"
    )

    llm_summary = await llm_client.invoke(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=500,
        temperature=0.7,
    )

    return {
        "session_id": str(session_id),
        "overall_average": overall_average,
        "total_evaluations": len(scores),
        "phases": list(phases_data.values()),
        "summary": llm_summary or "No se pudo generar el resumen.",
    }


@router.get("/phase/{phase_id}/summary")
async def get_phase_summary(
    _current_user: CurrentUserDep,
    db_session: SessionDep,
    phase_id: str,
) -> dict[str, Any]:
    """Get all scores for a phase with LLM-generated improvement summary."""

    # Get all scores for this phase
    result = await db_session.execute(
        select(PhaseScore)
        .where(PhaseScore.phase_id == phase_id)
        .where(PhaseScore.user_id == _current_user.id)
        .order_by(PhaseScore.created_at.desc())
    )
    scores = result.scalars().all()

    if not scores:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No scores found for this phase",
        )

    # Calculate average
    all_scores = [float(score.score) for score in scores]
    average_score = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0.0

    # Generate LLM summary
    llm_client = BedrockLlmClient()

    # Build context for LLM
    phase_context = f"Fase: {phase_id}\n"
    phase_context += f"Promedio de puntuación: {average_score}/100\n"
    phase_context += f"Total de evaluaciones: {len(scores)}\n\n"
    phase_context += "Retroalimentación recibida:\n"

    for idx, score in enumerate(scores[:10], 1):  # Last 10 feedbacks
        if score.feedback:
            phase_context += f"{idx}. Puntuación: {score.score}/100 - {score.feedback}\n"

    system_prompt = (
        "Eres un instructor de control de tráfico aéreo experto. "
        "Analiza el desempeño del estudiante en una fase específica del entrenamiento."
    )

    user_prompt = (
        f"{phase_context}\n\n"
        "Basándote en las evaluaciones previas, proporciona un análisis breve (máximo 3 párrafos) que incluya:\n"
        "1. Qué aspectos de esta fase el estudiante domina bien\n"
        "2. Qué aspectos específicos necesitan mejora para aumentar la puntuación\n"
        "3. Consejos prácticos y concretos para mejorar en esta fase"
    )

    llm_summary = await llm_client.invoke(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=500,
        temperature=0.7,
    )

    return {
        "phase_id": phase_id,
        "average_score": average_score,
        "total_scores": len(scores),
        "scores": [
            {
                "id": str(score.id),
                "session_id": str(score.training_session_id),
                "score": score.score,
                "feedback": score.feedback,
                "created_at": score.created_at.isoformat(),
            }
            for score in scores
        ],
        "summary": llm_summary or "No se pudo generar el resumen.",
    }
