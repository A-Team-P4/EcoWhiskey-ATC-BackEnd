"""FastAPI routers acting as controllers in the MVC architecture."""

from . import users, hello, tts, test

__all__ = ["users", "hello", "tts", "test"]
