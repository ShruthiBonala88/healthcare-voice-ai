"""
Twilio entrypoints:
<<<<<<< HEAD
  POST /calls/incoming       -> TwiML that opens a Media Stream to our WS endpoint
  WS   /calls/stream          -> the live audio stream, handled by voice/stream_handler.py
  POST /calls/handoff-status  -> Twilio <Dial> action callback, hit after a
                                  human-handoff transfer completes

Twilio request signatures are validated on all inbound webhooks when
settings.twilio_validate_signature is true (see _validate_twilio_signature).
"""
from fastapi import APIRouter, HTTPException, Request, WebSocket
=======
  POST /calls/incoming    -> TwiML that opens a Media Stream to our WS endpoint
  WS   /calls/stream      -> the live audio stream, handled by voice/stream_handler.py

The inbound call is also registered in the database so that
conversations and calls can be tracked in Supabase.
"""

from fastapi import APIRouter, Request, WebSocket
>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0
from fastapi.responses import Response
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import Connect, VoiceResponse

from app.config import get_settings
<<<<<<< HEAD
from app.observability.call_events import log_call_event
from app.observability.logging_config import get_logger
from app.voice.stream_handler import handle_media_stream

=======
from app.data.call_repository import create_call, create_conversation
from app.observability.logging_config import get_logger
from app.voice.stream_handler import handle_media_stream


>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0
router = APIRouter()
logger = get_logger("routes_calls")


<<<<<<< HEAD
def _public_url(request: Request) -> str:
    """
    Reconstructs the exact public URL Twilio called, using the
    X-Forwarded-Proto / X-Forwarded-Host headers set by ngrok (or any
    reverse proxy) instead of trusting request.url directly.

    This is more reliable than uvicorn's --proxy-headers flag, which
    depends on the immediate connecting peer being in
    --forwarded-allow-ips and can silently fail to apply inside Docker's
    bridge network. Reconstructing manually here works regardless of
    that flag's behavior.
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

    Twilio signs each request using the *public* URL it called (the https
    ngrok/prod URL) plus the POST form body. We reconstruct that exact
    URL via _public_url() rather than trusting request.url, since the
    latter reflects http:// internally unless the proxy-header chain is
    perfectly configured end-to-end.
    """
    settings = get_settings()
    if not settings.twilio_validate_signature:
        return True

    validator = RequestValidator(settings.twilio_auth_token)
    signature = request.headers.get("X-Twilio-Signature", "")
    url = _public_url(request)
    form = dict(await request.form())  # actual POST body, not query params

    is_valid = validator.validate(url, form, signature)

    # TEMPORARY DEBUG — remove once signature validation is confirmed working
    # against real Twilio calls (not just curl/health checks).
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
=======
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
>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0


@router.post("/calls/incoming")
async def incoming_call(request: Request):
    """
<<<<<<< HEAD
    Twilio webhook: called when a patient dials the hospital number.
    Returns TwiML that connects the call audio to our WebSocket stream.
    """
    if not await _validate_twilio_signature(request):
        logger.warning("invalid_twilio_signature", path="/calls/incoming")
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    settings = get_settings()
    form = await request.form()

    response = VoiceResponse()
    connect = Connect()
    stream = connect.stream(url=f"wss://{_ws_host(settings.base_url)}/calls/stream")
    stream.parameter(name="from", value=str(form.get("From", "unknown")))
    response.append(connect)

    logger.info("incoming_call", call_sid=form.get("CallSid"), from_=form.get("From"))
    return Response(content=str(response), media_type="text/xml")


@router.post("/calls/handoff-status")
async def handoff_status(request: Request):
    """
    Twilio <Dial> action callback, hit after a human-handoff transfer
    finishes (staff answered / no answer / busy / failed). By the time
    Twilio calls this, the transfer has already happened; we just log
    the outcome and end the call gracefully if nobody picked up.
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
    return Response(content=str(response), media_type="text/xml")
=======
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
>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0


@router.websocket("/calls/stream")
async def call_stream(websocket: WebSocket):
<<<<<<< HEAD
=======
    """
    WebSocket endpoint for the live Twilio Media Stream.
    """

>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0
    await handle_media_stream(websocket)


def _ws_host(base_url: str) -> str:
<<<<<<< HEAD
    return base_url.replace("https://", "").replace("http://", "").rstrip("/")
=======
    return (
        base_url
        .replace("https://", "")
        .replace("http://", "")
        .rstrip("/")
    )
>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0
