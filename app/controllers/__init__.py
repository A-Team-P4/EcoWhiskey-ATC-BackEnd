"""FastAPI routers acting as controllers in the MVC architecture."""

from . import audio, auth, hello, schools, test, tts, users

__all__ = ["audio", "auth", "hello", "schools", "test", "tts", "users"]
