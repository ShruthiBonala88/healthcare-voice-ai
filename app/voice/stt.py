"""
<<<<<<< HEAD
Streaming Speech-to-Text. Wraps Deepgram's realtime WebSocket API.
Swap the provider by implementing the same interface (start/send/finish)
against another vendor (Whisper streaming, Google STT, etc).
"""
from collections.abc import AsyncIterator
from typing import Optional

from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveOptions,
    LiveTranscriptionEvents,
)

from app.config import get_settings
from app.observability.logging_config import get_logger

logger = get_logger("stt")


class StreamingSTT:
    """
    Usage:
        stt = StreamingSTT()
        await stt.start(on_transcript=callback)
        stt.send_audio(mulaw_chunk)
        ...
        await stt.finish()
=======
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
>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0
    """

    def __init__(self):
        settings = get_settings()
<<<<<<< HEAD
        self._client = DeepgramClient(
            settings.deepgram_api_key, DeepgramClientOptions(options={"keepalive": "true"})
        )
        self._connection = None

    async def start(self, on_final_transcript, on_interim_transcript=None) -> None:
        self._connection = self._client.listen.asyncwebsocket.v("1")

        async def _on_message(_, result, **kwargs):
            sentence = result.channel.alternatives[0].transcript
            if not sentence:
                return
            if result.is_final:
                await on_final_transcript(sentence)
            elif on_interim_transcript:
                await on_interim_transcript(sentence)

        self._connection.on(LiveTranscriptionEvents.Transcript, _on_message)

        options = LiveOptions(
            model="nova-2-phonecall",
            language="en-US",
            encoding="mulaw",
            sample_rate=8000,
            channels=1,
            interim_results=True,
            endpointing=300,
            smart_format=True,
        )
        await self._connection.start(options)

    def send_audio(self, mulaw_chunk: bytes) -> None:
        if self._connection:
            self._connection.send(mulaw_chunk)

    async def finish(self) -> None:
        if self._connection:
            await self._connection.finish()
            self._connection = None
=======

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
>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0
