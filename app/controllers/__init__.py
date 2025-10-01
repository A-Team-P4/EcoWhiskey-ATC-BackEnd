"""FastAPI routers acting as controllers in the MVC architecture."""

from . import auth, hello, test, tts, users

__all__ = ["auth", "hello", "test", "tts", "users"]
