import pytest

from app.agent.state import AgentState
from app.tools.policy import (
    PolicyError,
    ToolCallContext,
    authorize_tool_call,
)


# ============================================================
# HELPERS
# ============================================================


def verified_state(
    patient_id: str = "test-patient-id",
) -> AgentState:
    """
    Create a verified patient state for tests.
    """

    return {
        "messages": [],
        "identity_verified": True,
        "patient_id": patient_id,
    }


def unverified_state() -> AgentState:
    """
    Create an unverified caller state for tests.
    """

    return {
        "messages": [],
        "identity_verified": False,
        "patient_id": None,
    }


# ============================================================
# UNKNOWN TOOL
# ============================================================


def test_unknown_tool_is_blocked():
    state = unverified_state()

    context = ToolCallContext(
        state=state,
        tool_name="delete_hospital_database",
        tool_args={},
    )

    with pytest.raises(PolicyError):
        authorize_tool_call(context)


# ============================================================
# BOOKING SECURITY
# ============================================================


def test_booking_requires_identity_verification():
    state = unverified_state()

    context = ToolCallContext(
        state=state,
        tool_name="book_appointment",
        tool_args={
            "patient_id": "test-patient-id",
            "slot_id": "test-slot-id",
        },
    )

    with pytest.raises(PolicyError):
        authorize_tool_call(context)


def test_booking_requires_verified_patient_id():
    state: AgentState = {
        "messages": [],
        "identity_verified": True,
        "patient_id": None,
    }

    context = ToolCallContext(
        state=state,
        tool_name="book_appointment",
        tool_args={
            "patient_id": "test-patient-id",
            "slot_id": "test-slot-id",
        },
    )

    with pytest.raises(PolicyError):
        authorize_tool_call(context)


def test_booking_requires_patient_id():
    state = verified_state()

    context = ToolCallContext(
        state=state,
        tool_name="book_appointment",
        tool_args={
            "slot_id": "test-slot-id",
        },
    )

    with pytest.raises(PolicyError):
        authorize_tool_call(context)


def test_booking_requires_slot_id():
    state = verified_state()

    context = ToolCallContext(
        state=state,
        tool_name="book_appointment",
        tool_args={
            "patient_id": "test-patient-id",
        },
    )

    with pytest.raises(PolicyError):
        authorize_tool_call(context)


def test_verified_booking_is_allowed():
    state = verified_state()

    context = ToolCallContext(
        state=state,
        tool_name="book_appointment",
        tool_args={
            "patient_id": "test-patient-id",
            "slot_id": "test-slot-id",
        },
    )

    authorize_tool_call(context)


def test_booking_blocks_different_patient_id():
    state = verified_state(
        patient_id="patient-a",
    )

    context = ToolCallContext(
        state=state,
        tool_name="book_appointment",
        tool_args={
            "patient_id": "patient-b",
            "slot_id": "test-slot-id",
        },
    )

    with pytest.raises(PolicyError):
        authorize_tool_call(context)


# ============================================================
# CANCEL APPOINTMENT SECURITY
# ============================================================


def test_cancel_requires_identity():
    state = unverified_state()

    context = ToolCallContext(
        state=state,
        tool_name="cancel_appointment",
        tool_args={
            "appointment_id": "test-appointment-id",
            "patient_id": "test-patient-id",
        },
    )

    with pytest.raises(PolicyError):
        authorize_tool_call(context)


def test_cancel_requires_verified_patient_id():
    state: AgentState = {
        "messages": [],
        "identity_verified": True,
        "patient_id": None,
    }

    context = ToolCallContext(
        state=state,
        tool_name="cancel_appointment",
        tool_args={
            "appointment_id": "test-appointment-id",
            "patient_id": "test-patient-id",
        },
    )

    with pytest.raises(PolicyError):
        authorize_tool_call(context)


def test_cancel_requires_appointment_id():
    state = verified_state()

    context = ToolCallContext(
        state=state,
        tool_name="cancel_appointment",
        tool_args={
            "patient_id": "test-patient-id",
        },
    )

    with pytest.raises(PolicyError):
        authorize_tool_call(context)


def test_cancel_requires_patient_id():
    state = verified_state()

    context = ToolCallContext(
        state=state,
        tool_name="cancel_appointment",
        tool_args={
            "appointment_id": "test-appointment-id",
        },
    )

    with pytest.raises(PolicyError):
        authorize_tool_call(context)


def test_verified_cancel_is_allowed():
    state = verified_state()

    context = ToolCallContext(
        state=state,
        tool_name="cancel_appointment",
        tool_args={
            "appointment_id": "test-appointment-id",
            "patient_id": "test-patient-id",
        },
    )

    authorize_tool_call(context)


def test_cancel_blocks_different_patient_id():
    state = verified_state(
        patient_id="patient-a",
    )

    context = ToolCallContext(
        state=state,
        tool_name="cancel_appointment",
        tool_args={
            "appointment_id": "test-appointment-id",
            "patient_id": "patient-b",
        },
    )

    with pytest.raises(PolicyError):
        authorize_tool_call(context)


