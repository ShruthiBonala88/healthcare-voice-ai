from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


# =========================================================
# 1. ROOT ENDPOINT INTEGRATION TEST
# =========================================================

def test_root_endpoint_integration():
    response = client.get("/")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"
    assert data["service"] == "Voxevia Hospital Voice AI Platform"
    assert data["version"] == "0.1.0"
    assert data["mode"] == "inbound"


# =========================================================
# 2. IDENTITY VERIFICATION + SESSION INTEGRATION TEST
# =========================================================

def test_identity_verification_and_session_integration():
    patient_id = "608afa3d-3f09-42ca-b6ec-207b208a0f88"

    identity_result = {
        "verified": True,
        "patient_id": patient_id,
        "patient_number": "P0001",
    }

    fake_session = {
        "session_id": "integration-test-session",
        "call_id": "call-test-001",
        "conversation_id": "conversation-test-001",
        "provider_call_id": "twilio-test-001",
        "patient_id": None,
        "identity_verified": False,
        "current_intent": None,
        "selected_doctor_id": None,
        "selected_slot_id": None,
    }

    updated_session = {
        **fake_session,
        "patient_id": patient_id,
        "identity_verified": True,
    }

    with patch(
        "app.security.identity.verify_patient_identity",
        return_value=identity_result,
    ) as mock_verify:

        with patch(
            "app.utils.session.create_session",
            return_value=fake_session,
        ) as mock_create_session:

            with patch(
                "app.utils.session.verify_call_session_identity",
                return_value=updated_session,
            ) as mock_verify_session:

                # Verify patient identity
                result = mock_verify(
                    caller_phone="+919876543210",
                    patient_number="P0001",
                    date_of_birth="1995-05-15",
                )

                assert result["verified"] is True
                assert result["patient_id"] == patient_id
                assert result["patient_number"] == "P0001"

                # Create call session
                session = mock_create_session(
                    session_id="integration-test-session",
                    call_id="call-test-001",
                    conversation_id="conversation-test-001",
                    provider_call_id="twilio-test-001",
                )

                assert session["session_id"] == "integration-test-session"
                assert session["patient_id"] is None
                assert session["identity_verified"] is False

                # Verify identity inside session
                verified_session = mock_verify_session(
                    session_id="integration-test-session",
                    patient_id=patient_id,
                )

                assert verified_session["patient_id"] == patient_id
                assert verified_session["identity_verified"] is True

                # Confirm functions were called correctly
                mock_verify.assert_called_once_with(
                    caller_phone="+919876543210",
                    patient_number="P0001",
                    date_of_birth="1995-05-15",
                )

                mock_create_session.assert_called_once_with(
                    session_id="integration-test-session",
                    call_id="call-test-001",
                    conversation_id="conversation-test-001",
                    provider_call_id="twilio-test-001",
                )

                mock_verify_session.assert_called_once_with(
                    session_id="integration-test-session",
                    patient_id=patient_id,
                )


# =========================================================
# 3. APPOINTMENT BOOKING INTEGRATION TEST
# =========================================================

def test_appointment_booking_integration():
    patient_id = "608afa3d-3f09-42ca-b6ec-207b208a0f88"

    slot_id = "11111111-1111-1111-1111-111111111111"

    department_id = "d39190a6-6123-43d5-9245-52222320f635"

    doctor_id = "321f82b5-6ee6-4550-a628-8b6fd57d856c"

    appointment_id = "22222222-2222-2222-2222-222222222222"

    fake_appointment = {
        "id": appointment_id,
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "department_id": department_id,
        "slot_id": slot_id,
        "appointment_date": "2026-09-15",
        "start_time": "10:00:00",
        "end_time": "10:30:00",
        "reason": "General consultation",
        "status": "scheduled",
        "notes": None,
    }

    # -----------------------------------------------------
    # Mock Supabase
    # -----------------------------------------------------

    mock_supabase = MagicMock()

    mock_rpc_response = MagicMock()

    mock_rpc_response.data = [
        fake_appointment
    ]

    mock_supabase.rpc.return_value.execute.return_value = (
        mock_rpc_response
    )

    # -----------------------------------------------------
    # Mock Redis
    # -----------------------------------------------------

    mock_redis = MagicMock()

    mock_redis.set.return_value = True
    mock_redis.delete.return_value = 1

    # -----------------------------------------------------
    # Run actual appointment tool
    # -----------------------------------------------------

    with patch(
        "app.tools.appointment_tools.get_supabase",
        return_value=mock_supabase,
    ):

        with patch(
            "app.tools.appointment_tools.get_redis",
            return_value=mock_redis,
        ):

            from app.tools.appointment_tools import book_appointment

            result = book_appointment.invoke(
                {
                    "patient_id": patient_id,
                    "slot_id": slot_id,
                    "department_id": department_id,
                    "reason": "General consultation",
                    "notes": None,
                }
            )

    # -----------------------------------------------------
    # Verify booking result
    # -----------------------------------------------------

    assert result["success"] is True

    assert "appointment" in result

    appointment = result["appointment"]

    assert appointment["id"] == appointment_id

    assert appointment["patient_id"] == patient_id

    assert appointment["doctor_id"] == doctor_id

    assert appointment["department_id"] == department_id

    assert appointment["slot_id"] == slot_id

    assert appointment["status"] == "scheduled"

    # -----------------------------------------------------
    # Verify PostgreSQL RPC was called
    # -----------------------------------------------------

    mock_supabase.rpc.assert_called_once()

    rpc_call = mock_supabase.rpc.call_args

    assert rpc_call.args[0] == "book_appointment_atomic"

    rpc_arguments = rpc_call.args[1]

    assert rpc_arguments["p_patient_id"] == patient_id

    assert rpc_arguments["p_slot_id"] == slot_id

    assert rpc_arguments["p_department_id"] == department_id

    assert rpc_arguments["p_reason"] == "General consultation"

    assert rpc_arguments["p_notes"] is None

    # -----------------------------------------------------
    # Verify Redis lock
    # -----------------------------------------------------

    mock_redis.set.assert_called_once()

    mock_redis.delete.assert_called_once()