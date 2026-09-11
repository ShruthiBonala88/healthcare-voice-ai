"""Twilio Media Stream handler."""

import asyncio
import audioop
import base64
import json
import tempfile
import time
import wave
from pathlib import Path

from fastapi import WebSocket, WebSocketDisconnect

from app.agent.graph import run_agent_turn
from app.config import get_settings
from app.data.call_repository import add_message
from app.observability.call_events import log_call_event
from app.observability.logging_config import get_logger
from app.voice.stt import get_stt
from app.voice.tts import StreamingTTS
from app.voice.vad import SilenceTracker, VoiceActivityDetector

logger = get_logger("stream_handler")


class CallSessionState:
    def __init__(self, call_sid: str, caller_number: str, conversation_id: str, call_id: str):
        self.call_sid = call_sid
        self.caller_number = caller_number
        self.conversation_id = conversation_id
        self.call_id = call_id
        self.conversation_state: dict = {}
        self.started_at = time.monotonic()
        self.speaking = False
        self.barge_in_event = asyncio.Event()
        self.audio_chunks: list[bytes] = []


def _mulaw_to_wav(audio_data: bytes) -> str:
    path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    with wave.open(path, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8000)
        output.writeframes(audioop.ulaw2lin(audio_data, 2))
    return path


async def _transcribe(audio_data: bytes) -> str:
    if not audio_data:
        return ""
    path = _mulaw_to_wav(audio_data)
    try:
        return (await asyncio.to_thread(get_stt().transcribe, path)).strip()
    finally:
        Path(path).unlink(missing_ok=True)


async def _save_message(session: CallSessionState, role: str, content: str) -> None:
    try:
        await asyncio.to_thread(add_message, session.conversation_id, role, content)
    except Exception:
        logger.exception("message_persistence_failed", call_sid=session.call_sid)


async def handle_media_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    settings = get_settings()
    vad = VoiceActivityDetector()
    silence = SilenceTracker()
    tts = StreamingTTS()
    session = None
    stream_sid = None
    try:
        while True:
            message = json.loads(await websocket.receive_text())
            event = message.get("event")
            if event == "start":
                data = message["start"]
                params = data.get("customParameters", {})
                session = CallSessionState(data["callSid"], params.get("from", "unknown"), params["conversation_id"], params["call_id"])
                stream_sid = data["streamSid"]
                await log_call_event(session.call_id, "call_started", {"call_sid": session.call_sid})
            elif event == "media" and session:
                if time.monotonic() - session.started_at > settings.max_call_duration_seconds:
                    await log_call_event(session.call_id, "call_timeout")
                    break
                chunk = base64.b64decode(message["media"]["payload"])
                speaking = vad.is_speech(chunk)
                if speaking:
                    session.audio_chunks.append(chunk)
                    silence.update(True)
                    if session.speaking:
                        session.barge_in_event.set()
                        await websocket.send_text(json.dumps({"event": "clear", "streamSid": stream_sid}))
                else:
                    if session.audio_chunks:
                        session.audio_chunks.append(chunk)
                    silence.update(False)
                if silence.end_of_turn and session.audio_chunks:
                    audio = b"".join(session.audio_chunks)
                    session.audio_chunks.clear()
                    silence.reset()
                    text = await _transcribe(audio)
                    if text:
                        await _handle_turn(websocket, stream_sid, session, tts, text)
            elif event == "stop":
                if session:
                    await log_call_event(session.call_id, "call_ended")
                break
    except WebSocketDisconnect:
        if session:
            await log_call_event(session.call_id, "call_disconnected")


async def _handle_turn(websocket: WebSocket, stream_sid: str, session: CallSessionState, tts: StreamingTTS, user_text: str) -> None:
    await _save_message(session, "user", user_text)
    result = await run_agent_turn(session.call_sid, session.caller_number, user_text, session.conversation_state)
    session.conversation_state = result["state"]
    reply = result["reply"]
    await _save_message(session, "assistant", reply)
    await log_call_event(session.call_id, "assistant_turn", {"text": reply})
    session.speaking = True
    session.barge_in_event.clear()
    try:
        async for audio in tts.synthesize(reply):
            if session.barge_in_event.is_set():
                break
            await websocket.send_text(json.dumps({"event": "media", "streamSid": stream_sid, "media": {"payload": base64.b64encode(audio).decode("ascii")}}))
    finally:
        session.speaking = False
