"""
<<<<<<< HEAD
<<<<<<< Updated upstream
Twilio entrypoints:
  POST /calls/incoming    -> TwiML that opens a Media Stream to our WS endpoint
  WS   /calls/stream      -> the live audio stream, handled by voice/stream_handler.py

The inbound call is also registered in the database so that
conversations and calls can be tracked in Supabase.
"""

from fastapi import APIRouter, Request, WebSocket
=======
Twilio entrypoints.

POST /calls/incoming
    Receives an inbound Twilio call and returns TwiML that opens
    a Media Stream to our WebSocket endpoint.

WS /calls/stream
    Handles the live Twilio Media Stream.

POST /calls/handoff-status
    Receives the Twilio <Dial> action callback after a human handoff.

Inbound Twilio signatures can be validated when
settings.twilio_validate_signature is enabled.
"""

from fastapi import APIRouter, HTTPException, Request, WebSocket
>>>>>>> Stashed changes
=======
Twilio entrypoints for Voxevia.

Endpoints:

    POST /calls/incoming
        Twilio inbound call webhook.

    WS /calls/stream
        Live Twilio Media Stream.

    POST /calls/handoff-status
        Twilio human-handoff callback.

When enabled, Twilio webhook signatures are validated before
processing inbound HTTP webhooks.
"""

from fastapi import APIRouter, HTTPException, Request, WebSocket
>>>>>>> 6928a2c (Complete backend security validation and tests)
from fastapi.responses import Response
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import Connect, VoiceResponse

from app.config import get_settings
from app.data.call_repository import create_call, create_conversation
<<<<<<< HEAD
<<<<<<< Updated upstream
from app.observability.logging_config import get_logger
from app.voice.stream_handler import handle_media_stream


=======
=======
>>>>>>> 6928a2c (Complete backend security validation and tests)
from app.observability.call_events import log_call_event
from app.observability.logging_config import get_logger
from app.voice.stream_handler import handle_media_stream


<<<<<<< HEAD
>>>>>>> Stashed changes
=======
>>>>>>> 6928a2c (Complete backend security validation and tests)
router = APIRouter()

logger = get_logger("routes_calls")


<<<<<<< HEAD
<<<<<<< Updated upstream
def _validate_twilio_signature(request: Request, body: bytes) -> bool:
=======
def _public_url(request: Request) -> str:
    """
    Reconstruct the public URL that Twilio actually called.

    When running behind ngrok, a reverse proxy, Docker, or another
    proxy, request.url may contain the internal HTTP URL instead of
    the public HTTPS URL.

    Twilio signature validation must use the exact public URL.
=======
def _public_url(request: Request) -> str:
    """
    Reconstruct the public URL Twilio called.

    Behind ngrok or another reverse proxy, request.url may contain
    an internal http scheme. Twilio signs the public URL, so we use
    forwarded headers when available.
>>>>>>> 6928a2c (Complete backend security validation and tests)
    """

    proto = request.headers.get(
        "x-forwarded-proto",
        request.url.scheme,
    )

    host = request.headers.get(
        "x-forwarded-host",
        request.headers.get(
            "host",
            request.url.hostname,
        ),
    )

    url = f"{proto}://{host}{request.url.path}"

    if request.url.query:
        url += f"?{request.url.query}"

    return url


async def _validate_twilio_signature(request: Request) -> bool:
    """
<<<<<<< HEAD
    Validate that an inbound webhook genuinely came from Twilio.

    Twilio signs the public URL plus the submitted form parameters.
    """

>>>>>>> Stashed changes
=======
    Validate an inbound Twilio webhook.

    If TWILIO_VALIDATE_SIGNATURE is false, validation is skipped.
    """

>>>>>>> 6928a2c (Complete backend security validation and tests)
    settings = get_settings()

    # Signature validation can be disabled during local development.
    if not settings.twilio_validate_signature:
        return True

    if not settings.twilio_auth_token:
<<<<<<< HEAD
        logger.warning(
            "twilio_signature_validation_enabled_but_auth_token_missing"
        )
        return False

    validator = RequestValidator(
        settings.twilio_auth_token
    )

    signature = request.headers.get(
        "X-Twilio-Signature",
        "",
    )

    url = _public_url(request)

    # Twilio sends POST form parameters.
