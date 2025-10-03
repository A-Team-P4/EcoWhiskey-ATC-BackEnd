"""FastAPI routers acting as controllers in the MVC architecture."""

from . import audio, auth, hello, test, tts, users

__all__ = ["audio", "auth", "hello", "test", "tts", "users"]
