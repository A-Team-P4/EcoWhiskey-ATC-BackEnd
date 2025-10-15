"""Integration-style test scaffolding for the /audio/analyze endpoint."""

from __future__ import annotations

from pathlib import Path
import sys
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
AUDIO_SAMPLE = ROOT / "out.mp3"
sys.path.insert(0, str(ROOT))

from app.controllers.dependencies import get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.services.radio_tts import RadioTtsResult  # noqa: E402
from app.services.transcribe import TranscriptionResult  # noqa: E402


@pytest.fixture(autouse=True)
def override_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass authentication and external integrations for the test client."""

    async def fake_get_current_user():
        return object()

    app.dependency_overrides[get_current_user] = fake_get_current_user

    class FakeTranscribeService:
        async def transcribe_session_audio(self, *, session_id, audio_bytes, content_type):
            return TranscriptionResult(
                transcript="Test transcript",
                job_name="test-job",
                media_uri="s3://test-bucket/audio.mp3",
                transcript_uri="https://example.com/transcript.json",
                object_key="sessions/test/audio.mp3",
            )

    class FakeRadioTtsService:
        async def synthesize_readback(self, text):
            return RadioTtsResult(
                audio_bytes=b"fake-bytes",
                media_type="audio/wav",
                voice_id="TestVoice",
                sample_rate=16000,
            )

    async def fake_upload_readback_audio(session_id, audio_bytes, content_type, extension):
        return "sessions/test/audio.wav", "https://example.com/audio.wav"

    monkeypatch.setattr("app.controllers.audio._transcribe_service", FakeTranscribeService())
    monkeypatch.setattr("app.controllers.audio._radio_tts_service", FakeRadioTtsService())
    monkeypatch.setattr("app.controllers.audio.upload_readback_audio", fake_upload_readback_audio)

    yield

    app.dependency_overrides.clear()


def test_analyze_audio_uses_sample_file():
    """Uploads the bundled MP3 and verifies the happy-path response."""

    client = TestClient(app)

    with AUDIO_SAMPLE.open("rb") as audio_fp:
        response = client.post(
            "/audio/analyze",
            data={
                "session_id": str(uuid4()),
                "frequency": "118.00",
            },
            files={
                "audio_file": ("out.mp3", audio_fp, "audio/mpeg"),
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["frequency"] == "118.00"
    assert payload["audio_url"] == "https://example.com/audio.wav"
    assert "session_id" in payload
    assert payload["feedback"] == "Test transcript"
