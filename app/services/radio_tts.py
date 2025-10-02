"""Amazon Polly TTS with ATC radio-style post-processing."""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from html import escape as html_escape
from typing import Any

import numpy as np
from botocore.exceptions import BotoCoreError, ClientError
from fastapi.concurrency import run_in_threadpool
from scipy.signal import butter, sosfiltfilt

from app.config.settings import settings
from app.services.aws import create_boto3_client

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RadioTtsResult:
    """Synthesised audio bytes representing the radio-filtered speech."""

    audio_bytes: bytes
    media_type: str
    voice_id: str
    sample_rate: int


class RadioTtsError(RuntimeError):
    """Raised when the Polly-based readback generation fails."""


_polly_client = create_boto3_client("polly", region_name=settings.polly.region)


class RadioTtsService:
    """Generate readback audio with a radio effect using Amazon Polly."""

    def __init__(
        self,
        *,
        default_voice_id: str = settings.polly.default_voice_id,
        sample_rate: int = 16000,
        noise_db: float = -32.0,
        tail_noise_db: float = -28.0,
    ) -> None:
        self._default_voice_id = default_voice_id
        self._sample_rate = sample_rate
        self._noise_db = noise_db
        self._tail_noise_db = tail_noise_db

    async def synthesize_readback(
        self,
        text: str,
        *,
        voice_id: str | None = None,
        rate: float = 0.9,
        pitch: int = 0,
    ) -> RadioTtsResult:
        """Convert text to speech, apply radio FX, and return WAV bytes."""

        voice = voice_id or self._default_voice_id
        ssml = self._build_ssml(text, rate=rate, pitch=pitch)
        pcm = await self._synthesize_pcm(ssml, voice)
        processed = await run_in_threadpool(self._apply_radio_fx, pcm)
        wav_bytes = await run_in_threadpool(self._to_wav_bytes, processed)
        return RadioTtsResult(
            audio_bytes=wav_bytes,
            media_type="audio/wav",
            voice_id=voice,
            sample_rate=self._sample_rate,
        )

    def _build_ssml(self, text: str, *, rate: float, pitch: int) -> str:
        rate_pct = max(60, min(140, int(round(rate * 100))))
        pitch_val = max(-50, min(50, int(pitch)))
        prosody_attrs: list[str] = []
        if rate_pct != 100:
            prosody_attrs.append(f'rate="{rate_pct}%"')
        if pitch_val != 0:
            prosody_attrs.append(f'pitch="{pitch_val}%"')
        if prosody_attrs:
            attr_str = " ".join(prosody_attrs)
            return f"<speak><prosody {attr_str}>{html_escape(text)}</prosody></speak>"
        return f"<speak>{html_escape(text)}</speak>"

    async def _synthesize_pcm(self, ssml: str, voice_id: str) -> np.ndarray:
        try:
            response: dict[str, Any] = await run_in_threadpool(
                _polly_client.synthesize_speech,
                TextType="ssml",
                Text=ssml,
                VoiceId=voice_id,
                Engine="neural",
                OutputFormat="pcm",
                SampleRate=str(self._sample_rate),
            )
        except (BotoCoreError, ClientError) as exc:
            logger.exception("Polly synth failed for voice '%s'", voice_id)
            raise RadioTtsError(f"Failed to synthesize speech: {exc}") from exc

        audio_stream = response.get("AudioStream")
        if audio_stream is None:
            raise RadioTtsError("Polly returned no audio stream.")
        pcm_bytes = audio_stream.read()
        if not pcm_bytes:
            raise RadioTtsError("Polly returned an empty audio stream.")

        audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        return audio

    def _apply_radio_fx(self, audio: np.ndarray) -> np.ndarray:
        filtered = self._bandpass(audio)
        compressed = self._soft_compress(filtered)
        hiss = self._add_hiss(compressed)
        tail = self._squelch_tail()
        return np.concatenate([hiss, tail], axis=0)

    def _bandpass(
        self,
        audio: np.ndarray,
        lo: int = 300,
        hi: int = 3000,
        order: int = 4,
    ) -> np.ndarray:
        nyquist = self._sample_rate / 2
        sos = butter(
            order,
            [lo / nyquist, hi / nyquist],
            btype="bandpass",
            output="sos",
        )
        return sosfiltfilt(sos, audio)

    def _soft_compress(
        self,
        audio: np.ndarray,
        thresh_db: float = -14.0,
        ratio: float = 3.0,
        win_ms: int = 10,
    ) -> np.ndarray:
        n = max(1, int(self._sample_rate * win_ms / 1000))
        kernel = np.ones(n, dtype=np.float32) / n
        rms = np.sqrt(np.maximum(1e-9, np.convolve(audio**2, kernel, mode="same")))
        level_db = 20 * np.log10(rms + 1e-9)
        over = np.maximum(0.0, level_db - thresh_db)
        gain_db = -over * (1.0 - 1.0 / ratio)
        gain = 10 ** (gain_db / 20.0)
        return audio * gain

    def _add_hiss(self, audio: np.ndarray) -> np.ndarray:
        noise_rms_target = 10 ** (self._noise_db / 20.0)
        noise = np.random.normal(0.0, 1.0, size=audio.shape).astype(np.float32)
        noise *= noise_rms_target / (np.sqrt(np.mean(noise**2) + 1e-9))
        return audio + noise

    def _squelch_tail(self, tail_ms: int = 70) -> np.ndarray:
        n = int(self._sample_rate * tail_ms / 1000)
        tail = np.random.normal(0.0, 1.0, size=n).astype(np.float32)
        tail *= (10 ** (self._tail_noise_db / 20.0)) / (
            np.sqrt(np.mean(tail**2) + 1e-9)
        )
        envelope = np.exp(-np.linspace(0, 5, n)).astype(np.float32)
        return tail * envelope

    def _to_wav_bytes(self, audio: np.ndarray) -> bytes:
        import wave

        audio = np.clip(audio, -1.0, 1.0)
        pcm16 = (audio * 32767.0).astype(np.int16)
        with io.BytesIO() as buffer:
            with wave.open(buffer, "wb") as wave_file:
                wave_file.setnchannels(1)
                wave_file.setsampwidth(2)
                wave_file.setframerate(self._sample_rate)
                wave_file.writeframes(pcm16.tobytes())
            return buffer.getvalue()


def get_radio_tts_service() -> RadioTtsService:
    """Return the default radio TTS service instance."""

    return _DEFAULT_SERVICE


_DEFAULT_SERVICE = RadioTtsService()


__all__ = [
    "RadioTtsService",
    "RadioTtsResult",
    "RadioTtsError",
    "get_radio_tts_service",
]
