from abc import ABC, abstractmethod
from typing import List, Optional

from app.domain.models import HelloMessage, User


class UserRepositoryInterface(ABC):
    """Persistence contract for user entities"""

    @abstractmethod
    async def create(self, user: User) -> User:
        ...

    @abstractmethod
    async def get_by_id(self, user_id: int) -> Optional[User]:
        ...

    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[User]:
        ...

    @abstractmethod
    async def list_all(self) -> List[User]:
        ...

    @abstractmethod
    async def update(self, user: User) -> User:
        ...

    @abstractmethod
    async def delete(self, user_id: int) -> bool:
        ...


class HelloMessageRepositoryInterface(ABC):
    """Persistence contract for hello-world messages"""

    @abstractmethod
    async def create(self, message: str) -> HelloMessage:
        ...

    @abstractmethod
    async def list_recent(self, limit: int = 10) -> List[HelloMessage]:
        ...
