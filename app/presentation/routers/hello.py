from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.dependencies import get_database_session
from app.application.use_cases.hello_use_cases import (
    CreateHelloMessageUseCase,
    ListHelloMessagesUseCase,
)
from app.infrastructure.persistence.repositories_sqlalchemy import (
    SQLAlchemyHelloMessageRepository,
)
from app.presentation.dtos import (
    HelloMessageCreateRequest,
    HelloMessageResponse,
)


router = APIRouter(prefix="/hello", tags=["hello"])


@router.post("/", response_model=HelloMessageResponse, status_code=201)
async def create_hello_message(
    payload: HelloMessageCreateRequest,
    session: AsyncSession = Depends(get_database_session),
):
    """Persist a hello-world message"""

    try:
        repository = SQLAlchemyHelloMessageRepository(session)
        use_case = CreateHelloMessageUseCase(repository)
        message = await use_case.execute(payload.message)
        return HelloMessageResponse(**message.model_dump())
    except Exception as exc:  # pragma: no cover - thin wrapper
        raise HTTPException(status_code=500, detail="Failed to store message") from exc


@router.get("/", response_model=List[HelloMessageResponse])
async def list_hello_messages(
    limit: int = 10,
    session: AsyncSession = Depends(get_database_session),
):
    """Return recent hello-world messages"""

    try:
        repository = SQLAlchemyHelloMessageRepository(session)
        use_case = ListHelloMessagesUseCase(repository)
        messages = await use_case.execute(limit=limit)
        return [HelloMessageResponse(**item.model_dump()) for item in messages]
    except Exception as exc:  # pragma: no cover - thin wrapper
        raise HTTPException(status_code=500, detail="Failed to read messages") from exc
