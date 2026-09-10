"""
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
    """

    def __init__(self):
        settings = get_settings()
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
