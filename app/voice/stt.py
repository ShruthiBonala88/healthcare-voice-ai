"""
Voxevia Speech-to-Text.

Uses faster-whisper for speech recognition.

Flow:

Twilio audio
    ↓
VAD
    ↓
Audio segment
    ↓
Whisper
    ↓
Text
"""

from pathlib import Path

from faster_whisper import WhisperModel

from app.config import get_settings
from app.observability.logging_config import get_logger


logger = get_logger("stt")


class WhisperSTT:
    """
    Speech-to-text engine using faster-whisper.
    """

    def __init__(self):
        settings = get_settings()

        logger.info(
            "whisper_model_loading",
            model=settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )

        self.model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )

        logger.info(
            "whisper_model_loaded",
            model=settings.whisper_model,
        )

    def transcribe(self, audio_path: str) -> str:
        """
        Convert an audio file into text.
        """

        if not audio_path or not audio_path.strip():
            raise ValueError("audio_path is required.")

        path = Path(audio_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Audio file not found: {audio_path}"
            )

        segments, _info = self.model.transcribe(
            str(path),
            beam_size=5,
        )

        text = " ".join(
            segment.text
            for segment in segments
        )

        return text.strip()


_stt_instance: WhisperSTT | None = None


def get_stt() -> WhisperSTT:
    """
    Return one reusable Whisper STT instance.

    Loading the Whisper model is expensive,
    so the model is loaded only once.
    """

    global _stt_instance

    if _stt_instance is None:
        _stt_instance = WhisperSTT()

    return _stt_instance