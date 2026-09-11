"""Whisper speech-to-text adapter for recorded Twilio utterances."""

from pathlib import Path

from faster_whisper import WhisperModel

from app.config import get_settings


class WhisperSTT:
    def __init__(self):
        settings = get_settings()
        self.model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )

    def transcribe(self, audio_path: str) -> str:
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        segments, _ = self.model.transcribe(str(path), beam_size=5)
        return " ".join(segment.text for segment in segments).strip()


_stt_instance: WhisperSTT | None = None


def get_stt() -> WhisperSTT:
    global _stt_instance
    if _stt_instance is None:
        _stt_instance = WhisperSTT()
    return _stt_instance
