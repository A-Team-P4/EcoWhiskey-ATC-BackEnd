from .models import User


class UserDomainService:
    """Domain service for User business logic"""

    @staticmethod
    def is_valid_email(email: str) -> bool:
        """Validate email format"""
        import re

        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    @staticmethod
    def generate_username(email: str) -> str:
        """Generate username from email"""
        return email.split('@')[0].lower()
