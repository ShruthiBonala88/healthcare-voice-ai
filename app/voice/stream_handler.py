"""
Handles a single Twilio Media Stream WebSocket connection end-to-end:

  Twilio audio in -> VAD -> STT -> LangGraph agent -> TTS -> Twilio audio out

Implements barge-in (caller speaking cancels in-flight TTS playback),
end-of-turn silence detection, and an overall call timeout.
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
            msg = json.loads(raw)
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

                # Barge-in: if we're currently speaking (TTS) and the caller
                # starts talking, cancel playback immediately.
                if vad.is_speech(mulaw_chunk):
                    if session.speaking:
                        session.barge_in_event.set()
                    silence.update(True)
                else:
                    silence.update(False)

                stt.send_audio(mulaw_chunk)

                if silence.end_of_turn and pending_transcript_parts:
                    user_text = " ".join(pending_transcript_parts).strip()
                    pending_transcript_parts.clear()
                    silence.reset()
                    await _handle_turn(websocket, stream_sid, session, tts, user_text)

            elif event == "stop":
                if session:
                    await log_call_event(session.call_sid, "call_ended")
                    await stt.finish()
                break

    except WebSocketDisconnect:
        if session:
            await log_call_event(session.call_sid, "call_disconnected")
    finally:
        if session:
            await stt.finish()


async def _handle_turn(
    websocket: WebSocket,
    stream_sid: str,
    session: CallSessionState,
    tts: StreamingTTS,
    user_text: str,
) -> None:
    await log_call_event(session.call_sid, "user_turn", {"text": user_text})

    agent_result = await run_agent_turn(
        call_sid=session.call_sid,
        caller_number=session.caller_number,
        user_text=user_text,
        state=session.conversation_state,
    )
    session.conversation_state = agent_result["state"]
    reply_text = agent_result["reply"]

    await log_call_event(session.call_sid, "assistant_turn", {"text": reply_text})

    session.speaking = True
    session.barge_in_event.clear()
    try:
        async for audio_chunk in tts.synthesize(reply_text):
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

    if agent_result.get("handoff_requested"):
        await log_call_event(session.call_sid, "human_handoff_triggered")
        # The agent/human_handoff tool has already queued the transfer;
        # the call flow (Twilio <Dial>) is coordinated from app/api/routes_calls.py.
