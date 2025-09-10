from fastapi import APIRouter, HTTPException, Depends
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from app.presentation.dtos import UserCreateRequest, UserUpdateRequest, UserResponse, ErrorResponse
from app.application.use_cases.user_use_cases import (
    CreateUserUseCase, GetUserUseCase, ListUsersUseCase, 
    UpdateUserUseCase, DeleteUserUseCase
)
from app.infrastructure.persistence.repositories_sqlalchemy import SQLAlchemyUserRepository
from app.config.dependencies import get_database_session

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(
    user_data: UserCreateRequest,
    session: AsyncSession = Depends(get_database_session)
):
    """Create a new user"""
    try:
        user_repository = SQLAlchemyUserRepository(session)
        use_case = CreateUserUseCase(user_repository)
        
        user = await use_case.execute(
            email=user_data.email,
            full_name=user_data.full_name,
            username=user_data.username
        )
        
        return UserResponse(**user.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    session: AsyncSession = Depends(get_database_session)
):
    """Get user by ID"""
    try:
        user_repository = SQLAlchemyUserRepository(session)
        use_case = GetUserUseCase(user_repository)
        
        user = await use_case.execute(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return UserResponse(**user.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=List[UserResponse])
async def list_users(
    session: AsyncSession = Depends(get_database_session)
):
    """List all users"""
    try:
        user_repository = SQLAlchemyUserRepository(session)
        use_case = ListUsersUseCase(user_repository)
        
        users = await use_case.execute()
        return [UserResponse(**user.model_dump()) for user in users]
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdateRequest,
    session: AsyncSession = Depends(get_database_session)
):
    """Update user"""
    try:
        user_repository = SQLAlchemyUserRepository(session)
        use_case = UpdateUserUseCase(user_repository)
        
        # Filter out None values
        updates = {k: v for k, v in user_data.model_dump().items() if v is not None}
        
        user = await use_case.execute(user_id, **updates)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return UserResponse(**user.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    session: AsyncSession = Depends(get_database_session)
):
    """Delete user"""
    try:
        user_repository = SQLAlchemyUserRepository(session)
        use_case = DeleteUserUseCase(user_repository)
        
        success = await use_case.execute(user_id)
        if not success:
            raise HTTPException(status_code=404, detail="User not found")
        
        return None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")