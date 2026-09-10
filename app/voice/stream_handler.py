"""
Handles a single Twilio Media Stream WebSocket connection.

Flow:

Twilio audio
    ↓
VAD
    ↓
Collect caller audio
    ↓
End-of-turn silence
    ↓
Whisper STT
    ↓
LangGraph agent
    ↓
TTS
    ↓
Twilio audio
"""

import asyncio
import audioop
import base64
import json
import tempfile
import time
import wave
from pathlib import Path
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from app.agent.graph import run_agent_turn
from app.config import get_settings
from app.observability.call_events import log_call_event
from app.observability.logging_config import get_logger
from app.voice.stt import get_stt
from app.voice.tts import StreamingTTS
from app.voice.vad import SilenceTracker, VoiceActivityDetector


logger = get_logger("stream_handler")


class CallSessionState:
    """
    Stores information for one active phone call.
    """

    def __init__(self, call_sid: str, caller_number: str):
        self.call_sid = call_sid
        self.caller_number = caller_number
        self.conversation_state: dict = {}

        self.started_at = time.monotonic()

        self.speaking = False
        self.barge_in_event = asyncio.Event()

        # Stores μ-law audio chunks for one caller utterance.
        self.audio_chunks: list[bytes] = []


def _mulaw_to_wav(audio_data: bytes) -> str:
    """
    Convert Twilio 8 kHz μ-law audio into a temporary WAV file.

    faster-whisper can then transcribe the WAV file.
    """

    pcm_data = audioop.ulaw2lin(audio_data, 2)

    temp_file = tempfile.NamedTemporaryFile(
        suffix=".wav",
        delete=False,
    )
    temp_path = temp_file.name
    temp_file.close()

    with wave.open(temp_path, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(8000)
        wav_file.writeframes(pcm_data)

    return temp_path


async def _transcribe_audio(audio_data: bytes) -> str:
    """
    Convert one complete caller utterance into text using Whisper.
    """

    if not audio_data:
        return ""

    audio_path = _mulaw_to_wav(audio_data)

    try:
        stt = get_stt()

        # Whisper transcription is blocking, so run it outside
        # the asyncio event loop.
        text = await asyncio.to_thread(
            stt.transcribe,
            audio_path,
        )

        return text.strip()

    finally:
        path = Path(audio_path)

        if path.exists():
            path.unlink()


async def handle_media_stream(websocket: WebSocket) -> None:
    """
    Handle one Twilio Media Stream connection.
    """

    await websocket.accept()

    settings = get_settings()

    session: Optional[CallSessionState] = None
    stream_sid: Optional[str] = None

    vad = VoiceActivityDetector()
    silence = SilenceTracker()

    tts = StreamingTTS()

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)

            event = msg.get("event")

            # =====================================================
            # CALL START
            # =====================================================

            if event == "start":
                start_data = msg.get("start", {})

                call_sid = start_data["callSid"]
                stream_sid = start_data["streamSid"]

                caller_number = (
                    start_data
                    .get("customParameters", {})
                    .get("from", "unknown")
                )

                session = CallSessionState(
                    call_sid=call_sid,
                    caller_number=caller_number,
                )

                await log_call_event(
                    call_sid,
                    "call_started",
                    {"caller": caller_number},
                )

                logger.info(
                    "media_stream_started",
                    call_sid=call_sid,
                )

            # =====================================================
            # AUDIO FROM CALLER
            # =====================================================

            elif event == "media" and session:

                # -----------------------------------------------
                # Maximum call duration
                # -----------------------------------------------

                elapsed = (
                    time.monotonic()
                    - session.started_at
                )

                if elapsed > settings.max_call_duration_seconds:

                    await log_call_event(
                        session.call_sid,
                        "call_timeout",
                    )

                    break

                # -----------------------------------------------
                # Decode Twilio μ-law audio
                # -----------------------------------------------

                mulaw_chunk = base64.b64decode(
                    msg["media"]["payload"]
                )

                # -----------------------------------------------
                # Voice Activity Detection
                # -----------------------------------------------

                is_speech = vad.is_speech(
                    mulaw_chunk
                )

                if is_speech:

                    # Caller interrupts AI speech.
                    if session.speaking:
                        session.barge_in_event.set()

                    # Save caller audio.
                    session.audio_chunks.append(
                        mulaw_chunk
                    )

                    silence.update(True)

                else:
                    # If we already started collecting an utterance,
                    # keep silence chunks too so the audio remains
                    # continuous.
                    if session.audio_chunks:
                        session.audio_chunks.append(
                            mulaw_chunk
                        )

                    silence.update(False)

                # -----------------------------------------------
                # End of caller turn
                # -----------------------------------------------

                if (
                    silence.end_of_turn
                    and session.audio_chunks
                ):

                    audio_data = b"".join(
                        session.audio_chunks
                    )

                    # Clear before processing the turn.
                    session.audio_chunks.clear()
                    silence.reset()

                    user_text = await _transcribe_audio(
                        audio_data
                    )

                    if user_text:

                        await _handle_turn(
                            websocket=websocket,
                            stream_sid=stream_sid,
                            session=session,
                            tts=tts,
                            user_text=user_text,
                        )

            # =====================================================
            # CALL STOP
            # =====================================================

            elif event == "stop":

                if session:

                    # Process remaining audio before ending.
                    if session.audio_chunks:

                        audio_data = b"".join(
                            session.audio_chunks
                        )

                        session.audio_chunks.clear()

                        user_text = await _transcribe_audio(
                            audio_data
                        )

                        if user_text:

                            await _handle_turn(
                                websocket=websocket,
                                stream_sid=stream_sid,
                                session=session,
                                tts=tts,
                                user_text=user_text,
                            )

                    await log_call_event(
                        session.call_sid,
                        "call_ended",
                    )

                    logger.info(
                        "media_stream_ended",
                        call_sid=session.call_sid,
                    )

                break

    except WebSocketDisconnect:

        if session:

            await log_call_event(
                session.call_sid,
                "call_disconnected",
            )

            logger.info(
                "media_stream_disconnected",
                call_sid=session.call_sid,
            )

    except Exception:

        logger.exception(
            "media_stream_error"
        )

        if session:

            await log_call_event(
                session.call_sid,
                "media_stream_error",
            )

        raise


