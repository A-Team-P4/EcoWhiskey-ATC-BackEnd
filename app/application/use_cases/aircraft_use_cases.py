from typing import List, Optional
from app.domain.models import Aircraft
from app.domain.services import AircraftDomainService
from app.application.interfaces import AircraftRepositoryInterface


class CreateAircraftUseCase:
    """Use case for creating a new aircraft"""
    
    def __init__(self, aircraft_repository: AircraftRepositoryInterface):
        self.aircraft_repository = aircraft_repository
    
    async def execute(self, registration: str, model: str, manufacturer: str, 
                     year: int, capacity: int) -> Aircraft:
        """Create a new aircraft"""
        # Check if aircraft already exists
        existing_aircraft = await self.aircraft_repository.get_by_registration(registration)
        if existing_aircraft:
            raise ValueError("Aircraft with this registration already exists")
        
        # Create aircraft
        aircraft = Aircraft(
            registration=registration,
            model=model,
            manufacturer=manufacturer,
            year=year,
            capacity=capacity,
            status="available"
        )
        
        return await self.aircraft_repository.create(aircraft)


class GetAircraftUseCase:
    """Use case for retrieving an aircraft"""
    
    def __init__(self, aircraft_repository: AircraftRepositoryInterface):
        self.aircraft_repository = aircraft_repository
    
    async def execute(self, aircraft_id: int) -> Optional[Aircraft]:
        """Get aircraft by ID"""
        return await self.aircraft_repository.get_by_id(aircraft_id)


class ListAircraftUseCase:
    """Use case for listing all aircraft"""
    
    def __init__(self, aircraft_repository: AircraftRepositoryInterface):
        self.aircraft_repository = aircraft_repository
    
    async def execute(self) -> List[Aircraft]:
        """List all aircraft"""
        return await self.aircraft_repository.list_all()


class GetAvailableAircraftUseCase:
    """Use case for getting available aircraft"""
    
    def __init__(self, aircraft_repository: AircraftRepositoryInterface):
        self.aircraft_repository = aircraft_repository
    
    async def execute(self) -> List[Aircraft]:
        """Get all available aircraft"""
        all_aircraft = await self.aircraft_repository.list_all()
        return [
            aircraft for aircraft in all_aircraft 
            if AircraftDomainService.is_aircraft_available(aircraft)
        ]