from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.asyncio import create_async_engine
from datetime import datetime

from app.application.interfaces import UserRepositoryInterface, AircraftRepositoryInterface, FlightRepositoryInterface
from app.domain.models import User, Aircraft, Flight

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


class AircraftEntity(Base):
    """SQLAlchemy Aircraft entity"""
    __tablename__ = "aircraft"
    
    id = Column(Integer, primary_key=True, index=True)
    registration = Column(String, unique=True, index=True)
    model = Column(String)
    manufacturer = Column(String)
    year = Column(Integer)
    capacity = Column(Integer)
    status = Column(String, default="available")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FlightEntity(Base):
    """SQLAlchemy Flight entity"""
    __tablename__ = "flights"
    
    id = Column(Integer, primary_key=True, index=True)
    flight_number = Column(String, unique=True, index=True)
    aircraft_id = Column(Integer, ForeignKey("aircraft.id"))
    origin = Column(String)
    destination = Column(String)
    departure_time = Column(DateTime)
    arrival_time = Column(DateTime)
    status = Column(String, default="scheduled")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SQLAlchemyUserRepository(UserRepositoryInterface):
    """SQLAlchemy implementation of User repository"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, user: User) -> User:
        db_user = UserEntity(
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            status=user.status
        )
        self.session.add(db_user)
        await self.session.commit()
        await self.session.refresh(db_user)
        return User.model_validate(db_user)
    
    async def get_by_id(self, user_id: int) -> Optional[User]:
        from sqlalchemy import select
        result = await self.session.execute(select(UserEntity).where(UserEntity.id == user_id))
        db_user = result.scalar_one_or_none()
        return User.model_validate(db_user) if db_user else None
    
    async def get_by_email(self, email: str) -> Optional[User]:
        from sqlalchemy import select
        result = await self.session.execute(select(UserEntity).where(UserEntity.email == email))
        db_user = result.scalar_one_or_none()
        return User.model_validate(db_user) if db_user else None
    
    async def list_all(self) -> List[User]:
        from sqlalchemy import select
        result = await self.session.execute(select(UserEntity))
        db_users = result.scalars().all()
        return [User.model_validate(db_user) for db_user in db_users]
    
    async def update(self, user: User) -> User:
        from sqlalchemy import select
        result = await self.session.execute(select(UserEntity).where(UserEntity.id == user.id))
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
        result = await self.session.execute(select(UserEntity).where(UserEntity.id == user_id))
        db_user = result.scalar_one_or_none()
        if db_user:
            await self.session.delete(db_user)
            await self.session.commit()
            return True
        return False


class SQLAlchemyAircraftRepository(AircraftRepositoryInterface):
    """SQLAlchemy implementation of Aircraft repository"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, aircraft: Aircraft) -> Aircraft:
        db_aircraft = AircraftEntity(
            registration=aircraft.registration,
            model=aircraft.model,
            manufacturer=aircraft.manufacturer,
            year=aircraft.year,
            capacity=aircraft.capacity,
            status=aircraft.status
        )
        self.session.add(db_aircraft)
        await self.session.commit()
        await self.session.refresh(db_aircraft)
        return Aircraft.model_validate(db_aircraft)
    
    async def get_by_id(self, aircraft_id: int) -> Optional[Aircraft]:
        from sqlalchemy import select
        result = await self.session.execute(select(AircraftEntity).where(AircraftEntity.id == aircraft_id))
        db_aircraft = result.scalar_one_or_none()
        return Aircraft.model_validate(db_aircraft) if db_aircraft else None
    
    async def get_by_registration(self, registration: str) -> Optional[Aircraft]:
        from sqlalchemy import select
        result = await self.session.execute(select(AircraftEntity).where(AircraftEntity.registration == registration))
        db_aircraft = result.scalar_one_or_none()
        return Aircraft.model_validate(db_aircraft) if db_aircraft else None
    
    async def list_all(self) -> List[Aircraft]:
        from sqlalchemy import select
        result = await self.session.execute(select(AircraftEntity))
        db_aircraft = result.scalars().all()
        return [Aircraft.model_validate(db_aircraft) for db_aircraft in db_aircraft]
    
    async def update(self, aircraft: Aircraft) -> Aircraft:
        from sqlalchemy import select
        result = await self.session.execute(select(AircraftEntity).where(AircraftEntity.id == aircraft.id))
        db_aircraft = result.scalar_one_or_none()
        if db_aircraft:
            db_aircraft.registration = aircraft.registration
            db_aircraft.model = aircraft.model
            db_aircraft.manufacturer = aircraft.manufacturer
            db_aircraft.year = aircraft.year
            db_aircraft.capacity = aircraft.capacity
            db_aircraft.status = aircraft.status
            db_aircraft.updated_at = datetime.utcnow()
            await self.session.commit()
            await self.session.refresh(db_aircraft)
        return Aircraft.model_validate(db_aircraft)
    
    async def delete(self, aircraft_id: int) -> bool:
        from sqlalchemy import select
        result = await self.session.execute(select(AircraftEntity).where(AircraftEntity.id == aircraft_id))
        db_aircraft = result.scalar_one_or_none()
        if db_aircraft:
            await self.session.delete(db_aircraft)
            await self.session.commit()
            return True
        return False