=======
        logger.error(
            "twilio_signature_validation_missing_auth_token"
        )
        return False

    signature = request.headers.get(
        "X-Twilio-Signature",
        "",
    )

    if not signature:
        logger.warning(
            "twilio_signature_missing"
        )
        return False

    validator = RequestValidator(
        settings.twilio_auth_token
    )

    url = _public_url(request)

>>>>>>> 6928a2c (Complete backend security validation and tests)
    form = dict(await request.form())

    is_valid = validator.validate(
        url,
        form,
        signature,
    )
<<<<<<< HEAD
<<<<<<< Updated upstream
=======
=======
>>>>>>> 6928a2c (Complete backend security validation and tests)

    if not is_valid:
        logger.warning(
            "invalid_twilio_signature",
<<<<<<< HEAD
            computed_url=url,
            raw_request_url=str(request.url),
            received_signature=signature,
            host_header=request.headers.get("host"),
            forwarded_proto=request.headers.get(
                "x-forwarded-proto"
            ),
            forwarded_host=request.headers.get(
                "x-forwarded-host"
            ),
            form_keys=list(form.keys()),
        )

    return is_valid
>>>>>>> Stashed changes
=======
            url=url,
        )

    return is_valid
>>>>>>> 6928a2c (Complete backend security validation and tests)


@router.post("/calls/incoming")
async def incoming_call(request: Request):
    """
<<<<<<< HEAD
    Twilio webhook called when a patient dials the hospital number.

    Flow:

        Patient
           |
           v
        Twilio
           |
           v
        /calls/incoming
           |
           +--> Create conversation
           |
           +--> Create call record
           |
           +--> Return TwiML
                    |
                    v
              /calls/stream
    """

    # ---------------------------------------------------------
    # 1. Validate Twilio request
    # ---------------------------------------------------------

    if not await _validate_twilio_signature(request):
        logger.warning(
            "invalid_twilio_signature",
            path="/calls/incoming",
        )

