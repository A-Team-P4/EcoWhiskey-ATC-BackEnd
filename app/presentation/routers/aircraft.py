from fastapi import APIRouter, HTTPException, Depends
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from app.presentation.dtos import AircraftCreateRequest, AircraftResponse
from app.application.use_cases.aircraft_use_cases import (
    CreateAircraftUseCase, GetAircraftUseCase, ListAircraftUseCase, GetAvailableAircraftUseCase
)
from app.infrastructure.persistence.repositories_sqlalchemy import SQLAlchemyAircraftRepository
from app.config.dependencies import get_database_session

router = APIRouter(prefix="/aircraft", tags=["aircraft"])


@router.post("/", response_model=AircraftResponse, status_code=201)
async def create_aircraft(
    aircraft_data: AircraftCreateRequest,
    session: AsyncSession = Depends(get_database_session)
):
    """Create a new aircraft"""
    try:
        aircraft_repository = SQLAlchemyAircraftRepository(session)
        use_case = CreateAircraftUseCase(aircraft_repository)
        
        aircraft = await use_case.execute(
            registration=aircraft_data.registration,
            model=aircraft_data.model,
            manufacturer=aircraft_data.manufacturer,
            year=aircraft_data.year,
            capacity=aircraft_data.capacity
        )
        
        return AircraftResponse(**aircraft.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{aircraft_id}", response_model=AircraftResponse)
async def get_aircraft(
    aircraft_id: int,
    session: AsyncSession = Depends(get_database_session)
):
    """Get aircraft by ID"""
    try:
        aircraft_repository = SQLAlchemyAircraftRepository(session)
        use_case = GetAircraftUseCase(aircraft_repository)
        
        aircraft = await use_case.execute(aircraft_id)
        if not aircraft:
            raise HTTPException(status_code=404, detail="Aircraft not found")
        
        return AircraftResponse(**aircraft.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=List[AircraftResponse])
async def list_aircraft(
    session: AsyncSession = Depends(get_database_session)
):
    """List all aircraft"""
    try:
        aircraft_repository = SQLAlchemyAircraftRepository(session)
        use_case = ListAircraftUseCase(aircraft_repository)
        
        aircraft = await use_case.execute()
        return [AircraftResponse(**a.model_dump()) for a in aircraft]
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/available/", response_model=List[AircraftResponse])
async def list_available_aircraft(
    session: AsyncSession = Depends(get_database_session)
):
    """List available aircraft"""
    try:
        aircraft_repository = SQLAlchemyAircraftRepository(session)
        use_case = GetAvailableAircraftUseCase(aircraft_repository)
        
        aircraft = await use_case.execute()
        return [AircraftResponse(**a.model_dump()) for a in aircraft]
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")