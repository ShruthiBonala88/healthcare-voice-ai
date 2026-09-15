"""
Security policy and business-rule validation for Voxevia.

Every agent tool call should pass through this layer before
the tool performs a database operation.

Voxevia is a single-hospital system.
There is no tenant or tenant_id concept.
"""

from dataclasses import dataclass, field
from typing import Any

from app.agent.state import AgentState


# ---------------------------------------------------------
# Public tools
# ---------------------------------------------------------
#
# These tools do not require an already verified patient.
#
# They provide general hospital information or support
# the initial registration flow.
#
# ---------------------------------------------------------

PUBLIC_TOOLS = {
    "get_departments",
    "get_doctors",
    "get_doctor_details",
    "get_available_slots",
    "hospital_information",
    "create_patient",
    "human_handoff",
}


# ---------------------------------------------------------
# Protected tools
# ---------------------------------------------------------
#
# These tools access or modify patient-specific information.
#
# Patient identity must be verified before they can be used.
#
# ---------------------------------------------------------

PROTECTED_TOOLS = {
    "find_patient",
    "book_appointment",
    "cancel_appointment",
    "reschedule_appointment",
}


class PolicyError(Exception):
    """Raised when a tool call violates the security policy."""


@dataclass
class ToolCallContext:
    """
    Context used when authorizing an agent tool call.
    """

    state: AgentState
    tool_name: str
    tool_args: dict[str, Any] = field(default_factory=dict)


def authorize_tool_call(ctx: ToolCallContext) -> None:
    """
    Authorize an agent tool call.

    Security checks:

    1. Tool must exist in the allow-list.
    2. Protected operations require verified identity.
    3. Protected operations require patient_id.
    4. Required business arguments must be present.

    Raises:
        PolicyError:
            If the tool call is not allowed.
    """

    # -----------------------------------------------------
    # 1. Tool allow-list
    # -----------------------------------------------------

    if (
        ctx.tool_name not in PUBLIC_TOOLS
        and ctx.tool_name not in PROTECTED_TOOLS
    ):
        raise PolicyError(
            f"Tool '{ctx.tool_name}' is not in the allowed tool list."
        )

    # -----------------------------------------------------
    # 2. Identity verification
    # -----------------------------------------------------

    if ctx.tool_name in PROTECTED_TOOLS:

        if not ctx.state.get("identity_verified", False):
            raise PolicyError(
                "Caller identity must be verified before this "
                "operation can be performed."
            )

        # A protected operation must also have a patient ID.
        if not ctx.state.get("patient_id"):
            raise PolicyError(
                "Verified patient information is required "
                "before this operation can be performed."
            )

    # -----------------------------------------------------
    # 3. Business-rule validation
    # -----------------------------------------------------

    _validate_business_rules(ctx)


def _validate_business_rules(ctx: ToolCallContext) -> None:
    """
    Validate required arguments for individual tools.
    """

    # -----------------------------------------------------
    # Book appointment
    # -----------------------------------------------------

    if ctx.tool_name == "book_appointment":

        slot_id = ctx.tool_args.get("slot_id")

        if not slot_id:
            raise PolicyError(
                "A specific slot_id must be selected before booking."
            )

    # -----------------------------------------------------
    # Cancel appointment
    # -----------------------------------------------------

    if ctx.tool_name == "cancel_appointment":

        appointment_id = ctx.tool_args.get("appointment_id")

        if not appointment_id:
            raise PolicyError(
                "appointment_id is required."
            )

    # -----------------------------------------------------
    # Reschedule appointment
    # -----------------------------------------------------

    if ctx.tool_name == "reschedule_appointment":

        appointment_id = ctx.tool_args.get("appointment_id")

        if not appointment_id:
            raise PolicyError(
                "appointment_id is required."
            )