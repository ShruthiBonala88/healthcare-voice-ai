"""
Handles a single Twilio Media Stream WebSocket connection end-to-end:

  Twilio audio in -> VAD -> STT -> LangGraph agent -> TTS -> Twilio audio out

Implements barge-in (caller speaking cancels an in-flight agent turn or
TTS playback), end-of-turn silence detection, and an overall call timeout.
"""
import asyncio
import base64
import json
import time
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from app.agent.graph import run_agent_turn
from app.config import get_settings
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
    settings = get_settings()

    session: Optional[CallSessionState] = None
    stream_sid: Optional[str] = None
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


async def _handle_turn(
    websocket: WebSocket,
    stream_sid: str,
    session: CallSessionState,
    tts: StreamingTTS,
    user_text: str,
) -> None:
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
            await websocket.send_text(
                json.dumps(
                    {
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {"payload": base64.b64encode(audio_chunk).decode()},
                    }
                )
            )
    finally:
        session.speaking = False