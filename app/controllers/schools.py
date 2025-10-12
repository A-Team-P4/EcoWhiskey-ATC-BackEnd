"""School controller offering CRUD operations for educational institutions."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.controllers.dependencies import CurrentUserDep, SessionDep
from app.models.school import School as SchoolModel
from app.views import (
    SchoolCreateRequest,
    SchoolResponse,
    SchoolUpdateRequest,
)

router = APIRouter(prefix="/schools", tags=["schools"])


@router.post("/", response_model=SchoolResponse, status_code=status.HTTP_201_CREATED)
async def create_school(
    payload: SchoolCreateRequest,
    session: SessionDep,
    _current_user: CurrentUserDep,
) -> SchoolResponse:
    name = payload.name.strip()
    location = payload.location.strip()

    if not name or not location:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Name and location cannot be empty",
        )

    existing = await session.execute(
        select(SchoolModel).where(func.lower(SchoolModel.name) == name.lower())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="School with this name already exists",
        )

    school = SchoolModel(name=name, location=location)
    session.add(school)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not create school",
        ) from exc

    await session.refresh(school)
    return SchoolResponse.model_validate(school)


@router.get("/", response_model=list[SchoolResponse])
async def list_schools(
    session: SessionDep,
    _current_user: CurrentUserDep,
) -> list[SchoolResponse]:
    result = await session.execute(select(SchoolModel).order_by(SchoolModel.name))
    schools = result.scalars().all()
    return [SchoolResponse.model_validate(school) for school in schools]


@router.get("/{school_id}", response_model=SchoolResponse)
async def get_school(
    school_id: int,
    session: SessionDep,
    _current_user: CurrentUserDep,
) -> SchoolResponse:
    result = await session.execute(
        select(SchoolModel).where(SchoolModel.id == school_id)
    )
    school = result.scalar_one_or_none()
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )
    return SchoolResponse.model_validate(school)


@router.put("/{school_id}", response_model=SchoolResponse)
async def update_school(
    school_id: int,
    payload: SchoolUpdateRequest,
    session: SessionDep,
    _current_user: CurrentUserDep,
) -> SchoolResponse:
    result = await session.execute(
        select(SchoolModel).where(SchoolModel.id == school_id)
    )
    school = result.scalar_one_or_none()
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    if payload.name is not None:
        new_name = payload.name.strip()
        if not new_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Name cannot be empty",
            )
        school.name = new_name
    if payload.location is not None:
        new_location = payload.location.strip()
        if not new_location:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Location cannot be empty",
            )
        school.location = new_location

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="School information conflicts with existing records",
        ) from exc

    await session.refresh(school)
    return SchoolResponse.model_validate(school)


@router.delete("/{school_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_school(
    school_id: int,
    session: SessionDep,
    _current_user: CurrentUserDep,
) -> Response:
    result = await session.execute(
        select(SchoolModel).where(SchoolModel.id == school_id)
    )
    school = result.scalar_one_or_none()
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    await session.delete(school)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
