"""FastAPI routers acting as controllers in the MVC architecture."""

from . import hello, test, tts, users

__all__ = ["users", "hello", "tts", "test"]
