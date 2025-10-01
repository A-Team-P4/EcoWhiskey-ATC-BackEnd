"""User controller implementing CRUD endpoints."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.controllers.dependencies import CurrentUserDep, SessionDep
from app.models.user import User as UserModel
from app.utils import hash_password
from app.views import (
    UserRegistrationRequest,
    UserRegistrationResponse,
    UserResponse,
    UserUpdateRequest,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "/", response_model=UserRegistrationResponse, status_code=status.HTTP_201_CREATED
)
async def register_user(
    payload: UserRegistrationRequest,
    session: SessionDep,
) -> UserRegistrationResponse:
    result = await session.execute(
        select(UserModel).where(UserModel.email == payload.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email address already registered",
        )

    hashed_password = hash_password(payload.password)

    db_user = UserModel(
        email=payload.email,
        first_name=payload.firstName,
        last_name=payload.lastName,
        password_hash=hashed_password,
        account_type=payload.accountType,
        school=payload.school,
    )

    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)

    return UserRegistrationResponse(
        id=db_user.id,
        email=db_user.email,
        firstName=db_user.first_name,
        lastName=db_user.last_name,
        status=db_user.status,
        accountType=db_user.account_type,
        school=db_user.school,
        created_at=db_user.created_at,
        message="User registered successfully",
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: CurrentUserDep,
) -> UserResponse:
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        firstName=current_user.first_name,
        lastName=current_user.last_name,
        status=current_user.status,
        accountType=current_user.account_type,
        school=current_user.school,
        created_at=current_user.created_at,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    session: SessionDep,
    _current_user: CurrentUserDep,
) -> UserResponse:
    result = await session.execute(select(UserModel).where(UserModel.id == user_id))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return UserResponse(
        id=db_user.id,
        email=db_user.email,
        firstName=db_user.first_name,
        lastName=db_user.last_name,
        status=db_user.status,
        accountType=db_user.account_type,
        school=db_user.school,
        created_at=db_user.created_at,
    )


@router.get("/", response_model=List[UserResponse])
async def list_users(
    session: SessionDep,
    _current_user: CurrentUserDep,
) -> List[UserResponse]:
    result = await session.execute(select(UserModel))
    users = result.scalars().all()
    print(_current_user)
    return [
        UserResponse(
            id=user.id,
            email=user.email,
            firstName=user.first_name,
            lastName=user.last_name,
            status=user.status,
            accountType=user.account_type,
            school=user.school,
            created_at=user.created_at,
        )
        for user in users
    ]


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    session: SessionDep,
    _current_user: CurrentUserDep,
) -> UserResponse:
    result = await session.execute(select(UserModel).where(UserModel.id == user_id))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if payload.firstName is not None:
        db_user.first_name = payload.firstName
    if payload.lastName is not None:
        db_user.last_name = payload.lastName
    if payload.accountType is not None:
        db_user.account_type = payload.accountType
    if payload.school is not None:
        db_user.school = payload.school
    if payload.status is not None:
        db_user.status = payload.status
    if payload.password is not None:
        db_user.password_hash = hash_password(payload.password)

    await session.commit()
    await session.refresh(db_user)

    return UserResponse(
        id=db_user.id,
        email=db_user.email,
        firstName=db_user.first_name,
        lastName=db_user.last_name,
        status=db_user.status,
        accountType=db_user.account_type,
        school=db_user.school,
        created_at=db_user.created_at,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    session: SessionDep,
    _current_user: CurrentUserDep,
) -> Response:
    result = await session.execute(select(UserModel).where(UserModel.id == user_id))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    await session.delete(db_user)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
