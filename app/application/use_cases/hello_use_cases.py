from typing import List

from app.domain.models import HelloMessage
from app.application.interfaces import HelloMessageRepositoryInterface


class CreateHelloMessageUseCase:
    """Use case to persist a hello-world message"""

    def __init__(self, repository: HelloMessageRepositoryInterface):
        self.repository = repository

    async def execute(self, message: str) -> HelloMessage:
        return await self.repository.create(message)


class ListHelloMessagesUseCase:
    """Use case to retrieve recent hello-world messages"""

    def __init__(self, repository: HelloMessageRepositoryInterface):
        self.repository = repository

    async def execute(self, limit: int = 10) -> List[HelloMessage]:
        return await self.repository.list_recent(limit)
