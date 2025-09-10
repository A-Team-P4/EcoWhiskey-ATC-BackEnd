from typing import List, Optional
from .models import User, Aircraft, Flight


class UserDomainService:
    """Domain service for User business logic"""
    
    @staticmethod
    def is_valid_email(email: str) -> bool:
        """Validate email format"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def can_user_access_system(user: User) -> bool:
        """Check if user can access the system"""
        return user.status == "active"
    
    @staticmethod
    def generate_username(email: str) -> str:
        """Generate username from email"""
        return email.split('@')[0].lower()


class AircraftDomainService:
    """Domain service for Aircraft business logic"""
    
    @staticmethod
    def is_aircraft_available(aircraft: Aircraft) -> bool:
        """Check if aircraft is available for flights"""
        return aircraft.status == "available"
    
    @staticmethod
    def calculate_flight_capacity(aircraft: Aircraft, safety_factor: float = 0.9) -> int:
        """Calculate effective flight capacity considering safety factors"""
        return int(aircraft.capacity * safety_factor)


class FlightDomainService:
    """Domain service for Flight business logic"""
    
    @staticmethod
    def is_flight_time_valid(departure_time, arrival_time) -> bool:
        """Validate that arrival time is after departure time"""
        return arrival_time > departure_time
    
    @staticmethod
    def can_aircraft_fly_route(aircraft: Aircraft, flight: Flight) -> bool:
        """Check if aircraft can handle the specific flight route"""
        # This would contain business rules about aircraft capabilities
        return AircraftDomainService.is_aircraft_available(aircraft)
    
    @staticmethod
    def generate_flight_number(origin: str, destination: str) -> str:
        """Generate flight number based on route"""
        import random
        return f"EW{origin[:2].upper()}{destination[:2].upper()}{random.randint(100, 999)}"