from fastapi import APIRouter, HTTPException, Depends
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from app.presentation.dtos import FlightCreateRequest, FlightUpdateRequest, FlightResponse
from app.application.use_cases.flight_use_cases import (
    CreateFlightUseCase, GetFlightUseCase, ListFlightsUseCase, UpdateFlightStatusUseCase
)
from app.infrastructure.persistence.repositories_sqlalchemy import SQLAlchemyFlightRepository, SQLAlchemyAircraftRepository
from app.config.dependencies import get_database_session

router = APIRouter(prefix="/flights", tags=["flights"])


@router.post("/", response_model=FlightResponse, status_code=201)
async def create_flight(
    flight_data: FlightCreateRequest,
    session: AsyncSession = Depends(get_database_session)
):
    """Create a new flight"""
    try:
        flight_repository = SQLAlchemyFlightRepository(session)
        aircraft_repository = SQLAlchemyAircraftRepository(session)
        use_case = CreateFlightUseCase(flight_repository, aircraft_repository)
        
        flight = await use_case.execute(
            aircraft_id=flight_data.aircraft_id,
            origin=flight_data.origin,
            destination=flight_data.destination,
            departure_time=flight_data.departure_time,
            arrival_time=flight_data.arrival_time,
            flight_number=flight_data.flight_number
        )
        
        return FlightResponse(**flight.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{flight_id}", response_model=FlightResponse)
async def get_flight(
    flight_id: int,
    session: AsyncSession = Depends(get_database_session)
):
    """Get flight by ID"""
    try:
        flight_repository = SQLAlchemyFlightRepository(session)
        use_case = GetFlightUseCase(flight_repository)
        
        flight = await use_case.execute(flight_id)
        if not flight:
            raise HTTPException(status_code=404, detail="Flight not found")
        
        return FlightResponse(**flight.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=List[FlightResponse])
async def list_flights(
    session: AsyncSession = Depends(get_database_session)
):
    """List all flights"""
    try:
        flight_repository = SQLAlchemyFlightRepository(session)
        use_case = ListFlightsUseCase(flight_repository)
        
        flights = await use_case.execute()
        return [FlightResponse(**f.model_dump()) for f in flights]
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{flight_id}/status", response_model=FlightResponse)
async def update_flight_status(
    flight_id: int,
    status_data: FlightUpdateRequest,
    session: AsyncSession = Depends(get_database_session)
):
    """Update flight status"""
    try:
        flight_repository = SQLAlchemyFlightRepository(session)
        use_case = UpdateFlightStatusUseCase(flight_repository)
        
        flight = await use_case.execute(flight_id, status_data.status)
        if not flight:
            raise HTTPException(status_code=404, detail="Flight not found")
        
        return FlightResponse(**flight.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")