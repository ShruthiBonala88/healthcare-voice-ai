"""Twilio webhook and Media Stream endpoints."""

from fastapi import APIRouter, HTTPException, Request, WebSocket
from fastapi.responses import Response
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import Connect, VoiceResponse

from app.config import get_settings
from app.data.call_repository import create_call, create_conversation
from app.observability.call_events import log_call_event
from app.observability.logging_config import get_logger

router = APIRouter()
logger = get_logger("routes_calls")


def _public_url(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get(
        "x-forwarded-host",
        request.headers.get("host", request.url.hostname),
    )
    url = f"{proto}://{host}{request.url.path}"
    if request.url.query:
        url += f"?{request.url.query}"
    return url


async def _validate_twilio_signature(request: Request) -> bool:
    settings = get_settings()
    if not settings.twilio_validate_signature:
        return True
    if not settings.twilio_auth_token:
        logger.error("twilio_auth_token_missing")
        return False

    form = dict(await request.form())
    signature = request.headers.get("X-Twilio-Signature", "")
    is_valid = RequestValidator(settings.twilio_auth_token).validate(
        _public_url(request),
        form,
        signature,
    )
    if not is_valid:
        logger.warning(
            "invalid_twilio_signature",
            url=_public_url(request),
            form_keys=list(form),
        )
    return is_valid


@router.post("/calls/incoming")
async def incoming_call(request: Request):
    if not await _validate_twilio_signature(request):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    settings = get_settings()
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    from_number = str(form.get("From", "unknown"))
    to_number = str(form.get("To", "unknown"))

    conversation = create_conversation(phone_number=from_number, channel="voice")
    call = create_call(
        conversation_id=conversation["id"],
        provider_call_id=call_sid,
        from_number=from_number,
        to_number=to_number,
    )

    response = VoiceResponse()
    connect = Connect()
    stream = connect.stream(url=f"wss://{_ws_host(settings.base_url)}/calls/stream")
    stream.parameter(name="from", value=from_number)
    stream.parameter(name="conversation_id", value=str(conversation["id"]))
    stream.parameter(name="call_id", value=str(call["id"]))
    response.append(connect)

    logger.info("incoming_call", call_sid=call_sid, from_=from_number)
    return Response(content=str(response), media_type="application/xml")


@router.post("/calls/handoff-status")
async def handoff_status(request: Request):
    if not await _validate_twilio_signature(request):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    form = await request.form()
    call_id = str(form.get("CallSid", ""))
    dial_status = form.get("DialCallStatus")
    await log_call_event(call_id, "handoff_dial_completed", {"status": dial_status})

    response = VoiceResponse()
    if dial_status != "completed":
        response.say("We're sorry, no staff member is available right now. Please call back later.")
    response.hangup()
    return Response(content=str(response), media_type="application/xml")


@router.websocket("/calls/stream")
async def call_stream(websocket: WebSocket):
    from app.voice.stream_handler import handle_media_stream

    await handle_media_stream(websocket)


def _ws_host(base_url: str) -> str:
    return base_url.replace("https://", "").replace("http://", "").rstrip("/")
