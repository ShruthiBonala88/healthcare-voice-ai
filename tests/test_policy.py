import pytest

from app.agent.state import AgentState
from app.tools.policy import (
    PolicyError,
    ToolCallContext,
    authorize_tool_call,
)


def test_unknown_tool_is_blocked():
    state: AgentState = {
        "messages": [],
        "identity_verified": False,
        "patient_id": None,
    }

    context = ToolCallContext(
        state=state,
        tool_name="delete_hospital_database",
        tool_args={},
    )

    with pytest.raises(PolicyError):
        authorize_tool_call(context)


def test_booking_requires_identity_verification():
    state: AgentState = {
        "messages": [],
        "identity_verified": False,
        "patient_id": None,
    }

    context = ToolCallContext(
        state=state,
        tool_name="book_appointment",
        tool_args={
            "slot_id": "test-slot-id",
        },
    )

    with pytest.raises(PolicyError):
        authorize_tool_call(context)


def test_booking_requires_patient_id():
    state: AgentState = {
        "messages": [],
        "identity_verified": True,
        "patient_id": None,
    }

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
    state: AgentState = {
        "messages": [],
        "identity_verified": True,
        "patient_id": "test-patient-id",
    }

    context = ToolCallContext(
        state=state,
        tool_name="book_appointment",
        tool_args={},
    )

    with pytest.raises(PolicyError):
        authorize_tool_call(context)


def test_verified_booking_is_allowed():
    state: AgentState = {
        "messages": [],
        "identity_verified": True,
        "patient_id": "test-patient-id",
    }

    context = ToolCallContext(
        state=state,
        tool_name="book_appointment",
        tool_args={
            "slot_id": "test-slot-id",
        },
    )

    authorize_tool_call(context)


def test_cancel_requires_identity():
    state: AgentState = {
        "messages": [],
        "identity_verified": False,
        "patient_id": None,
    }

    context = ToolCallContext(
        state=state,
        tool_name="cancel_appointment",
        tool_args={
            "appointment_id": "test-appointment-id",
        },
    )

    with pytest.raises(PolicyError):
        authorize_tool_call(context)


def test_reschedule_requires_identity():
    state: AgentState = {
        "messages": [],
        "identity_verified": False,
        "patient_id": None,
    }

    context = ToolCallContext(
        state=state,
        tool_name="reschedule_appointment",
        tool_args={
            "appointment_id": "test-appointment-id",
        },
    )

    with pytest.raises(PolicyError):
        authorize_tool_call(context)


def test_find_patient_requires_identity_verification():
    state: AgentState = {
        "messages": [],
        "identity_verified": False,
        "patient_id": None,
    }

    context = ToolCallContext(
        state=state,
        tool_name="find_patient",
        tool_args={
            "phone_number": "+919876543210",
        },
    )

    with pytest.raises(PolicyError):
        authorize_tool_call(context)
