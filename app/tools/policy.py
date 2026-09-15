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


# ============================================================
# TOOL ALLOW-LIST
# ============================================================


PUBLIC_TOOLS = {
    "get_departments",
    "get_doctors",
    "get_doctor_details",
    "get_available_slots",
    "hospital_information",
    "create_patient",
    "human_handoff",
}


PROTECTED_TOOLS = {
    "find_patient",
    "book_appointment",
    "cancel_appointment",
    "reschedule_appointment",
}


# ============================================================
# POLICY ERROR
# ============================================================


class PolicyError(Exception):
    """Raised when a tool call violates the security policy."""


# ============================================================
# TOOL CALL CONTEXT
# ============================================================


@dataclass
class ToolCallContext:
    """
    Information required to authorize a tool call.
    """

    state: AgentState
    tool_name: str
    tool_args: dict[str, Any] = field(
        default_factory=dict
    )


# ============================================================
# MAIN AUTHORIZATION
# ============================================================


def authorize_tool_call(
    ctx: ToolCallContext,
) -> None:
    """
    Authorize a tool call before the tool is executed.

    Security checks:

        1. Tool must be explicitly allowed.
        2. Protected tools require verified identity.
        3. Protected tools require a verified patient_id.
        4. Security-sensitive arguments must match trusted state.
        5. Business rules are validated.

    This function does not execute the tool.
    """

    # ========================================================
    # TOOL ALLOW-LIST
    # ========================================================

    if (
        ctx.tool_name not in PUBLIC_TOOLS
        and ctx.tool_name not in PROTECTED_TOOLS
    ):
        raise PolicyError(
            f"Tool '{ctx.tool_name}' is not in the allowed tool list."
        )

    # ========================================================
    # PROTECTED TOOL CHECK
    # ========================================================

    if ctx.tool_name in PROTECTED_TOOLS:

        if not ctx.state.get(
            "identity_verified",
            False,
        ):
            raise PolicyError(
                "Caller identity must be verified before "
                "this operation can be performed."
            )

        verified_patient_id = ctx.state.get(
            "patient_id"
        )

        if not verified_patient_id:
            raise PolicyError(
                "Verified patient information is required "
                "before this operation can be performed."
            )

        # ----------------------------------------------------
        # PATIENT OWNERSHIP CHECK
        # ----------------------------------------------------
        #
        # The patient_id inside tool_args must match the
        # verified patient stored in trusted state.
        #
        # graph.py normally replaces the LLM-generated
        # patient_id before this function is called.
        #
        # This is an additional defense-in-depth check.
        #

        if ctx.tool_name in {
            "find_patient",
            "book_appointment",
            "cancel_appointment",
            "reschedule_appointment",
        }:

            requested_patient_id = ctx.tool_args.get(
                "patient_id"
            )

            if not requested_patient_id:
                raise PolicyError(
                    "patient_id is required for this operation."
                )

            if requested_patient_id != verified_patient_id:
                raise PolicyError(
                    "The requested patient does not match "
                    "the verified caller."
                )

    # ========================================================
    # BUSINESS RULES
    # ========================================================

    _validate_business_rules(ctx)


# ============================================================
# BUSINESS RULE VALIDATION
# ============================================================


def _validate_business_rules(
    ctx: ToolCallContext,
) -> None:
    """
    Validate tool-specific business rules.

    This function is intentionally separate from the main
    authorization logic so security rules and business rules
    remain easy to understand and test.
    """

    # ========================================================
    # BOOK APPOINTMENT
    # ========================================================

    if ctx.tool_name == "book_appointment":

        patient_id = ctx.tool_args.get(
            "patient_id"
        )

        slot_id = ctx.tool_args.get(
            "slot_id"
        )

        verified_patient_id = ctx.state.get(
            "patient_id"
        )

        if not patient_id:
            raise PolicyError(
                "patient_id is required for appointment booking."
            )

        if not slot_id:
            raise PolicyError(
                "A specific slot_id must be selected before booking."
            )

        if patient_id != verified_patient_id:
            raise PolicyError(
                "The requested patient does not match "
                "the verified caller."
            )

    # ========================================================
    # CANCEL APPOINTMENT
    # ========================================================

    if ctx.tool_name == "cancel_appointment":

        appointment_id = ctx.tool_args.get(
            "appointment_id"
        )

        patient_id = ctx.tool_args.get(
            "patient_id"
        )

        verified_patient_id = ctx.state.get(
            "patient_id"
        )

        if not appointment_id:
            raise PolicyError(
                "appointment_id is required."
            )

        if not patient_id:
            raise PolicyError(
                "patient_id is required for appointment cancellation."
            )

        if patient_id != verified_patient_id:
            raise PolicyError(
                "The appointment does not belong "
                "to the verified patient."
            )

    # ========================================================
    # RESCHEDULE APPOINTMENT
    # ========================================================

    if ctx.tool_name == "reschedule_appointment":

        appointment_id = ctx.tool_args.get(
            "appointment_id"
        )

        new_slot_id = ctx.tool_args.get(
            "new_slot_id"
        )

        patient_id = ctx.tool_args.get(
            "patient_id"
        )

        verified_patient_id = ctx.state.get(
            "patient_id"
        )

        if not appointment_id:
            raise PolicyError(
                "appointment_id is required."
            )

        if not new_slot_id:
            raise PolicyError(
                "new_slot_id is required."
            )

        if not patient_id:
            raise PolicyError(
                "patient_id is required for appointment rescheduling."
            )

        if patient_id != verified_patient_id:
            raise PolicyError(
                "The appointment does not belong "
                "to the verified patient."
            )
