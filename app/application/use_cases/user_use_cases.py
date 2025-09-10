from typing import List, Optional
from app.domain.models import User, UserStatus
from app.domain.services import UserDomainService
from app.application.interfaces import UserRepositoryInterface


class CreateUserUseCase:
    """Use case for creating a new user"""
    
    def __init__(self, user_repository: UserRepositoryInterface):
        self.user_repository = user_repository
    
    async def execute(self, email: str, full_name: str, username: str = None) -> User:
        """Create a new user"""
        # Domain validation
        if not UserDomainService.is_valid_email(email):
            raise ValueError("Invalid email format")
        
        # Check if user already exists
        existing_user = await self.user_repository.get_by_email(email)
        if existing_user:
            raise ValueError("User with this email already exists")
        
        # Generate username if not provided
        if not username:
            username = UserDomainService.generate_username(email)
        
        # Create user
        user = User(
            email=email,
            username=username,
            full_name=full_name,
            status=UserStatus.ACTIVE
        )
        
        return await self.user_repository.create(user)


class GetUserUseCase:
    """Use case for retrieving a user"""
    
    def __init__(self, user_repository: UserRepositoryInterface):
        self.user_repository = user_repository
    
    async def execute(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return await self.user_repository.get_by_id(user_id)


class ListUsersUseCase:
    """Use case for listing all users"""
    
    def __init__(self, user_repository: UserRepositoryInterface):
        self.user_repository = user_repository
    
    async def execute(self) -> List[User]:
        """List all users"""
        return await self.user_repository.list_all()


class UpdateUserUseCase:
    """Use case for updating a user"""
    
    def __init__(self, user_repository: UserRepositoryInterface):
        self.user_repository = user_repository
    
    async def execute(self, user_id: int, **updates) -> Optional[User]:
        """Update user information"""
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        # Update fields
        for field, value in updates.items():
            if hasattr(user, field):
                setattr(user, field, value)
        
        # Validate email if it's being updated
        if 'email' in updates:
            if not UserDomainService.is_valid_email(user.email):
                raise ValueError("Invalid email format")
        
        return await self.user_repository.update(user)


class DeleteUserUseCase:
    """Use case for deleting a user"""
    
    def __init__(self, user_repository: UserRepositoryInterface):
        self.user_repository = user_repository
    
    async def execute(self, user_id: int) -> bool:
        """Delete user by ID"""
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        return await self.user_repository.delete(user_id)