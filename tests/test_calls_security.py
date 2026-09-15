"""
Security tests for the incoming Twilio call endpoint.
"""

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


TEST_TWILIO_AUTH_TOKEN = "test-auth-token"


def test_incoming_call_allows_request_when_signature_validation_disabled():
    """Incoming call should be accepted when Twilio signature validation is disabled."""

    unique_call_sid = "CA" + uuid.uuid4().hex

    with patch("app.api.routes_calls.get_settings") as mock_settings:
        mock_settings.return_value.twilio_validate_signature = False
        mock_settings.return_value.twilio_auth_token = TEST_TWILIO_AUTH_TOKEN
        mock_settings.return_value.rate_limit_per_phone_per_hour = 20

        with TestClient(app) as client:
            response = client.post(
                "/calls/incoming",
                data={
                    "CallSid": unique_call_sid,
                    "From": "+919876543210",
                    "To": "+911234567890",
                },
            )

    assert response.status_code == 200


def test_incoming_call_rejects_invalid_signature_when_validation_enabled():
    """Incoming call should be rejected when Twilio signature validation is enabled."""

    unique_call_sid = "CA" + uuid.uuid4().hex

    with patch("app.api.routes_calls.get_settings") as mock_settings:
        mock_settings.return_value.twilio_validate_signature = True
        mock_settings.return_value.twilio_auth_token = TEST_TWILIO_AUTH_TOKEN
        mock_settings.return_value.rate_limit_per_phone_per_hour = 20

        with TestClient(app) as client:
            response = client.post(
                "/calls/incoming",
                data={
                    "CallSid": unique_call_sid,
                    "From": "+919876543210",
                    "To": "+911234567890",
                },
                headers={
                    "X-Twilio-Signature": "invalid-signature",
                },
            )

    assert response.status_code in {400, 403}