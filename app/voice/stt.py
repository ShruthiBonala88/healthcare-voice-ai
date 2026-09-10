"""
Voxevia Speech-to-Text

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


class WhisperSTT:
    """
    Speech-to-text engine using faster-whisper.
    """

    def __init__(self):
        settings = get_settings()

        self.model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )

    def transcribe(self, audio_path: str) -> str:
        """
        Convert an audio file into text.
        """

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

    Loading the model is expensive, so we load it only once.
    """

    global _stt_instance

    if _stt_instance is None:
        _stt_instance = WhisperSTT()

    return _stt_instance