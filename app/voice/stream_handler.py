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

Database tracking:

Twilio Call
    ↓
Conversation
    ↓
Messages
    ↓
Call Events
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
from app.data.call_repository import add_message
from app.observability.call_events import log_call_event
from app.observability.logging_config import get_logger
from app.voice.call_control import transfer_call_to_human
from app.voice.stt import get_stt
from app.voice.tts import StreamingTTS
from app.voice.vad import SilenceTracker, VoiceActivityDetector


logger = get_logger("stream_handler")


# ================================================================
# CALL SESSION STATE
# ================================================================

class CallSessionState:
    """
    Stores information for one active phone call.
    """

    def __init__(
        self,
        call_sid: str,
        caller_number: str,
        conversation_id: str,
        call_id: str,
    ):
        # Twilio provider call ID
        self.call_sid = call_sid

        # Patient/caller phone number
        self.caller_number = caller_number

        # Internal Supabase conversation UUID
        self.conversation_id = conversation_id

        # Internal Supabase call UUID
        self.call_id = call_id

        # LangGraph conversation state
        self.conversation_state: dict = {}

        # Maximum call duration timer
        self.started_at = time.monotonic()

        # True while AI/TTS is speaking
        self.speaking = False

        # Caller interruption event
        self.barge_in_event = asyncio.Event()

        # μ-law audio chunks for current caller utterance
        self.audio_chunks: list[bytes] = []


# ================================================================
# μ-LAW → WAV
# ================================================================

