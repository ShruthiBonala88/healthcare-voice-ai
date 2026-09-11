"""
Twilio entrypoints:
  POST /calls/incoming       -> TwiML that opens a Media Stream to our WS endpoint
  WS   /calls/stream          -> the live audio stream, handled by voice/stream_handler.py
  POST /calls/handoff-status  -> Twilio <Dial> action callback, hit after a human-handoff transfer completes

Twilio request signatures are validated on all inbound webhooks when
settings.twilio_validate_signature is true (see _validate_twilio_signature).

The inbound call is also registered in the database so that conversations and calls can be tracked.
"""
from fastapi import APIRouter, HTTPException, Request, WebSocket
from fastapi.responses import Response
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import Connect, VoiceResponse

from app.config import get_settings
from app.data.call_repository import create_call, create_conversation
from app.observability.call_events import log_call_event
from app.observability.logging_config import get_logger
from app.voice.stream_handler import handle_media_stream

router = APIRouter()
logger = get_logger("routes_calls")


def _public_url(request: Request) -> str:
    """
    Reconstructs the exact public URL Twilio called, using the
    X-Forwarded-Proto / X-Forwarded-Host headers set by ngrok (or any
    reverse proxy) instead of trusting request.url directly.
    """
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.hostname))
    url = f"{proto}://{host}{request.url.path}"
    if request.url.query:
        url += f"?{request.url.query}"
    return url


async def _validate_twilio_signature(request: Request) -> bool:
    """
    Validates that an inbound webhook genuinely came from Twilio.
    """
    settings = get_settings()
    if not settings.twilio_validate_signature:
        return True

    validator = RequestValidator(settings.twilio_auth_token)
    signature = request.headers.get("X-Twilio-Signature", "")
    url = _public_url(request)
    form = dict(await request.form())

    is_valid = validator.validate(url, form, signature)

    if not is_valid:
        logger.warning(
            "twilio_signature_debug",
            computed_url=url,
            raw_request_url=str(request.url),
            received_signature=signature,
            host_header=request.headers.get("host"),
            forwarded_proto=request.headers.get("x-forwarded-proto"),
            forwarded_host=request.headers.get("x-forwarded-host"),
            form_keys=list(form.keys()),
        )

    return is_valid


@router.post("/calls/incoming")
async def incoming_call(request: Request):
    """
    Twilio webhook: called when a patient dials the hospital number.
    Returns TwiML that connects the call audio to our WebSocket stream.
    """
    if not await _validate_twilio_signature(request):
        logger.warning("invalid_twilio_signature", path="/calls/incoming")
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    settings = get_settings()
    form = await request.form()

    call_sid = str(form.get("CallSid", ""))
    from_number = str(form.get("From", "unknown"))
    to_number = str(form.get("To", "unknown"))

    # Create conversation
    conversation = create_conversation(
        phone_number=from_number,
        channel="voice",
    )
    conversation_id = conversation["id"]

    # Create call
    call = create_call(
        conversation_id=conversation_id,
        provider_call_id=call_sid,
        from_number=from_number,
        to_number=to_number,
    )
    call_id = call["id"]

    # Create TwiML response
    response = VoiceResponse()
    connect = Connect()
    stream = connect.stream(url=f"wss://{_ws_host(settings.base_url)}/calls/stream")
    
    stream.parameter(name="from", value=from_number)
    stream.parameter(name="conversation_id", value=str(conversation_id))
    stream.parameter(name="call_id", value=str(call_id))
    
    response.append(connect)

    logger.info(
        "incoming_call",
        call_sid=call_sid,
        from_=from_number,
        to=to_number,
        conversation_id=conversation_id,
        call_id=call_id,
    )

    return Response(content=str(response), media_type="application/xml")


@router.post("/calls/handoff-status")
async def handoff_status(request: Request):
    """
    Twilio <Dial> action callback, hit after a human-handoff transfer
    finishes (staff answered / no answer / busy / failed).
    """
    if not await _validate_twilio_signature(request):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    form = await request.form()
    call_sid = form.get("CallSid")
    dial_status = form.get("DialCallStatus")
    await log_call_event(call_sid, "handoff_dial_completed", {"status": dial_status})

    response = VoiceResponse()
    if dial_status != "completed":
        response.say(
            "We're sorry, no staff member is available right now. "
            "Please call back or try again later."
        )
    response.hangup()
    return Response(content=str(response), media_type="application/xml")


@router.websocket("/calls/stream")
async def call_stream(websocket: WebSocket):
    """
    WebSocket endpoint for the live Twilio Media Stream.
    """
    await handle_media_stream(websocket)


def _ws_host(base_url: str) -> str:
    return base_url.replace("https://", "").replace("http://", "").rstrip("/")
