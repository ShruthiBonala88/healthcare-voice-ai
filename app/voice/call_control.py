"""
Live in-call control via Twilio's REST API.

A Media Stream (<Connect><Stream>) only lets us listen/talk over the
WebSocket — to move the caller *out* of the stream and onto a real phone
line (e.g. a human handoff), we have to replace the call's TwiML via
Twilio's REST API. Doing so ends the Media Stream on Twilio's side, so
the stream_handler's WebSocket loop should stop after calling this.
"""
from twilio.rest import Client as TwilioClient
from twilio.twiml.voice_response import Dial, VoiceResponse

from app.config import get_settings
from app.observability.logging_config import get_logger

logger = get_logger("call_control")


def _twilio_client() -> TwilioClient:
    settings = get_settings()
    return TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)


def transfer_call_to_human(call_sid: str) -> None:
    """
    Redirects an in-progress call to a human staff member.

    Note: this calls the Twilio REST API synchronously (the twilio-python
    SDK is not async). Call it via `asyncio.to_thread(...)` from async
    code so it doesn't block the event loop.
    """
    settings = get_settings()
    if not settings.human_handoff_phone_number:
        logger.error("handoff_requested_but_no_number_configured", call_sid=call_sid)
        return

    response = VoiceResponse()
    dial = Dial(
        action=f"{settings.base_url.rstrip('/')}/calls/handoff-status",
        method="POST",
        timeout=20,
    )
    dial.number(settings.human_handoff_phone_number)
    response.append(dial)

    try:
        client = _twilio_client()
        client.calls(call_sid).update(twiml=str(response))
        logger.info("call_transferred_to_human", call_sid=call_sid)
    except Exception:
        logger.exception("call_transfer_failed", call_sid=call_sid)
        