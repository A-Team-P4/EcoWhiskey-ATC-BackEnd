"""Schema for text-to-speech requests."""

from typing import Optional

from pydantic import BaseModel


class TextToSpeechRequest(BaseModel):
    text: str
    voice_id: Optional[str] = None
