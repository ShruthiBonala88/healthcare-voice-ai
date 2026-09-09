"""
Twilio entrypoints:
  POST /calls/incoming    -> TwiML that opens a Media Stream to our WS endpoint
  WS   /calls/stream       -> the live audio stream, handled by voice/stream_handler.py

In production, validate the Twilio request signature (see
settings.twilio_validate_signature) to ensure requests genuinely come
from Twilio.
"""
from fastapi import APIRouter, Request, WebSocket
from fastapi.responses import Response
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import Connect, VoiceResponse

from app.config import get_settings
from app.observability.logging_config import get_logger
from app.voice.stream_handler import handle_media_stream

router = APIRouter()
logger = get_logger("routes_calls")


def _validate_twilio_signature(request: Request, body: bytes) -> bool:
    settings = get_settings()
    if not settings.twilio_validate_signature:
        return True
    validator = RequestValidator(settings.twilio_auth_token)
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    form = dict(request.query_params)
    return validator.validate(url, form, signature)


@router.post("/calls/incoming")
async def incoming_call(request: Request):
    """
    Twilio webhook: called when a patient dials the hospital number.
    Returns TwiML that connects the call audio to our WebSocket stream.
    """
    settings = get_settings()
    form = await request.form()

    response = VoiceResponse()
    connect = Connect()
    stream = connect.stream(url=f"wss://{_ws_host(settings.base_url)}/calls/stream")
    stream.parameter(name="from", value=str(form.get("From", "unknown")))
    response.append(connect)

    logger.info("incoming_call", call_sid=form.get("CallSid"), from_=form.get("From"))
    return Response(content=str(response), media_type="application/xml")


@router.websocket("/calls/stream")
async def call_stream(websocket: WebSocket):
    await handle_media_stream(websocket)


def _ws_host(base_url: str) -> str:
    return base_url.replace("https://", "").replace("http://", "").rstrip("/")
