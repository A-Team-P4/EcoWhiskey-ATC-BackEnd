"""FastAPI routers acting as controllers in the MVC architecture."""

from . import auth, users, hello, tts, test

__all__ = ["auth", "users", "hello", "tts", "test"]
