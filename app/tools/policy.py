"""
Policy + validation layer: authentication/authorization gates, business
rules, and the allow-list of tools the agent may invoke in a given call
state. Every tool call from the agent should be checked here before it
touches the data layer.
"""
from dataclasses import dataclass, field

from app.agent.state import AgentState

# Tools that never require identity verification (read-only, non-PHI)
PUBLIC_TOOLS = {
    "get_departments",
    "get_doctors",
    "get_doctor_details",
    "get_available_slots",
    "hospital_information",
    "find_patient",
    "create_patient",
    "human_handoff",
}

# Tools that touch PHI or mutate appointment data and require a verified caller
PROTECTED_TOOLS = {
    "book_appointment",
    "cancel_appointment",
    "reschedule_appointment",
}


class PolicyError(Exception):
    """Raised when a tool call is blocked by policy."""


@dataclass
class ToolCallContext:
    state: AgentState
    tool_name: str
    tool_args: dict = field(default_factory=dict)


def authorize_tool_call(ctx: ToolCallContext) -> None:
    """
    Raises PolicyError if the call should be blocked. Call this at the top
    of every tool implementation (or in a LangGraph pre-tool hook).
    """
    if ctx.tool_name in PROTECTED_TOOLS and not ctx.state.get("identity_verified"):
        raise PolicyError(
            "Caller identity must be verified (name + DOB or name + phone on "
            "file) before performing this action."
        )

    if ctx.tool_name not in PUBLIC_TOOLS and ctx.tool_name not in PROTECTED_TOOLS:
        raise PolicyError(f"Tool '{ctx.tool_name}' is not in the allowed tool list.")

    _validate_business_rules(ctx)


def _validate_business_rules(ctx: ToolCallContext) -> None:
    if ctx.tool_name == "book_appointment":
        if not ctx.tool_args.get("slot_id"):
            raise PolicyError("A specific slot_id must be selected before booking.")

    if ctx.tool_name in {"cancel_appointment", "reschedule_appointment"}:
        if not ctx.tool_args.get("appointment_id"):
            raise PolicyError("appointment_id is required.")
