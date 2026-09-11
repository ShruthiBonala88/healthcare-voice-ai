"""
<<<<<<< HEAD
Handles a single Twilio Media Stream WebSocket connection end-to-end:

  Twilio audio in -> VAD -> STT -> LangGraph agent -> TTS -> Twilio audio out

Implements barge-in (caller speaking cancels an in-flight agent turn or
TTS playback), end-of-turn silence detection, and an overall call timeout.
"""
import asyncio
import base64
import json
import time
=======
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
>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from app.agent.graph import run_agent_turn
from app.config import get_settings
<<<<<<< HEAD
from app.observability.call_events import log_call_event
from app.observability.logging_config import get_logger
from app.voice.call_control import transfer_call_to_human
from app.voice.stt import StreamingSTT
from app.voice.tts import StreamingTTS
from app.voice.vad import SilenceTracker, VoiceActivityDetector

logger = get_logger("stream_handler")


class CallSessionState:
    def __init__(self, call_sid: str, caller_number: str):
        self.call_sid = call_sid
        self.caller_number = caller_number
        self.conversation_state: dict = {}  # passed to / returned from LangGraph
        self.started_at = time.monotonic()
        self.speaking = False  # True while TTS audio is being played to caller
        self.barge_in_event = asyncio.Event()
        self.turn_task: Optional[asyncio.Task] = None  # currently running agent/TTS turn


async def handle_media_stream(websocket: WebSocket) -> None:
    await websocket.accept()
=======
from app.data.call_repository import add_message
from app.observability.call_events import log_call_event
from app.observability.logging_config import get_logger
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

        # Used for maximum call duration
        self.started_at = time.monotonic()

        # Whether TTS is currently speaking
        self.speaking = False

        # Used when caller interrupts TTS
        self.barge_in_event = asyncio.Event()

        # Stores μ-law audio chunks for one caller utterance
        self.audio_chunks: list[bytes] = []


# ================================================================
# μ-LAW → WAV
# ================================================================

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


# ================================================================
# WHISPER TRANSCRIPTION
# ================================================================

