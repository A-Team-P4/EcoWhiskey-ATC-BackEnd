"""Hello-world example controller."""

from typing import Annotated, List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.hello import HelloMessage as HelloMessageModel
from app.views import HelloMessageCreate, HelloMessageRead

router = APIRouter(prefix="/hello", tags=["hello"])


SessionDep = Annotated[AsyncSession, Depends(get_session)]
LimitQuery = Annotated[int, Query(ge=1, le=100)]


@router.post("/", response_model=HelloMessageRead, status_code=status.HTTP_201_CREATED)
async def create_hello_message(
    payload: HelloMessageCreate,
    session: SessionDep,
) -> HelloMessageRead:
    db_message = HelloMessageModel(message=payload.message)
    session.add(db_message)
    await session.commit()
    await session.refresh(db_message)
    return HelloMessageRead.model_validate(db_message)


@router.get("/", response_model=List[HelloMessageRead])
async def list_hello_messages(
    session: SessionDep,
    limit: LimitQuery = 10,
) -> List[HelloMessageRead]:
    result = await session.execute(
        select(HelloMessageModel)
        .order_by(HelloMessageModel.created_at.desc())
        .limit(limit)
    )
    messages = result.scalars().all()
    if not messages:
        return []
    return [HelloMessageRead.model_validate(row) for row in messages]
