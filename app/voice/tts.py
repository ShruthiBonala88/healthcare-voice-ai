"""
Text-to-Speech. Wraps ElevenLabs streaming API and returns mu-law 8kHz
audio chunks ready to forward directly into a Twilio media stream.
"""
from collections.abc import AsyncIterator

from elevenlabs.client import AsyncElevenLabs

from app.config import get_settings
from app.observability.logging_config import get_logger

logger = get_logger("tts")


class StreamingTTS:
    def __init__(self):
        settings = get_settings()
        self._client = AsyncElevenLabs(api_key=settings.elevenlabs_api_key)
        self._voice_id = settings.elevenlabs_voice_id

    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        """
        Streams audio chunks encoded as mu-law/8000 (Twilio-compatible)
        as they become available, so playback can start before the full
        reply has been synthesized.
        """
        stream = self._client.text_to_speech.convert_as_stream(
            voice_id=self._voice_id,
            text=text,
            model_id="eleven_turbo_v2_5",
            output_format="ulaw_8000",
        )
        async for chunk in stream:
            yield chunk
