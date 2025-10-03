"""Flight context endpoints."""
from uuid import uuid4
from fastapi import APIRouter, status
from app.controllers.dependencies import CurrentUserDep, SessionDep
from app.models.training_context import TrainingContext
from app.views.training_context import TrainingContextRequest, TrainingContextResponse

router = APIRouter(prefix="/training_context", tags=["training_context"])

@router.post("/", 
             response_model = TrainingContextResponse, 
             status_code=status.HTTP_201_CREATED
            )
async def create_flight_context(
    _current_user: CurrentUserDep,
    payload: TrainingContextRequest,
    session: SessionDep,
) -> TrainingContextResponse:
    """Create a new flight context with a unique trainingSessionId and persist it."""

    # Generate training session id
    training_session_id = uuid4()

    
    # Create DB entity
    db_context = TrainingContext(
        training_session_id=training_session_id,
        user_id=_current_user.id,  # assuming CurrentUserDep gives you the authenticated user
        context=payload.context,
    )

    session.add(db_context)

    await session.commit()
    
    await session.refresh(db_context)

    return TrainingContextResponse(
        trainingSessionId=db_context.training_session_id,
        context=db_context.context,
    )