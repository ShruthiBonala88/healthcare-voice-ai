"""
Streaming Speech-to-Text.

Uses Deepgram's realtime WebSocket API for Twilio Media Streams.

Flow:

Twilio Media Stream
        ↓
8 kHz μ-law audio
        ↓
Deepgram realtime STT
        ↓
Final transcript
        ↓
LangGraph agent
"""

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
    Realtime Speech-to-Text using Deepgram.

    Usage:

        stt = StreamingSTT()

        await stt.start(
            on_final_transcript=callback
        )

        stt.send_audio(mulaw_chunk)

        await stt.finish()
    """

    def __init__(self):
        settings = get_settings()

        self._client = DeepgramClient(
            settings.deepgram_api_key,
            DeepgramClientOptions(
                options={
                    "keepalive": "true",
                }
            ),
        )

        self._connection = None

    async def start(
        self,
        on_final_transcript,
        on_interim_transcript=None,
    ) -> None:
        """
        Start the Deepgram realtime WebSocket connection.
        """

        self._connection = (
            self._client.listen.asyncwebsocket.v("1")
        )

        async def _on_message(_, result, **kwargs):
            """
            Handle transcripts received from Deepgram.
            """

            try:
                sentence = (
                    result.channel.alternatives[0].transcript
                )
            except (AttributeError, IndexError):
                return

            if not sentence:
                return

            if result.is_final:
                await on_final_transcript(sentence)

            elif on_interim_transcript:
                await on_interim_transcript(sentence)

        self._connection.on(
            LiveTranscriptionEvents.Transcript,
            _on_message,
        )

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

        logger.info("deepgram_stt_started")

    def send_audio(self, mulaw_chunk: bytes) -> None:
        """
        Send a μ-law audio chunk to Deepgram.
        """

        if self._connection:
            self._connection.send(mulaw_chunk)

    async def finish(self) -> None:
        """
        Close the Deepgram realtime connection.
        """

        if self._connection:
            await self._connection.finish()
            self._connection = None

            logger.info("deepgram_stt_finished")
def get_stt() -> StreamingSTT:
    return StreamingSTT()