def _mulaw_to_wav(audio_data: bytes) -> str:
    """
    Convert Twilio 8 kHz μ-law audio into a temporary WAV file.

    Whisper can then transcribe the WAV file.
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


# ================================================================
# WHISPER TRANSCRIPTION
# ================================================================

async def _transcribe_audio(audio_data: bytes) -> str:
    """
    Transcribe one complete caller utterance using Whisper.
    """

    if not audio_data:
        return ""

    audio_path = _mulaw_to_wav(audio_data)

    try:
        stt = get_stt()

        # Whisper is blocking, so run it outside
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


# ================================================================
# SAVE MESSAGE
# ================================================================

async def _save_message(
    conversation_id: str,
    role: str,
    content: str,
    call_sid: str,
) -> None:
    """
    Save a conversation message to Supabase.

    Database failures must never break the live call.
    """

    try:
        await asyncio.to_thread(
            add_message,
            conversation_id,
            role,
            content,
        )

    except Exception:
        logger.exception(
            "message_persistence_failed",
            call_sid=call_sid,
            conversation_id=conversation_id,
            role=role,
        )


# ================================================================
# CLEAR TWILIO PLAYBACK
# ================================================================

async def _clear_twilio_playback(
    websocket: WebSocket,
    stream_sid: Optional[str],
) -> None:
    """
    Tell Twilio to immediately clear queued audio.

    Used when the caller interrupts AI speech.
    """

    if not stream_sid:
        return

    try:
        await websocket.send_text(
            json.dumps(
                {
                    "event": "clear",
                    "streamSid": stream_sid,
                }
            )
        )

    except Exception:
        logger.warning(
            "failed_to_send_clear_event",
            stream_sid=stream_sid,
        )


# ================================================================
# MEDIA STREAM HANDLER
# ================================================================

async def handle_media_stream(websocket: WebSocket) -> None:
    """
    Handle one Twilio Media Stream WebSocket connection.
    """

    await websocket.accept()

    settings = get_settings()

    session: Optional[CallSessionState] = None
    stream_sid: Optional[str] = None

    # Voice Activity Detector
    vad = VoiceActivityDetector()

    # End-of-turn silence detector
    silence = SilenceTracker()

    # Text-to-speech
    tts = StreamingTTS()

    try:

        # ========================================================
        # MAIN WEBSOCKET LOOP
        # ========================================================

        while True:

            raw = await websocket.receive_text()

            try:
                msg = json.loads(raw)

            except json.JSONDecodeError:
                logger.warning(
                    "malformed_stream_message",
                    raw=raw[:200],
                )
                continue

            event = msg.get("event")

            # ====================================================
            # CALL START
            # ====================================================

            if event == "start":

                start_data = msg.get("start", {})

                call_sid = start_data["callSid"]

                stream_sid = start_data["streamSid"]

                # Twilio custom parameters
                custom_parameters = start_data.get(
                    "customParameters",
                    {},
                )

                caller_number = custom_parameters.get(
                    "from",
                    "unknown",
                )

                conversation_id = custom_parameters.get(
                    "conversation_id",
                )

                call_id = custom_parameters.get(
                    "call_id",
                )

                # ------------------------------------------------
                # Validate database identifiers
                # ------------------------------------------------

                if not conversation_id:

                    logger.error(
                        "missing_conversation_id",
                        call_sid=call_sid,
                    )

                    break

                if not call_id:

                    logger.error(
                        "missing_call_id",
                        call_sid=call_sid,
                    )

                    break

                # ------------------------------------------------
                # Create active session
                # ------------------------------------------------

                session = CallSessionState(
                    call_sid=call_sid,
                    caller_number=caller_number,
                    conversation_id=conversation_id,
                    call_id=call_id,
                )

                # ------------------------------------------------
                # Database event
                # ------------------------------------------------

                await log_call_event(
                    session.call_id,
                    "call_started",
                    {
                        "caller": caller_number,
                        "conversation_id": conversation_id,
                        "call_sid": call_sid,
                    },
                )

                logger.info(
                    "media_stream_started",
                    call_sid=call_sid,
                    conversation_id=conversation_id,
                    call_id=call_id,
                )

            # ====================================================
            # AUDIO FROM CALLER
            # ====================================================

            elif event == "media" and session:

                # ------------------------------------------------
                # Maximum call duration
                # ------------------------------------------------

                elapsed = (
                    time.monotonic()
                    - session.started_at
                )

                if elapsed > settings.max_call_duration_seconds:

                    await log_call_event(
                        session.call_id,
                        "call_timeout",
                        {
                            "duration_seconds": int(elapsed),
                        },
                    )

                    logger.warning(
                        "call_timeout",
                        call_sid=session.call_sid,
                        call_id=session.call_id,
                        duration_seconds=int(elapsed),
                    )

                    break

                # ------------------------------------------------
                # Decode Twilio μ-law audio
                # ------------------------------------------------

                try:

                    mulaw_chunk = base64.b64decode(
                        msg["media"]["payload"]
                    )

                except Exception:

                    logger.exception(
                        "invalid_media_payload",
                        call_sid=session.call_sid,
                    )

                    await log_call_event(
                        session.call_id,
                        "media_stream_error",
                        {
                            "error": "Invalid media payload",
                        },
                    )

                    continue

                # ------------------------------------------------
                # Voice Activity Detection
                # ------------------------------------------------

                is_speech = vad.is_speech(
                    mulaw_chunk
                )

                if is_speech:

                    # Caller is speaking while AI is speaking.
                    if session.speaking:

                        session.barge_in_event.set()

                        await _clear_twilio_playback(
                            websocket,
                            stream_sid,
                        )

                    # Save caller audio
                    session.audio_chunks.append(
                        mulaw_chunk
                    )

                    silence.update(True)

                else:

                    # Keep silence chunks when an utterance
                    # has already started.
                    if session.audio_chunks:

                        session.audio_chunks.append(
                            mulaw_chunk
                        )

                    silence.update(False)

                # ------------------------------------------------
                # End of caller turn
                # ------------------------------------------------

                if (
                    silence.end_of_turn
                    and session.audio_chunks
                ):

                    audio_data = b"".join(
                        session.audio_chunks
                    )

                    session.audio_chunks.clear()

                    silence.reset()

                    # ------------------------------------------------
                    # Whisper STT
                    # ------------------------------------------------

                    user_text = await _transcribe_audio(
                        audio_data
                    )

                    if user_text:

                        # ------------------------------------------------
                        # Handle AI turn
                        # ------------------------------------------------

                        try:

                            await _handle_turn(
                                websocket=websocket,
                                stream_sid=stream_sid,
                                session=session,
                                tts=tts,
                                user_text=user_text,
                            )

                        except asyncio.CancelledError:

                            logger.info(
                                "turn_cancelled",
                                call_sid=session.call_sid,
                                call_id=session.call_id,
                            )

            # ====================================================
            # CALL STOP
            # ====================================================

            elif event == "stop":

                if session:

                    # ------------------------------------------------
                    # Process remaining audio
                    # ------------------------------------------------

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

                    # ------------------------------------------------
                    # Calculate duration
                    # ------------------------------------------------

                    duration_seconds = int(
                        time.monotonic()
                        - session.started_at
                    )

                    # ------------------------------------------------
                    # Call ended event
                    # ------------------------------------------------

                    await log_call_event(
                        session.call_id,
                        "call_ended",
                        {
                            "duration_seconds": duration_seconds,
                        },
                    )

                    logger.info(
                        "media_stream_ended",
                        call_sid=session.call_sid,
                        call_id=session.call_id,
                        duration_seconds=duration_seconds,
                    )

                break

    # ============================================================
    # WEBSOCKET DISCONNECTED
    # ============================================================

    except WebSocketDisconnect:

        if session:

            duration_seconds = int(
                time.monotonic()
                - session.started_at
            )

            await log_call_event(
                session.call_id,
                "call_disconnected",
                {
                    "duration_seconds": duration_seconds,
                },
            )

            logger.info(
                "media_stream_disconnected",
                call_sid=session.call_sid,
                call_id=session.call_id,
            )

    # ============================================================
    # UNEXPECTED ERROR
    # ============================================================

    except Exception:

        logger.exception(
            "media_stream_error",
        )

        if session:

            await log_call_event(
                session.call_id,
                "media_stream_error",
            )

        raise


# ================================================================
# HANDLE ONE COMPLETE CALLER TURN
# ================================================================

async def _handle_turn(
    websocket: WebSocket,
    stream_sid: str,
    session: CallSessionState,
    tts: StreamingTTS,
    user_text: str,
) -> None:
    """
    Process one complete caller turn.

    Caller speech
        ↓
    Save user message
        ↓
    LangGraph
        ↓
    Save assistant message
        ↓
    TTS
        ↓
    Twilio
    """

    # ============================================================
    # USER TURN EVENT
    # ============================================================

    await log_call_event(
        session.call_id,
        "user_turn",
        {
            "text": user_text,
        },
    )

    logger.info(
        "user_turn_received",
        call_sid=session.call_sid,
        call_id=session.call_id,
        text=user_text,
    )

    # ============================================================
    # SAVE USER MESSAGE
    # ============================================================

    await _save_message(
        conversation_id=session.conversation_id,
        role="user",
        content=user_text,
        call_sid=session.call_sid,
    )

    # ============================================================
    # LANGGRAPH AGENT
    # ============================================================

    try:

        agent_result = await run_agent_turn(
            call_sid=session.call_sid,
            caller_number=session.caller_number,
            user_text=user_text,
            state=session.conversation_state,
        )

    except asyncio.CancelledError:

        await log_call_event(
            session.call_id,
            "turn_cancelled_barge_in",
        )

        raise

    # ------------------------------------------------------------
    # Update conversation state
    # ------------------------------------------------------------

    session.conversation_state = (
        agent_result["state"]
    )

    reply_text = agent_result["reply"]

    # ============================================================
    # ASSISTANT TURN EVENT
    # ============================================================

    await log_call_event(
        session.call_id,
        "assistant_turn",
        {
            "text": reply_text,
        },
    )

    logger.info(
        "assistant_turn_generated",
        call_sid=session.call_sid,
        call_id=session.call_id,
        text=reply_text,
    )

    # ============================================================
    # SAVE ASSISTANT MESSAGE
    # ============================================================

    await _save_message(
        conversation_id=session.conversation_id,
        role="assistant",
        content=reply_text,
        call_sid=session.call_sid,
    )

    # ============================================================
    # TEXT-TO-SPEECH
    # ============================================================

    session.speaking = True

    session.barge_in_event.clear()

    try:

        async for audio_chunk in tts.synthesize(
            reply_text
        ):

            # ----------------------------------------------------
            # Caller interrupted AI
            # ----------------------------------------------------

            if session.barge_in_event.is_set():

                await log_call_event(
                    session.call_id,
                    "barge_in",
                )

                logger.info(
                    "barge_in_detected",
                    call_sid=session.call_sid,
                    call_id=session.call_id,
                )

                break

            # ----------------------------------------------------
            # Send audio to Twilio
            # ----------------------------------------------------

            await websocket.send_text(
                json.dumps(
                    {
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {
                            "payload": base64.b64encode(
                                audio_chunk
                            ).decode("utf-8")
                        },
                    }
                )
            )

    finally:

        session.speaking = False

    # ============================================================
    # HUMAN HANDOFF
    # ============================================================

    if agent_result.get("handoff_requested"):

        await log_call_event(
            session.call_id,
            "human_handoff_triggered",
        )

        logger.info(
            "human_handoff_triggered",
            call_sid=session.call_sid,
            call_id=session.call_id,
        )

        try:

            await asyncio.to_thread(
                transfer_call_to_human,
                session.call_sid,
            )

        except Exception:

            logger.exception(
                "human_handoff_failed",
                call_sid=session.call_sid,
                call_id=session.call_id,
            )