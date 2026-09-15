from unittest.mock import MagicMock, patch

from app.security.identity import verify_patient_identity


def test_verify_patient_identity_success():
    mock_supabase = MagicMock()

    (
        mock_supabase.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .eq.return_value
        .limit.return_value
        .execute.return_value.data
    ) = [
        {
            "id": "608afa3d-3f09-42ca-b6ec-207b208a0f88",
            "patient_number": "P0001",
        }
    ]

    with patch(
        "app.security.identity.get_supabase",
        return_value=mock_supabase,
    ):
        result = verify_patient_identity(
            caller_phone="+919876543210",
            patient_number="P0001",
            date_of_birth="1995-05-15",
        )

    assert result["verified"] is True
    assert result["patient_id"] == (
        "608afa3d-3f09-42ca-b6ec-207b208a0f88"
    )
    assert result["patient_number"] == "P0001"


def test_verify_patient_identity_failure():
    mock_supabase = MagicMock()

    (
        mock_supabase.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .eq.return_value
        .limit.return_value
        .execute.return_value.data
    ) = []

    with patch(
        "app.security.identity.get_supabase",
        return_value=mock_supabase,
    ):
        result = verify_patient_identity(
            caller_phone="+919876543210",
            patient_number="P0001",
            date_of_birth="2000-01-01",
        )

    assert result["verified"] is False
    assert result["patient_id"] is None


def test_verify_patient_identity_requires_phone():
    result = verify_patient_identity(
        caller_phone="",
        patient_number="P0001",
        date_of_birth="1995-05-15",
    )

    assert result["verified"] is False
    assert result["patient_id"] is None


def test_verify_patient_identity_requires_patient_number():
    result = verify_patient_identity(
        caller_phone="+919876543210",
        patient_number="",
        date_of_birth="1995-05-15",
    )

    assert result["verified"] is False
    assert result["patient_id"] is None


def test_verify_patient_identity_requires_date_of_birth():
    result = verify_patient_identity(
        caller_phone="+919876543210",
        patient_number="P0001",
        date_of_birth="",
    )

    assert result["verified"] is False
    assert result["patient_id"] is None