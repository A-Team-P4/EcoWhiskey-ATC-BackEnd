"""Flight context endpoints."""

from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.controllers.dependencies import CurrentUserDep, SessionDep
from app.models.training_context import TrainingContext
from app.views.training_context import (
    TrainingContextHistoryItem,
    TrainingContextRequest,
    TrainingContextResponse,
)

router = APIRouter(prefix="/training_context", tags=["training_context"])


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

    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to requested user history is forbidden",
        )

    result = await session.execute(
        select(
            TrainingContext.training_session_id,
            TrainingContext.context["scenario_id"].label("scenario_id"),
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
            context={"scenario_id": row.scenario_id},
            createdAt=row.created_at,
            updatedAt=row.updated_at,
        )
        for row in rows
    ]
