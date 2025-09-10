from abc import ABC, abstractmethod
from typing import List, Optional
from app.domain.models import User, Aircraft, Flight


class UserRepositoryInterface(ABC):
    """Interface for User repository"""
    
    @abstractmethod
    async def create(self, user: User) -> User:
        pass
    
    @abstractmethod
    async def get_by_id(self, user_id: int) -> Optional[User]:
        pass
    
    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[User]:
        pass
    
    @abstractmethod
    async def list_all(self) -> List[User]:
        pass
    
    @abstractmethod
    async def update(self, user: User) -> User:
        pass
    
    @abstractmethod
    async def delete(self, user_id: int) -> bool:
        pass


class AircraftRepositoryInterface(ABC):
    """Interface for Aircraft repository"""
    
    @abstractmethod
    async def create(self, aircraft: Aircraft) -> Aircraft:
        pass
    
    @abstractmethod
    async def get_by_id(self, aircraft_id: int) -> Optional[Aircraft]:
        pass
    
    @abstractmethod
    async def get_by_registration(self, registration: str) -> Optional[Aircraft]:
        pass
    
    @abstractmethod
    async def list_all(self) -> List[Aircraft]:
        pass
    
    @abstractmethod
    async def update(self, aircraft: Aircraft) -> Aircraft:
        pass
    
    @abstractmethod
    async def delete(self, aircraft_id: int) -> bool:
        pass


class FlightRepositoryInterface(ABC):
    """Interface for Flight repository"""
    
    @abstractmethod
    async def create(self, flight: Flight) -> Flight:
        pass
    
    @abstractmethod
    async def get_by_id(self, flight_id: int) -> Optional[Flight]:
        pass
    
    @abstractmethod
    async def get_by_flight_number(self, flight_number: str) -> Optional[Flight]:
        pass
    
    @abstractmethod
    async def list_all(self) -> List[Flight]:
        pass
    
    @abstractmethod
    async def update(self, flight: Flight) -> Flight:
        pass
    
    @abstractmethod
    async def delete(self, flight_id: int) -> bool:
        pass


class S3ServiceInterface(ABC):
    """Interface for S3 service"""
    
    @abstractmethod
    async def upload_file(self, file_path: str, bucket: str, key: str) -> str:
        pass
    
    @abstractmethod
    async def download_file(self, bucket: str, key: str, local_path: str) -> bool:
        pass
    
    @abstractmethod
    async def delete_file(self, bucket: str, key: str) -> bool:
        pass


class MessageQueueInterface(ABC):
    """Interface for Message Queue service"""
    
    @abstractmethod
    async def publish_message(self, queue_name: str, message: dict) -> bool:
        pass
    
    @abstractmethod
    async def consume_message(self, queue_name: str) -> Optional[dict]:
        pass