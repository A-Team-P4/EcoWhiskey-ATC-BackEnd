from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime

from app.application.interfaces import (
    UserRepositoryInterface,
    HelloMessageRepositoryInterface,
)
from app.domain.models import User, HelloMessage


Base = declarative_base()


class UserEntity(Base):
    """SQLAlchemy User entity"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    full_name = Column(String)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class HelloMessageEntity(Base):
    """SQLAlchemy entity for hello-world messages"""

    __tablename__ = "hello_messages"

    id = Column(Integer, primary_key=True, index=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class SQLAlchemyUserRepository(UserRepositoryInterface):
    """SQLAlchemy implementation of User repository"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user: User) -> User:
        db_user = UserEntity(
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            status=user.status,
        )
        self.session.add(db_user)
        await self.session.commit()
        await self.session.refresh(db_user)
        return User.model_validate(db_user)

    async def get_by_id(self, user_id: int) -> Optional[User]:
        from sqlalchemy import select

        result = await self.session.execute(
            select(UserEntity).where(UserEntity.id == user_id)
        )
        db_user = result.scalar_one_or_none()
        return User.model_validate(db_user) if db_user else None

    async def get_by_email(self, email: str) -> Optional[User]:
        from sqlalchemy import select

        result = await self.session.execute(
            select(UserEntity).where(UserEntity.email == email)
        )
        db_user = result.scalar_one_or_none()
        return User.model_validate(db_user) if db_user else None

    async def list_all(self) -> List[User]:
        from sqlalchemy import select

        result = await self.session.execute(select(UserEntity))
        db_users = result.scalars().all()
        return [User.model_validate(db_user) for db_user in db_users]

    async def update(self, user: User) -> User:
        from sqlalchemy import select

        result = await self.session.execute(
            select(UserEntity).where(UserEntity.id == user.id)
        )
        db_user = result.scalar_one_or_none()
        if db_user:
            db_user.email = user.email
            db_user.username = user.username
            db_user.full_name = user.full_name
            db_user.status = user.status
            db_user.updated_at = datetime.utcnow()
            await self.session.commit()
            await self.session.refresh(db_user)
        return User.model_validate(db_user)

    async def delete(self, user_id: int) -> bool:
        from sqlalchemy import select

        result = await self.session.execute(
            select(UserEntity).where(UserEntity.id == user_id)
        )
        db_user = result.scalar_one_or_none()
        if db_user:
            await self.session.delete(db_user)
            await self.session.commit()
            return True
        return False


class SQLAlchemyHelloMessageRepository(HelloMessageRepositoryInterface):
    """SQLAlchemy implementation for hello-world messages"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, message: str) -> HelloMessage:
        db_message = HelloMessageEntity(message=message)
        self.session.add(db_message)
        await self.session.commit()
        await self.session.refresh(db_message)
        return HelloMessage.model_validate(db_message)

    async def list_recent(self, limit: int = 10) -> List[HelloMessage]:
        from sqlalchemy import select

        result = await self.session.execute(
            select(HelloMessageEntity)
            .order_by(HelloMessageEntity.created_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        return [HelloMessage.model_validate(row) for row in rows]


async def init_models(engine: AsyncEngine) -> None:
    """Create database tables if they do not exist"""

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
