import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


TEST_TWILIO_AUTH_TOKEN = "test-twilio-auth-token"


def test_incoming_call_rejects_invalid_twilio_signature():
    with patch("app.api.routes_calls.get_settings") as mock_settings:
        mock_settings.return_value.twilio_validate_signature = True
        mock_settings.return_value.twilio_auth_token = TEST_TWILIO_AUTH_TOKEN

        client = TestClient(app)

        response = client.post(
            "/calls/incoming",
            data={
                "CallSid": "CA-security-disabled-002",
                "From": "+919876543210",
                "To": "+911234567890",
            },
            headers={
                "X-Twilio-Signature": "invalid-signature",
            },
        )

        assert response.status_code in {400, 403}


def test_incoming_call_allows_request_when_signature_validation_disabled():
    with patch("app.api.routes_calls.get_settings") as mock_settings:
        mock_settings.return_value.twilio_validate_signature = False
        mock_settings.return_value.twilio_auth_token = TEST_TWILIO_AUTH_TOKEN

        client = TestClient(app)

        unique_call_sid = "CA" + uuid.uuid4().hex

        response = client.post(
            "/calls/incoming",
            data={
                "CallSid": unique_call_sid,
                "From": "+919876543210",
                "To": "+911234567890",
            },
        )

        assert response.status_code != 403