=======
    Twilio webhook called when a patient calls the hospital.

    Responsibilities:

    1. Validate the Twilio signature.
    2. Read Twilio call information.
    3. Create a conversation record.
    4. Create a call record.
    5. Return TwiML.
    6. Connect the call to the Media Stream WebSocket.
    """

    if not await _validate_twilio_signature(request):
>>>>>>> 6928a2c (Complete backend security validation and tests)
        raise HTTPException(
            status_code=403,
            detail="Invalid Twilio signature",
        )

    settings = get_settings()

    # ---------------------------------------------------------
    # 2. Read Twilio form data
    # ---------------------------------------------------------

    form = await request.form()

    call_sid = str(
        form.get("CallSid", "")
    )

    from_number = str(
        form.get("From", "unknown")
    )

    to_number = str(
        form.get("To", "unknown")
    )

    # ---------------------------------------------------------
    # 3. Create conversation record
    # ---------------------------------------------------------

    conversation = create_conversation(
        phone_number=from_number,
        channel="voice",
    )

    conversation_id = conversation["id"]

    # ---------------------------------------------------------
    # 4. Create call record
    # ---------------------------------------------------------

    call = create_call(
        conversation_id=conversation_id,
        provider_call_id=call_sid,
        from_number=from_number,
        to_number=to_number,
    )

    call_id = call["id"]

    # ---------------------------------------------------------
    # 5. Create TwiML response
    # ---------------------------------------------------------

    response = VoiceResponse()

    connect = Connect()

    stream = connect.stream(
        url=f"wss://{_ws_host(settings.base_url)}/calls/stream"
    )

<<<<<<< HEAD
    # Patient phone number
=======
    # Pass caller information to the Media Stream.
>>>>>>> 6928a2c (Complete backend security validation and tests)
    stream.parameter(
        name="from",
        value=from_number,
    )

<<<<<<< HEAD
    # Database conversation ID
=======
    # Pass backend database IDs to the stream handler.
>>>>>>> 6928a2c (Complete backend security validation and tests)
    stream.parameter(
        name="conversation_id",
        value=str(conversation_id),
    )

    # Database call ID
    stream.parameter(
        name="call_id",
        value=str(call_id),
    )

    response.append(connect)

    # ---------------------------------------------------------
    # 6. Log incoming call
    # ---------------------------------------------------------

    logger.info(
        "incoming_call",
        call_sid=call_sid,
        from_=from_number,
        to=to_number,
        conversation_id=conversation_id,
        call_id=call_id,
    )

    # ---------------------------------------------------------
    # 7. Return TwiML to Twilio
    # ---------------------------------------------------------

    return Response(
        content=str(response),
        media_type="application/xml",
    )


@router.post("/calls/handoff-status")
async def handoff_status(request: Request):
    """
    Twilio <Dial> action callback.

    This endpoint is called after a human-handoff transfer
    finishes.

    Possible DialCallStatus values include:

        completed
        no-answer
        busy
        failed
        canceled
    """

    # ---------------------------------------------------------
    # 1. Validate Twilio request
    # ---------------------------------------------------------

    if not await _validate_twilio_signature(request):
        raise HTTPException(
            status_code=403,
            detail="Invalid Twilio signature",
        )

    # ---------------------------------------------------------
    # 2. Read callback data
    # ---------------------------------------------------------

    form = await request.form()

    call_sid = form.get("CallSid")
    dial_status = form.get("DialCallStatus")

    # ---------------------------------------------------------
    # 3. Log handoff result
    # ---------------------------------------------------------

    await log_call_event(
        call_sid,
        "handoff_dial_completed",
        {
            "status": dial_status,
        },
    )

    # ---------------------------------------------------------
    # 4. Return TwiML
    # ---------------------------------------------------------

    response = VoiceResponse()

    if dial_status != "completed":
        response.say(
            "We're sorry, no staff member is available right now. "
            "Please call back or try again later."
        )

    response.hangup()

    return Response(
        content=str(response),
        media_type="application/xml",
    )
<<<<<<< HEAD
=======


@router.post("/calls/handoff-status")
async def handoff_status(request: Request):
    """
    Twilio callback after a human-handoff <Dial> finishes.

    Possible DialCallStatus values include:

        completed
        busy
        failed
        no-answer
    """

    if not await _validate_twilio_signature(request):
        raise HTTPException(
            status_code=403,
            detail="Invalid Twilio signature",
        )

    form = await request.form()

    call_sid = str(
        form.get("CallSid", "")
    )

    dial_status = str(
        form.get("DialCallStatus", "")
    )

    logger.info(
        "handoff_dial_completed",
        call_sid=call_sid,
        status=dial_status,
    )

    # Do not allow an invalid event type to break the webhook.
    if call_sid:
        try:
            await log_call_event(
                call_sid,
                "human_handoff_requested",
                {
                    "dial_status": dial_status,
                },
            )
        except Exception as exc:
            logger.warning(
                "handoff_event_logging_failed",
                call_sid=call_sid,
                error=str(exc),
            )

    response = VoiceResponse()

    if dial_status != "completed":
        response.say(
            "We're sorry, no staff member is available right now. "
            "Please call back or try again later."
        )

    response.hangup()

    return Response(
        content=str(response),
        media_type="application/xml",
    )
>>>>>>> 6928a2c (Complete backend security validation and tests)


@router.websocket("/calls/stream")
async def call_stream(websocket: WebSocket):
    """
    WebSocket endpoint for the live Twilio Media Stream.
    """

    await handle_media_stream(websocket)


def _ws_host(base_url: str) -> str:
<<<<<<< HEAD
<<<<<<< Updated upstream
=======
    """
    Convert the configured base URL into a hostname.

    Example:

        https://example.ngrok.app
            ->
        example.ngrok.app
    """

>>>>>>> Stashed changes
=======
    """
    Convert the configured HTTP base URL into a host.
    """

>>>>>>> 6928a2c (Complete backend security validation and tests)
    return (
        base_url
        .replace("https://", "")
        .replace("http://", "")
        .rstrip("/")
    )