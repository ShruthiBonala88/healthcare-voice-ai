"""
Safety-critical escape hatch: transfers the caller to a human. Triggered
for medical emergencies, explicit requests for a human, repeated failed
attempts, or self-harm indicators. See app/agent/prompts.py for the
system-prompt rules governing when the agent should call this.
"""
from langchain_core.tools import tool

from app.observability.call_events import log_call_event


@tool
async def human_handoff(call_sid: str, reason: str) -> dict:
    """
    Signal that this call must be transferred to a human staff member.
    The actual Twilio <Dial> transfer is executed by the call-routing
    layer (app/api/routes_calls.py) once this flag is observed in the
    agent's returned state.
    """
    await log_call_event(call_sid, "human_handoff_requested", {"reason": reason})
    return {"handoff_requested": True, "reason": reason}