async def _transcribe_audio(audio_data: bytes) -> str:
    """
    Convert one complete caller utterance into text using Whisper.
    """

    if not audio_data:
        return ""

    audio_path = _mulaw_to_wav(audio_data)

    try:
        stt = get_stt()

        # Whisper is blocking.
        # Run it outside the asyncio event loop.
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

    Database writes are synchronous, so they are executed
    in a worker thread to avoid blocking the live voice pipeline.
    """

    try:
        await asyncio.to_thread(
            add_message,
            conversation_id,
            role,
            content,
        )

    except Exception:
        # Database persistence must never break the live call.
        logger.exception(
            "message_persistence_failed",
            call_sid=call_sid,
            conversation_id=conversation_id,
            role=role,
        )


# ================================================================
# MEDIA STREAM HANDLER
# ================================================================

async def handle_media_stream(websocket: WebSocket) -> None:
    """
    Handle one Twilio Media Stream WebSocket connection.
    """

    await websocket.accept()

>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0
    settings = get_settings()

    session: Optional[CallSessionState] = None
    stream_sid: Optional[str] = None
<<<<<<< HEAD
    vad = VoiceActivityDetector()
    silence = SilenceTracker()
    stt = StreamingSTT()
    tts = StreamingTTS()

    pending_transcript_parts: list[str] = []

    async def on_final_transcript(text: str) -> None:
        pending_transcript_parts.append(text)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("malformed_stream_message", raw=raw[:200])
                continue

            event = msg.get("event")

            if event == "start":
                call_sid = msg["start"]["callSid"]
                stream_sid = msg["start"]["streamSid"]
                caller_number = msg["start"].get("customParameters", {}).get("from", "unknown")
                session = CallSessionState(call_sid, caller_number)
                await log_call_event(call_sid, "call_started", {"caller": caller_number})
                await stt.start(on_final_transcript=on_final_transcript)

            elif event == "media" and session:
                # Elapsed-time guard
                if time.monotonic() - session.started_at > settings.max_call_duration_seconds:
                    await log_call_event(session.call_sid, "call_timeout")
                    break

                mulaw_chunk = base64.b64decode(msg["media"]["payload"])

                is_speech = vad.is_speech(mulaw_chunk)
                if is_speech:
                    silence.update(True)
                    # Barge-in: caller is talking while we're speaking OR
                    # still generating a reply. Cancel whichever is active
                    # and tell Twilio to drop any audio it has buffered.
                    turn_in_flight = session.turn_task is not None and not session.turn_task.done()
                    if (session.speaking or turn_in_flight) and not session.barge_in_event.is_set():
                        session.barge_in_event.set()
                        await _clear_twilio_playback(websocket, stream_sid)
                        if turn_in_flight:
                            session.turn_task.cancel()
                else:
                    silence.update(False)

                stt.send_audio(mulaw_chunk)

                if silence.end_of_turn and pending_transcript_parts:
                    user_text = " ".join(pending_transcript_parts).strip()
                    pending_transcript_parts.clear()
                    silence.reset()
                    session.barge_in_event.clear()
                    session.turn_task = asyncio.create_task(
                        _handle_turn(websocket, stream_sid, session, tts, user_text)
                    )

            elif event == "stop":
                if session:
                    await log_call_event(session.call_sid, "call_ended")
                    if session.turn_task and not session.turn_task.done():
                        session.turn_task.cancel()
                    await stt.finish()
                break

    except WebSocketDisconnect:
        if session:
            await log_call_event(session.call_sid, "call_disconnected")
            if session.turn_task and not session.turn_task.done():
                session.turn_task.cancel()
    finally:
        if session:
            await stt.finish()


async def _clear_twilio_playback(websocket: WebSocket, stream_sid: Optional[str]) -> None:
    """
    Tells Twilio to immediately drop any audio it has already buffered
    for playback on this stream. Without this, audio queued before a
    barge-in keeps playing to the caller even after we stop sending
    new chunks — this "clear" event is Twilio's documented way to flush it.
    """
    if not stream_sid:
        return
    try:
        await websocket.send_text(json.dumps({"event": "clear", "streamSid": stream_sid}))
    except Exception:
        logger.warning("failed_to_send_clear_event", stream_sid=stream_sid)

=======

    # Voice activity detector
    vad = VoiceActivityDetector()

    # Detect end of caller sentence
    silence = SilenceTracker()

    # Text-to-speech
    tts = StreamingTTS()

    try:

        # ========================================================
        # MAIN WEBSOCKET LOOP
        # ========================================================

        while True:

            raw = await websocket.receive_text()

            msg = json.loads(raw)

            event = msg.get("event")

            # ====================================================
            # CALL START
            # ====================================================

            if event == "start":

                start_data = msg.get("start", {})

                call_sid = start_data["callSid"]

                stream_sid = start_data["streamSid"]

                # Twilio custom parameters are sent by
                # /calls/incoming.
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

                    # We do NOT call log_call_event here because
                    # there is no valid internal call UUID yet.
                    break

                if not call_id:

                    logger.error(
                        "missing_call_id",
                        call_sid=call_sid,
                    )

                    # We do NOT call log_call_event here because
                    # there is no valid internal call UUID yet.
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

                    # Caller interrupts AI speech.
                    if session.speaking:

                        session.barge_in_event.set()

                    # Save caller audio.
                    session.audio_chunks.append(
                        mulaw_chunk
                    )

                    silence.update(True)

                else:

                    # If we already started collecting an
                    # utterance, keep silence chunks too so
                    # the audio remains continuous.
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

                    # Clear before processing the turn.
                    session.audio_chunks.clear()

                    silence.reset()

                    # ------------------------------------------------
                    # Whisper
                    # ------------------------------------------------

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
>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0

async def _handle_turn(
    websocket: WebSocket,
    stream_sid: str,
    session: CallSessionState,
    tts: StreamingTTS,
    user_text: str,
) -> None:
<<<<<<< HEAD
    await log_call_event(session.call_sid, "user_turn", {"text": user_text})

    try:
        agent_result = await run_agent_turn(
            call_sid=session.call_sid,
            caller_number=session.caller_number,
            user_text=user_text,
            state=session.conversation_state,
        )
    except asyncio.CancelledError:
        await log_call_event(session.call_sid, "turn_cancelled_barge_in")
        raise

    session.conversation_state = agent_result["state"]
    reply_text = agent_result["reply"]
    await log_call_event(session.call_sid, "assistant_turn", {"text": reply_text})

    if agent_result.get("handoff_requested"):
        await log_call_event(session.call_sid, "human_handoff_triggered")
        # Speak the handoff message if we can, then transfer via Twilio's
        # REST API. The transfer replaces this call's TwiML, which ends
        # the Media Stream from Twilio's side — nothing more to do here.
        try:
            await _speak(websocket, stream_sid, session, tts, reply_text)
        except asyncio.CancelledError:
            pass
        await asyncio.to_thread(transfer_call_to_human, session.call_sid)
        return

    try:
        await _speak(websocket, stream_sid, session, tts, reply_text)
    except asyncio.CancelledError:
        await log_call_event(session.call_sid, "tts_cancelled_barge_in")
        raise


async def _speak(
    websocket: WebSocket,
    stream_sid: str,
    session: CallSessionState,
    tts: StreamingTTS,
    text: str,
) -> None:
    session.speaking = True
    try:
        async for audio_chunk in tts.synthesize(text):
            if session.barge_in_event.is_set():
                await log_call_event(session.call_sid, "barge_in")
                break
=======
    """
    Process one complete caller turn.

    Flow:

    Caller speech
        ↓
    Whisper text
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
    # AI AGENT
    # ============================================================

    agent_result = await run_agent_turn(
        call_sid=session.call_sid,
        caller_number=session.caller_number,
        user_text=user_text,
        state=session.conversation_state,
    )

    # ------------------------------------------------------------
    # Update LangGraph conversation state
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
            # Caller started speaking while AI was talking
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
            # Send audio back to Twilio
            # ----------------------------------------------------

>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0
            await websocket.send_text(
                json.dumps(
                    {
                        "event": "media",
                        "streamSid": stream_sid,
<<<<<<< HEAD
                        "media": {"payload": base64.b64encode(audio_chunk).decode()},
                    }
                )
            )
    finally:
        session.speaking = False
=======
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
>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0
