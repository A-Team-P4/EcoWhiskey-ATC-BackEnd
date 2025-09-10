from typing import List, Optional
from datetime import datetime
from app.domain.models import Flight
from app.domain.services import FlightDomainService, AircraftDomainService
from app.application.interfaces import FlightRepositoryInterface, AircraftRepositoryInterface


class CreateFlightUseCase:
    """Use case for creating a new flight"""
    
    def __init__(self, flight_repository: FlightRepositoryInterface,
                 aircraft_repository: AircraftRepositoryInterface):
        self.flight_repository = flight_repository
        self.aircraft_repository = aircraft_repository
    
    async def execute(self, aircraft_id: int, origin: str, destination: str,
                     departure_time: datetime, arrival_time: datetime,
                     flight_number: str = None) -> Flight:
        """Create a new flight"""
        # Validate times
        if not FlightDomainService.is_flight_time_valid(departure_time, arrival_time):
            raise ValueError("Arrival time must be after departure time")
        
        # Check if aircraft exists and is available
        aircraft = await self.aircraft_repository.get_by_id(aircraft_id)
        if not aircraft:
            raise ValueError("Aircraft not found")
        
        if not AircraftDomainService.is_aircraft_available(aircraft):
            raise ValueError("Aircraft is not available")
        
        # Generate flight number if not provided
        if not flight_number:
            flight_number = FlightDomainService.generate_flight_number(origin, destination)
        
        # Check if flight number already exists
        existing_flight = await self.flight_repository.get_by_flight_number(flight_number)
        if existing_flight:
            raise ValueError("Flight with this number already exists")
        
        # Create flight
        flight = Flight(
            flight_number=flight_number,
            aircraft_id=aircraft_id,
            origin=origin,
            destination=destination,
            departure_time=departure_time,
            arrival_time=arrival_time,
            status="scheduled"
        )
        
        return await self.flight_repository.create(flight)


class GetFlightUseCase:
    """Use case for retrieving a flight"""
    
    def __init__(self, flight_repository: FlightRepositoryInterface):
        self.flight_repository = flight_repository
    
    async def execute(self, flight_id: int) -> Optional[Flight]:
        """Get flight by ID"""
        return await self.flight_repository.get_by_id(flight_id)


class ListFlightsUseCase:
    """Use case for listing all flights"""
    
    def __init__(self, flight_repository: FlightRepositoryInterface):
        self.flight_repository = flight_repository
    
    async def execute(self) -> List[Flight]:
        """List all flights"""
        return await self.flight_repository.list_all()


class UpdateFlightStatusUseCase:
    """Use case for updating flight status"""
    
    def __init__(self, flight_repository: FlightRepositoryInterface):
        self.flight_repository = flight_repository
    
    async def execute(self, flight_id: int, new_status: str) -> Optional[Flight]:
        """Update flight status"""
        flight = await self.flight_repository.get_by_id(flight_id)
        if not flight:
            raise ValueError("Flight not found")
        
        flight.status = new_status
        return await self.flight_repository.update(flight)