# ============================================================
# RESCHEDULE APPOINTMENT SECURITY
# ============================================================


def test_reschedule_requires_identity():
    state = unverified_state()

    context = ToolCallContext(
        state=state,
        tool_name="reschedule_appointment",
        tool_args={
            "appointment_id": "test-appointment-id",
            "new_slot_id": "new-slot-id",
            "patient_id": "test-patient-id",
        },
    )

    with pytest.raises(PolicyError):
        authorize_tool_call(context)


def test_reschedule_requires_verified_patient_id():
    state: AgentState = {
        "messages": [],
        "identity_verified": True,
        "patient_id": None,
    }

    context = ToolCallContext(
        state=state,
        tool_name="reschedule_appointment",
        tool_args={
            "appointment_id": "test-appointment-id",
            "new_slot_id": "new-slot-id",
            "patient_id": "test-patient-id",
        },
    )

    with pytest.raises(PolicyError):
        authorize_tool_call(context)


def test_reschedule_requires_appointment_id():
    state = verified_state()

    context = ToolCallContext(
        state=state,
        tool_name="reschedule_appointment",
        tool_args={
            "new_slot_id": "new-slot-id",
            "patient_id": "test-patient-id",
        },
    )

    with pytest.raises(PolicyError):
        authorize_tool_call(context)


def test_reschedule_requires_new_slot_id():
    state = verified_state()

    context = ToolCallContext(
        state=state,
        tool_name="reschedule_appointment",
        tool_args={
            "appointment_id": "test-appointment-id",
            "patient_id": "test-patient-id",
        },
    )

    with pytest.raises(PolicyError):
        authorize_tool_call(context)


def test_reschedule_requires_patient_id():
    state = verified_state()

    context = ToolCallContext(
        state=state,
        tool_name="reschedule_appointment",
        tool_args={
            "appointment_id": "test-appointment-id",
            "new_slot_id": "new-slot-id",
        },
    )

    with pytest.raises(PolicyError):
        authorize_tool_call(context)


def test_verified_reschedule_is_allowed():
    state = verified_state()

    context = ToolCallContext(
        state=state,
        tool_name="reschedule_appointment",
        tool_args={
            "appointment_id": "test-appointment-id",
            "new_slot_id": "new-slot-id",
            "patient_id": "test-patient-id",
        },
    )

    authorize_tool_call(context)


def test_reschedule_blocks_different_patient_id():
    state = verified_state(
        patient_id="patient-a",
    )

    context = ToolCallContext(
        state=state,
        tool_name="reschedule_appointment",
        tool_args={
            "appointment_id": "test-appointment-id",
            "new_slot_id": "new-slot-id",
            "patient_id": "patient-b",
        },
    )

    with pytest.raises(PolicyError):
        authorize_tool_call(context)


# ============================================================
# FIND PATIENT SECURITY
# ============================================================


def test_find_patient_requires_identity_verification():
    state = unverified_state()

    context = ToolCallContext(
        state=state,
        tool_name="find_patient",
        tool_args={
            "patient_id": "test-patient-id",
        },
    )

    with pytest.raises(PolicyError):
        authorize_tool_call(context)


def test_find_patient_requires_verified_patient_id():
    state: AgentState = {
        "messages": [],
        "identity_verified": True,
        "patient_id": None,
    }

    context = ToolCallContext(
        state=state,
        tool_name="find_patient",
        tool_args={
            "patient_id": "test-patient-id",
        },
    )

    with pytest.raises(PolicyError):
        authorize_tool_call(context)


def test_find_patient_requires_patient_id_argument():
    state = verified_state()

    context = ToolCallContext(
        state=state,
        tool_name="find_patient",
        tool_args={},
    )

    with pytest.raises(PolicyError):
        authorize_tool_call(context)


def test_find_patient_blocks_different_patient_id():
    state = verified_state(
        patient_id="patient-a",
    )

    context = ToolCallContext(
        state=state,
        tool_name="find_patient",
        tool_args={
            "patient_id": "patient-b",
        },
    )

    with pytest.raises(PolicyError):
        authorize_tool_call(context)


def test_verified_find_patient_is_allowed():
    state = verified_state()

    context = ToolCallContext(
        state=state,
        tool_name="find_patient",
        tool_args={
            "patient_id": "test-patient-id",
        },
    )

    authorize_tool_call(context)


# ============================================================
# PUBLIC TOOLS
# ============================================================


def test_public_tool_does_not_require_identity():
    state = unverified_state()

    context = ToolCallContext(
        state=state,
        tool_name="get_departments",
        tool_args={},
    )

    authorize_tool_call(context)


def test_hospital_information_does_not_require_identity():
    state = unverified_state()

    context = ToolCallContext(
        state=state,
        tool_name="hospital_information",
        tool_args={},
    )

    authorize_tool_call(context)


def test_human_handoff_does_not_require_identity():
    state = unverified_state()

    context = ToolCallContext(
        state=state,
        tool_name="human_handoff",
        tool_args={},
    )

    authorize_tool_call(context)
