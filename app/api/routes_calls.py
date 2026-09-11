"""
Twilio entrypoints:
  POST /calls/incoming    -> TwiML that opens a Media Stream to our WS endpoint
  WS   /calls/stream      -> the live audio stream, handled by voice/stream_handler.py

The inbound call is also registered in the database so that
conversations and calls can be tracked in Supabase.
"""

from fastapi import APIRouter, Request, WebSocket
from fastapi.responses import Response
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import Connect, VoiceResponse

from app.config import get_settings
from app.data.call_repository import create_call, create_conversation
from app.observability.logging_config import get_logger
from app.voice.stream_handler import handle_media_stream


router = APIRouter()
logger = get_logger("routes_calls")


def _validate_twilio_signature(request: Request, body: bytes) -> bool:
    settings = get_settings()

    if not settings.twilio_validate_signature:
        return True

    if not settings.twilio_auth_token:
        return False

    validator = RequestValidator(settings.twilio_auth_token)

    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)

    form = dict(request.query_params)

    return validator.validate(
        url,
        form,
        signature,
    )


@router.post("/calls/incoming")
async def incoming_call(request: Request):
    """
    Twilio webhook called when a patient dials the hospital number.

    Responsibilities:
    1. Read Twilio call information.
    2. Create a conversation record.
    3. Create a call record.
    4. Return TwiML that connects the call to our WebSocket stream.
    """

    settings = get_settings()

    form = await request.form()

    call_sid = str(form.get("CallSid", ""))
    from_number = str(form.get("From", "unknown"))
    to_number = str(form.get("To", "unknown"))

    # ---------------------------------------------------------
    # Create conversation
    # ---------------------------------------------------------

    conversation = create_conversation(
        phone_number=from_number,
        channel="voice",
    )

    conversation_id = conversation["id"]

    # ---------------------------------------------------------
    # Create call
    # ---------------------------------------------------------

    call = create_call(
        conversation_id=conversation_id,
        provider_call_id=call_sid,
        from_number=from_number,
        to_number=to_number,
    )

    call_id = call["id"]

    # ---------------------------------------------------------
    # Create TwiML response
    # ---------------------------------------------------------

    response = VoiceResponse()

    connect = Connect()

    stream = connect.stream(
        url=f"wss://{_ws_host(settings.base_url)}/calls/stream"
    )

    stream.parameter(
        name="from",
        value=from_number,
    )

    # Pass database IDs to the WebSocket connection.
    # The stream handler can use these later to save
    # messages and call events.
    stream.parameter(
        name="conversation_id",
        value=str(conversation_id),
    )

    stream.parameter(
        name="call_id",
        value=str(call_id),
    )

    response.append(connect)

    logger.info(
        "incoming_call",
        call_sid=call_sid,
        from_=from_number,
        to=to_number,
        conversation_id=conversation_id,
        call_id=call_id,
    )

    return Response(
        content=str(response),
        media_type="application/xml",
    )


@router.websocket("/calls/stream")
async def call_stream(websocket: WebSocket):
    """
    WebSocket endpoint for the live Twilio Media Stream.
    """

    await handle_media_stream(websocket)


def _ws_host(base_url: str) -> str:
    return (
        base_url
        .replace("https://", "")
        .replace("http://", "")
        .rstrip("/")
    )