async def _handle_turn(
    websocket: WebSocket,
    stream_sid: str,
    session: CallSessionState,
    tts: StreamingTTS,
    user_text: str,
) -> None:
    """
    Process one complete caller turn.
    """

    await log_call_event(
        session.call_sid,
        "user_turn",
        {"text": user_text},
    )

    logger.info(
        "user_turn_received",
        call_sid=session.call_sid,
        text=user_text,
    )

    # =============================================================
    # AI AGENT
    # =============================================================

    agent_result = await run_agent_turn(
        call_sid=session.call_sid,
        caller_number=session.caller_number,
        user_text=user_text,
        state=session.conversation_state,
    )

    session.conversation_state = (
        agent_result["state"]
    )

    reply_text = agent_result["reply"]

    await log_call_event(
        session.call_sid,
        "assistant_turn",
        {"text": reply_text},
    )

    logger.info(
        "assistant_turn_generated",
        call_sid=session.call_sid,
        text=reply_text,
    )

    # =============================================================
    # TEXT-TO-SPEECH
    # =============================================================

    session.speaking = True
    session.barge_in_event.clear()

    try:

        async for audio_chunk in tts.synthesize(
            reply_text
        ):

            # Caller started speaking while AI was talking.
            if session.barge_in_event.is_set():

                await log_call_event(
                    session.call_sid,
                    "barge_in",
                )

                logger.info(
                    "barge_in_detected",
                    call_sid=session.call_sid,
                )

                break

            await websocket.send_text(
                json.dumps(
                    {
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {
                            "payload": (
                                base64.b64encode(
                                    audio_chunk
                                ).decode("utf-8")
                            )
                        },
                    }
                )
            )

    finally:

        session.speaking = False

    # =============================================================
    # HUMAN HANDOFF
    # =============================================================

    if agent_result.get("handoff_requested"):

        await log_call_event(
            session.call_sid,
            "human_handoff_triggered",
        )