class SQLAlchemyFlightRepository(FlightRepositoryInterface):
    """SQLAlchemy implementation of Flight repository"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, flight: Flight) -> Flight:
        db_flight = FlightEntity(
            flight_number=flight.flight_number,
            aircraft_id=flight.aircraft_id,
            origin=flight.origin,
            destination=flight.destination,
            departure_time=flight.departure_time,
            arrival_time=flight.arrival_time,
            status=flight.status
        )
        self.session.add(db_flight)
        await self.session.commit()
        await self.session.refresh(db_flight)
        return Flight.model_validate(db_flight)
    
    async def get_by_id(self, flight_id: int) -> Optional[Flight]:
        from sqlalchemy import select
        result = await self.session.execute(select(FlightEntity).where(FlightEntity.id == flight_id))
        db_flight = result.scalar_one_or_none()
        return Flight.model_validate(db_flight) if db_flight else None
    
    async def get_by_flight_number(self, flight_number: str) -> Optional[Flight]:
        from sqlalchemy import select
        result = await self.session.execute(select(FlightEntity).where(FlightEntity.flight_number == flight_number))
        db_flight = result.scalar_one_or_none()
        return Flight.model_validate(db_flight) if db_flight else None
    
    async def list_all(self) -> List[Flight]:
        from sqlalchemy import select
        result = await self.session.execute(select(FlightEntity))
        db_flights = result.scalars().all()
        return [Flight.model_validate(db_flight) for db_flight in db_flights]
    
    async def update(self, flight: Flight) -> Flight:
        from sqlalchemy import select
        result = await self.session.execute(select(FlightEntity).where(FlightEntity.id == flight.id))
        db_flight = result.scalar_one_or_none()
        if db_flight:
            db_flight.flight_number = flight.flight_number
            db_flight.aircraft_id = flight.aircraft_id
            db_flight.origin = flight.origin
            db_flight.destination = flight.destination
            db_flight.departure_time = flight.departure_time
            db_flight.arrival_time = flight.arrival_time
            db_flight.status = flight.status
            db_flight.updated_at = datetime.utcnow()
            await self.session.commit()
            await self.session.refresh(db_flight)
        return Flight.model_validate(db_flight)
    
    async def delete(self, flight_id: int) -> bool:
        from sqlalchemy import select
        result = await self.session.execute(select(FlightEntity).where(FlightEntity.id == flight_id))
        db_flight = result.scalar_one_or_none()
        if db_flight:
            await self.session.delete(db_flight)
            await self.session.commit()
            return True
        return False