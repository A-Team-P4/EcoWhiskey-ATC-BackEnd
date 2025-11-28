"""Flight context endpoints."""

from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, select

from app.controllers.dependencies import CurrentUserDep, SessionDep
from app.models.phase_score import PhaseScore
from app.models.training_context import TrainingContext
from app.models.user import AccountType, User as UserModel
from app.views.training_context import (
    LastControllerTurnResponse,
    TrainingContextHistoryItem,
    TrainingContextRequest,
    TrainingContextResponse,
)

router = APIRouter(prefix="/training_context", tags=["training_context"])


async def _ensure_can_view_user_training(
    session: SessionDep,
    target_user_id: int,
    current_user: CurrentUserDep,
) -> UserModel:
    """Validate that the requester can read training data for the target user."""

    result = await session.execute(select(UserModel).where(UserModel.id == target_user_id))
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if target_user.id == current_user.id:
        return target_user

    if current_user.account_type != AccountType.INSTRUCTOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to view this training data",
        )
    if not current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Assign an academy to your profile first",
        )
    if target_user.school_id != current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view students from your academy",
        )

    return target_user


@router.post(
    "/",
    response_model=TrainingContextResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_flight_context(
    _current_user: CurrentUserDep,
    payload: TrainingContextRequest,
    session: SessionDep,
) -> TrainingContextResponse:
    """Create a new flight context with a unique trainingSessionId and persist it."""

    training_session_id = uuid4()

    db_context = TrainingContext(
        training_session_id=training_session_id,
        user_id=_current_user.id,
        context=payload.context,
    )

    session.add(db_context)

    await session.commit()

    await session.refresh(db_context)

    return TrainingContextResponse(
        trainingSessionId=db_context.training_session_id,
        context=db_context.context,
    )


@router.get(
    "/history/{user_id}",
    response_model=list[TrainingContextHistoryItem],
)
async def get_training_history(
    user_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> list[TrainingContextHistoryItem]:
    """Return the chronological history of training contexts for the given user.

    Only extracts scenario_id from the context JSONB for efficiency.
    """

    await _ensure_can_view_user_training(session, user_id, current_user)

    result = await session.execute(
        select(
            TrainingContext.training_session_id,
            TrainingContext.context["scenario_id"].label("scenario_id"),
            TrainingContext.context["session_completed"].label("session_completed"),
            TrainingContext.created_at,
            TrainingContext.updated_at,
        )
        .where(TrainingContext.user_id == user_id)
        .order_by(TrainingContext.created_at.desc())
    )
    rows = result.all()

    return [
        TrainingContextHistoryItem(
            trainingSessionId=row.training_session_id,
            context={
                "scenario_id": row.scenario_id,
                "session_completed": row.session_completed,
            },
            createdAt=row.created_at,
            updatedAt=row.updated_at,
        )
        for row in rows
    ]


@router.get(
    "/last-controller-turn/{training_session_id}",
    response_model=LastControllerTurnResponse,
)
async def get_last_controller_turn(
    training_session_id: UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> LastControllerTurnResponse:
    """Get the last controller turn information from a training session.

    Finds the last turn where role === 'controller' in the turns array,
    and extracts frequency from the previous turn.
    """

    # Fetch the training context
    result = await session.execute(
        select(TrainingContext).where(
            TrainingContext.training_session_id == training_session_id
        )
    )
    training_context = result.scalar_one_or_none()

    if not training_context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Training session not found",
        )

    await _ensure_can_view_user_training(
        session,
        training_context.user_id,
        current_user,
    )

    context = training_context.context
    turns = context.get("turns", [])
    session_completed = context.get("session_completed", False)

    # Find the last controller turn
    frequency = None
    controller_text = None
    feedback = None

    # Iterate backwards to find the last controller turn
    for i in range(len(turns) - 1, -1, -1):
        turn = turns[i]
        if turn.get("role") == "controller":
            controller_text = turn.get("text")
            feedback = turn.get("feedback")

            # Get frequency from the previous turn (index i-1)
            if i > 0:
                previous_turn = turns[i - 1]
                frequency = previous_turn.get("frequency")

            break

    return LastControllerTurnResponse(
        session_id=training_session_id,
        frequency=frequency,
        controller_text=controller_text,
        feedback=feedback,
        session_completed=session_completed,
    )


@router.delete(
    "/{training_session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_training_session(
    training_session_id: UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> None:
    """Delete a training session and all associated phase scores.

    First deletes all phase scores, then deletes the training context.
    Only the owner of the training session can delete it.
    """

    # Verify the training session exists and belongs to the current user
    result = await session.execute(
        select(TrainingContext).where(
            TrainingContext.training_session_id == training_session_id
        )
    )
    training_context = result.scalar_one_or_none()

    if not training_context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Training session not found",
        )

    if training_context.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to this training session is forbidden",
        )

    # Delete phase scores first
    await session.execute(
        delete(PhaseScore).where(PhaseScore.training_session_id == training_session_id)
    )

    # Delete training context
    await session.execute(
        delete(TrainingContext).where(
            TrainingContext.training_session_id == training_session_id
        )
    )

    await session.commit()
