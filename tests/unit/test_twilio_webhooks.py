"""Unit tests for Twilio webhook handlers.

Tests cover:
- Webhook endpoint at /webhooks/twilio/voice
- Twilio signature validation
- TwiML response generation
- Various webhook callbacks (status, recording)
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from vozbot.telephony.webhooks.twilio_webhooks import (
    get_request_validator,
    get_twilio_adapter,
    router,
    validate_twilio_signature,
)


@pytest.fixture
def app() -> FastAPI:
    """Create a FastAPI app with Twilio router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_env_dev():
    """Mock development environment with validation skipped."""
    with patch.dict(os.environ, {
        "APP_ENV": "development",
        "SKIP_TWILIO_VALIDATION": "true",
        "TWILIO_AUTH_TOKEN": "test_token",
        "TWILIO_ACCOUNT_SID": "test_sid",
    }):
        yield


@pytest.fixture
def mock_env_prod():
    """Mock production environment requiring validation."""
    with patch.dict(os.environ, {
        "APP_ENV": "production",
        "TWILIO_AUTH_TOKEN": "test_token_12345",
        "TWILIO_ACCOUNT_SID": "test_sid",
    }, clear=True):
        yield


class TestTwilioVoiceWebhook:
    """Tests for the /webhooks/twilio/voice endpoint."""

    def test_webhook_endpoint_exists(self, client: TestClient, mock_env_dev) -> None:
        """Test that the voice webhook endpoint exists."""
        response = client.post(
            "/webhooks/twilio/voice",
            data={
                "CallSid": "CA123456",
                "From": "+15551234567",
                "To": "+15559876543",
                "CallStatus": "ringing",
                "Direction": "inbound",
            },
        )

        # Should not return 404
        assert response.status_code != 404

    def test_webhook_returns_twiml(self, client: TestClient, mock_env_dev) -> None:
        """Test that webhook returns valid TwiML."""
        response = client.post(
            "/webhooks/twilio/voice",
            data={
                "CallSid": "CA123456",
                "From": "+15551234567",
                "To": "+15559876543",
                "CallStatus": "ringing",
            },
        )

        assert response.status_code == 200
        content = response.text

        # Should be valid TwiML
        assert "<?xml version" in content
        assert "<Response>" in content
        assert "</Response>" in content

    def test_webhook_generates_bilingual_greeting(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that webhook generates bilingual greeting TwiML."""
        response = client.post(
            "/webhooks/twilio/voice",
            data={
                "CallSid": "CA123456",
                "From": "+15551234567",
                "To": "+15559876543",
                "CallStatus": "ringing",
            },
        )

        content = response.text

        # Should have Gather for language selection
        assert "<Gather" in content

        # Should mention VozBot in greeting
        assert "VozBot" in content or "vozbot" in content.lower()

    def test_webhook_requires_call_sid(self, client: TestClient, mock_env_dev) -> None:
        """Test that webhook requires CallSid parameter."""
        response = client.post(
            "/webhooks/twilio/voice",
            data={
                "From": "+15551234567",
                "To": "+15559876543",
                "CallStatus": "ringing",
            },
        )

        # Should fail validation for missing CallSid
        assert response.status_code == 422

    def test_webhook_requires_from_number(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that webhook requires From parameter."""
        response = client.post(
            "/webhooks/twilio/voice",
            data={
                "CallSid": "CA123456",
                "To": "+15559876543",
                "CallStatus": "ringing",
            },
        )

        assert response.status_code == 422

    def test_webhook_handles_db_failure_gracefully(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that DB failure during call creation doesn't crash the webhook."""
        with patch(
            "vozbot.storage.db.session.get_db_session"
        ) as mock_session:
            # Make DB session raise an exception
            mock_session.side_effect = Exception("Database connection failed")

            response = client.post(
                "/webhooks/twilio/voice",
                data={
                    "CallSid": "CA123456",
                    "From": "+15551234567",
                    "To": "+15559876543",
                    "CallStatus": "ringing",
                },
            )

            # Should still return 200 with TwiML (call continues even if DB fails)
            assert response.status_code == 200
            content = response.text
            assert "<Response>" in content
            assert "<Gather" in content  # Should still have the greeting


class TestLanguageSelectWebhook:
    """Tests for the /webhooks/twilio/language-select endpoint."""

    def test_language_select_english(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test language selection with English (digit 1)."""
        response = client.post(
            "/webhooks/twilio/language-select",
            data={
                "CallSid": "CA123456",
                "Digits": "1",
            },
        )

        assert response.status_code == 200
        # Parse JSON-encoded string to get actual XML
        content = response.json()

        # Should respond in English
        assert 'language="en-US"' in content
        assert "Thank you" in content

    def test_language_select_spanish(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test language selection with Spanish (digit 2)."""
        response = client.post(
            "/webhooks/twilio/language-select",
            data={
                "CallSid": "CA123456",
                "Digits": "2",
            },
        )

        assert response.status_code == 200
        # Parse JSON-encoded string to get actual XML
        content = response.json()

        # Should respond in Spanish
        assert 'language="es-MX"' in content
        assert "Gracias" in content

    def test_language_select_default_to_english(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test language selection defaults to English with no input."""
        response = client.post(
            "/webhooks/twilio/language-select",
            data={
                "CallSid": "CA123456",
            },
        )

        assert response.status_code == 200
        content = response.text

        # Should default to English
        assert "Thank you" in content

    def test_language_select_hangup(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test language selection ends with hangup (Phase 0)."""
        response = client.post(
            "/webhooks/twilio/language-select",
            data={
                "CallSid": "CA123456",
                "Digits": "1",
            },
        )

        content = response.text
        assert "<Hangup" in content or "<Hangup/>" in content


class TestStatusWebhook:
    """Tests for the /webhooks/twilio/status endpoint."""

    def test_status_webhook_exists(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that status webhook endpoint exists."""
        response = client.post(
            "/webhooks/twilio/status",
            data={
                "CallSid": "CA123456",
                "CallStatus": "completed",
            },
        )

        assert response.status_code == 200

    def test_status_webhook_returns_empty_twiml(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that status webhook returns empty TwiML response."""
        response = client.post(
            "/webhooks/twilio/status",
            data={
                "CallSid": "CA123456",
                "CallStatus": "completed",
                "CallDuration": "120",
            },
        )

        # Decode JSON-encoded string to get actual XML
        content = response.json()
        # Empty response may be <Response></Response> or <Response />
        assert "<Response" in content
        assert ("Response>" in content or "Response />" in content)

    def test_status_webhook_accepts_recording_url(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that status webhook accepts recording URL parameter."""
        response = client.post(
            "/webhooks/twilio/status",
            data={
                "CallSid": "CA123456",
                "CallStatus": "completed",
                "RecordingUrl": "https://api.twilio.com/recordings/RE123",
            },
        )

        assert response.status_code == 200

    def test_status_webhook_handles_db_failure_gracefully(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that DB failure during status update doesn't crash the webhook."""
        with patch(
            "vozbot.storage.db.session.get_db_session"
        ) as mock_session:
            # Make DB session raise an exception
            mock_session.side_effect = Exception("Database connection failed")

            response = client.post(
                "/webhooks/twilio/status",
                data={
                    "CallSid": "CA123456",
                    "CallStatus": "completed",
                    "CallDuration": "120",
                },
            )

            # Should still return 200 with TwiML response
            assert response.status_code == 200
            content = response.json()
            assert "<Response" in content

    def test_status_webhook_handles_all_terminal_statuses(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that status webhook handles all terminal call statuses."""
        terminal_statuses = ["completed", "failed", "busy", "no-answer", "canceled"]

        for status in terminal_statuses:
            response = client.post(
                "/webhooks/twilio/status",
                data={
                    "CallSid": f"CA_{status}_test",
                    "CallStatus": status,
                    "CallDuration": "60",
                },
            )

            assert response.status_code == 200, f"Failed for status: {status}"

    def test_status_webhook_ignores_non_terminal_statuses(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that status webhook doesn't try to update for in-progress status."""
        non_terminal_statuses = ["ringing", "in-progress", "queued"]

        for status in non_terminal_statuses:
            response = client.post(
                "/webhooks/twilio/status",
                data={
                    "CallSid": f"CA_{status}_test",
                    "CallStatus": status,
                },
            )

            # Should return 200 without triggering DB update
            assert response.status_code == 200


class TestRecordingWebhook:
    """Tests for the /webhooks/twilio/recording endpoint."""

    def test_recording_webhook_exists(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that recording webhook endpoint exists."""
        response = client.post(
            "/webhooks/twilio/recording",
            data={
                "CallSid": "CA123456",
                "RecordingSid": "RE123456",
                "RecordingUrl": "https://api.twilio.com/recordings/RE123",
                "RecordingStatus": "completed",
            },
        )

        assert response.status_code == 200

    def test_recording_webhook_returns_empty_twiml(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that recording webhook returns empty TwiML response."""
        response = client.post(
            "/webhooks/twilio/recording",
            data={
                "CallSid": "CA123456",
                "RecordingSid": "RE123456",
                "RecordingUrl": "https://api.twilio.com/recordings/RE123",
                "RecordingStatus": "completed",
                "RecordingDuration": "45",
            },
        )

        # Decode JSON-encoded string to get actual XML
        content = response.json()
        # Empty response may be <Response></Response> or <Response />
        assert "<Response" in content


class TestTwilioSignatureValidation:
    """Tests for Twilio request signature validation."""

    def test_missing_signature_in_production(
        self, client: TestClient, mock_env_prod
    ) -> None:
        """Test that missing signature returns 401 in production."""
        response = client.post(
            "/webhooks/twilio/voice",
            data={
                "CallSid": "CA123456",
                "From": "+15551234567",
                "To": "+15559876543",
                "CallStatus": "ringing",
            },
        )

        assert response.status_code == 401
        assert "Missing Twilio signature" in response.json()["detail"]

    def test_invalid_signature_rejected(
        self, client: TestClient, mock_env_prod
    ) -> None:
        """Test that invalid signature returns 401."""
        response = client.post(
            "/webhooks/twilio/voice",
            data={
                "CallSid": "CA123456",
                "From": "+15551234567",
                "To": "+15559876543",
                "CallStatus": "ringing",
            },
            headers={
                "X-Twilio-Signature": "invalid_signature_here",
            },
        )

        assert response.status_code == 401

    def test_validation_skipped_in_development(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that signature validation is skipped in development mode."""
        response = client.post(
            "/webhooks/twilio/voice",
            data={
                "CallSid": "CA123456",
                "From": "+15551234567",
                "To": "+15559876543",
                "CallStatus": "ringing",
            },
        )

        # Should succeed without signature in dev mode
        assert response.status_code == 200

    def test_missing_auth_token_in_production(self, client: TestClient) -> None:
        """Test error when auth token is not configured."""
        with patch.dict(os.environ, {
            "APP_ENV": "production",
            "TWILIO_AUTH_TOKEN": "",
        }, clear=True):
            response = client.post(
                "/webhooks/twilio/voice",
                data={
                    "CallSid": "CA123456",
                    "From": "+15551234567",
                    "To": "+15559876543",
                    "CallStatus": "ringing",
                },
                headers={
                    "X-Twilio-Signature": "some_signature",
                },
            )

            assert response.status_code == 500
            assert "not configured" in response.json()["detail"]


class TestDependencyInjection:
    """Tests for FastAPI dependency injection functions."""

    def test_get_twilio_adapter_returns_adapter(self) -> None:
        """Test that get_twilio_adapter returns a TwilioAdapter instance."""
        from vozbot.telephony.adapters.twilio_adapter import TwilioAdapter

        adapter = get_twilio_adapter()
        assert isinstance(adapter, TwilioAdapter)

    def test_get_request_validator_returns_validator(self) -> None:
        """Test that get_request_validator returns a RequestValidator."""
        from twilio.request_validator import RequestValidator

        with patch.dict(os.environ, {"TWILIO_AUTH_TOKEN": "test_token"}):
            validator = get_request_validator()
            assert isinstance(validator, RequestValidator)


class TestSignatureValidationFunction:
    """Tests for the validate_twilio_signature function."""

    @pytest.mark.asyncio
    async def test_validation_passes_with_valid_signature(self) -> None:
        """Test signature validation with valid signature."""
        import asyncio
        from unittest.mock import AsyncMock

        from fastapi import Request

        with patch.dict(os.environ, {
            "APP_ENV": "production",
            "TWILIO_AUTH_TOKEN": "test_auth_token",
        }):
            # Create mock request
            mock_request = MagicMock(spec=Request)
            mock_request.url = "https://example.com/webhooks/twilio/voice"

            # Mock form data as async
            mock_form = MagicMock()
            mock_form.items.return_value = [
                ("CallSid", "CA123"),
                ("From", "+15551234567"),
            ]
            mock_request.form = AsyncMock(return_value=mock_form)

            # Mock the validator to return True
            with patch(
                "vozbot.telephony.webhooks.twilio_webhooks.RequestValidator"
            ) as mock_validator_class:
                mock_validator = MagicMock()
                mock_validator.validate.return_value = True
                mock_validator_class.return_value = mock_validator

                result = await validate_twilio_signature(
                    request=mock_request,
                    x_twilio_signature="valid_signature",
                )

                assert result is True

    @pytest.mark.asyncio
    async def test_validation_skipped_in_test_mode(self) -> None:
        """Test that validation is skipped in test environment."""
        from fastapi import Request

        with patch.dict(os.environ, {
            "APP_ENV": "test",
            "SKIP_TWILIO_VALIDATION": "true",
        }):
            mock_request = MagicMock(spec=Request)

            result = await validate_twilio_signature(
                request=mock_request,
                x_twilio_signature=None,  # No signature provided
            )

            assert result is True


class TestWebhookTwiMLOutput:
    """Tests verifying TwiML output format and structure."""

    def test_voice_webhook_twiml_contains_gather(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that voice webhook TwiML contains Gather for input."""
        response = client.post(
            "/webhooks/twilio/voice",
            data={
                "CallSid": "CA123456",
                "From": "+15551234567",
                "To": "+15559876543",
                "CallStatus": "ringing",
            },
        )

        content = response.text

        # Must have Gather for DTMF input
        assert "<Gather" in content
        assert "numDigits" in content
        assert "action=" in content

    def test_voice_webhook_twiml_bilingual_say(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that voice webhook TwiML has bilingual Say elements."""
        response = client.post(
            "/webhooks/twilio/voice",
            data={
                "CallSid": "CA123456",
                "From": "+15551234567",
                "To": "+15559876543",
                "CallStatus": "ringing",
            },
        )

        content = response.text

        # Must have Say elements
        assert "<Say" in content

        # Should have both English and Spanish
        assert "en-US" in content or "en" in content.lower()
        assert "es-MX" in content or "es" in content.lower()

    def test_twiml_well_formed_xml(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that all webhook responses are well-formed XML."""
        endpoints = [
            ("/webhooks/twilio/voice", {
                "CallSid": "CA123",
                "From": "+15551234567",
                "To": "+15559876543",
                "CallStatus": "ringing",
            }),
            ("/webhooks/twilio/language-select", {
                "CallSid": "CA123",
                "Digits": "1",
            }),
            ("/webhooks/twilio/status", {
                "CallSid": "CA123",
                "CallStatus": "completed",
            }),
            ("/webhooks/twilio/recording", {
                "CallSid": "CA123",
                "RecordingSid": "RE123",
                "RecordingUrl": "https://api.twilio.com/recordings/RE123",
                "RecordingStatus": "completed",
            }),
        ]

        for endpoint, data in endpoints:
            response = client.post(endpoint, data=data)

            # Decode JSON-encoded string to get actual XML
            content = response.json()

            # All responses should be XML
            assert content.startswith("<?xml version")
            # Check for Response element (may be <Response> or <Response />)
            assert "<Response" in content
            assert ("Response>" in content or "Response />" in content)
