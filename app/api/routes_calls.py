"""
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

Voxevia is a single-hospital system.
"""

from fastapi import APIRouter, HTTPException, Request, WebSocket
from fastapi.responses import Response
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import Connect, VoiceResponse

from app.config import get_settings
from app.data.call_repository import (
    create_call,
    create_conversation,
)
from app.observability.call_events import log_call_event
from app.observability.logging_config import get_logger
from app.voice.stream_handler import handle_media_stream


router = APIRouter()
logger = get_logger("routes_calls")


# ============================================================
# PUBLIC URL
# ============================================================


def _public_url(request: Request) -> str:
    """
    Reconstruct the public URL that Twilio actually called.

    When running behind ngrok, Docker, or another reverse proxy,
    request.url may contain the internal HTTP URL.

    Twilio signature validation must use the public URL that
    Twilio originally signed.
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


# ============================================================
# TWILIO SIGNATURE VALIDATION
# ============================================================


async def _validate_twilio_signature(
    request: Request,
) -> bool:
    """
    Validate that an inbound HTTP webhook genuinely came from Twilio.

    If TWILIO_VALIDATE_SIGNATURE is disabled, validation is skipped.

    Twilio signs:
        public URL + submitted form parameters
    """
    settings = get_settings()

    # Signature validation can be disabled during local development.
    if not settings.twilio_validate_signature:
        return True

    if not settings.twilio_auth_token:
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

    # Twilio sends POST form parameters.
    form = dict(
        await request.form()
    )

    is_valid = validator.validate(
        url,
        form,
        signature,
    )

    if not is_valid:
        logger.warning(
            "invalid_twilio_signature",
            extra={
                "url": url,
            },
        )

    return is_valid


# ============================================================
# INCOMING CALL
# ============================================================


@router.post("/calls/incoming")
async def incoming_call(
    request: Request,
):
    """
    Twilio webhook called when a patient calls the hospital.

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

    # --------------------------------------------------------
    # 1. Validate Twilio request
    # --------------------------------------------------------

    if not await _validate_twilio_signature(
        request
    ):
        logger.warning(
            "invalid_twilio_signature",
            extra={
                "path": "/calls/incoming",
            },
        )

        raise HTTPException(
            status_code=403,
            detail="Invalid Twilio signature",
        )

    settings = get_settings()

    # --------------------------------------------------------
    # 2. Read Twilio form data
    # --------------------------------------------------------

    form = await request.form()

    call_sid = str(
        form.get(
            "CallSid",
            "",
        )
    )

    from_number = str(
        form.get(
            "From",
            "unknown",
        )
    )

    to_number = str(
        form.get(
            "To",
            "unknown",
        )
    )

    # --------------------------------------------------------
    # 3. Create conversation record
    # --------------------------------------------------------

    conversation = create_conversation(
        phone_number=from_number,
        channel="voice",
    )

    conversation_id = conversation["id"]

    # --------------------------------------------------------
    # 4. Create call record
    # --------------------------------------------------------

    call = create_call(
        conversation_id=conversation_id,
        provider_call_id=call_sid,
        from_number=from_number,
        to_number=to_number,
    )

    call_id = call["id"]

    # --------------------------------------------------------
    # 5. Create TwiML response
    # --------------------------------------------------------

    response = VoiceResponse()

    connect = Connect()

    stream = connect.stream(
        url=f"wss://{_ws_host(settings.base_url)}/calls/stream"
    )

    # Pass caller information to the Media Stream.
    stream.parameter(
        name="from",
        value=from_number,
    )

    # Pass backend database IDs to the stream handler.
    stream.parameter(
        name="conversation_id",
        value=str(conversation_id),
    )

    stream.parameter(
        name="call_id",
        value=str(call_id),
    )

    response.append(connect)

    # --------------------------------------------------------
    # 6. Log incoming call
    # --------------------------------------------------------

    logger.info(
        "incoming_call",
        extra={
            "call_sid": call_sid,
            "conversation_id": conversation_id,
            "call_id": call_id,
        },
    )

    # --------------------------------------------------------
    # 7. Return TwiML to Twilio
    # --------------------------------------------------------

    return Response(
        content=str(response),
        media_type="application/xml",
    )


# ============================================================
# HUMAN HANDOFF STATUS
# ============================================================


@router.post("/calls/handoff-status")
async def handoff_status(
    request: Request,
):
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

    # --------------------------------------------------------
    # 1. Validate Twilio request
    # --------------------------------------------------------

    if not await _validate_twilio_signature(
        request
    ):
        raise HTTPException(
            status_code=403,
            detail="Invalid Twilio signature",
        )

    # --------------------------------------------------------
    # 2. Read callback data
    # --------------------------------------------------------

    form = await request.form()

    call_sid = str(
        form.get(
            "CallSid",
            "",
        )
    )

    dial_status = str(
        form.get(
            "DialCallStatus",
            "",
        )
    )

    # --------------------------------------------------------
    # 3. Log handoff result
    # --------------------------------------------------------

    logger.info(
        "handoff_dial_completed",
        extra={
            "call_sid": call_sid,
            "status": dial_status,
        },
    )

    # Only attempt database event logging when
    # a CallSid was actually provided.
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
                extra={
                    "call_sid": call_sid,
                    "error": str(exc),
                },
            )

    # --------------------------------------------------------
    # 4. Return TwiML
    # --------------------------------------------------------

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


# ============================================================
# MEDIA STREAM WEBSOCKET
# ============================================================


@router.websocket("/calls/stream")
async def call_stream(
    websocket: WebSocket,
):
    """
    WebSocket endpoint for the live Twilio Media Stream.
    """
    await handle_media_stream(
        websocket
    )


# ============================================================
# WEBSOCKET HOST
# ============================================================


def _ws_host(
    base_url: str,
) -> str:
    """
    Convert the configured HTTP/HTTPS base URL into a host.

    Example:

        https://example.ngrok.app
            ->
        example.ngrok.app
    """
    return (
        base_url
        .replace(
            "https://",
            "",
        )
        .replace(
            "http://",
            "",
        )
        .rstrip("/")
    )