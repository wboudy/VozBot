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

from vozbot.storage.db.models import Language
from vozbot.telephony.webhooks.twilio_webhooks import (
    ENGLISH_SPEECH_PATTERNS,
    MAX_LANGUAGE_ATTEMPTS,
    SPANISH_SPEECH_PATTERNS,
    detect_language_from_input,
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
            "/webhooks/twilio/language-select?attempt=1",
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
        assert "You have selected English" in content

    def test_language_select_spanish(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test language selection with Spanish (digit 2)."""
        response = client.post(
            "/webhooks/twilio/language-select?attempt=1",
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
        assert "Ha seleccionado español" in content

    def test_language_select_default_to_english(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test language selection defaults to English after max attempts with no input."""
        response = client.post(
            "/webhooks/twilio/language-select?attempt=3&timeout=true",
            data={
                "CallSid": "CA123456",
            },
        )

        assert response.status_code == 200
        content = response.text

        # Should default to English after max attempts
        assert "Defaulting to English" in content

    def test_language_select_hangup(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test language selection ends with hangup (Phase 0)."""
        response = client.post(
            "/webhooks/twilio/language-select?attempt=1",
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
            ("/webhooks/twilio/language-select?attempt=1", {
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


class TestLanguageDetectionFunction:
    """Tests for the detect_language_from_input function."""

    # DTMF Tests
    def test_detect_english_from_digit_1(self) -> None:
        """Test that pressing 1 selects English."""
        result = detect_language_from_input(digits="1")
        assert result == Language.EN

    def test_detect_spanish_from_digit_2(self) -> None:
        """Test that pressing 2 selects Spanish."""
        result = detect_language_from_input(digits="2")
        assert result == Language.ES

    def test_invalid_digit_returns_none(self) -> None:
        """Test that invalid digits return None."""
        for digit in ["0", "3", "4", "5", "6", "7", "8", "9", "*", "#"]:
            result = detect_language_from_input(digits=digit)
            assert result is None, f"Digit {digit} should return None"

    def test_empty_digit_returns_none(self) -> None:
        """Test that empty digit returns None."""
        result = detect_language_from_input(digits="")
        assert result is None

    # Speech Tests - English patterns
    def test_detect_english_from_speech_english(self) -> None:
        """Test that saying 'English' selects English."""
        result = detect_language_from_input(speech_result="English")
        assert result == Language.EN

    def test_detect_english_from_speech_ingles(self) -> None:
        """Test that saying 'inglés' selects English."""
        result = detect_language_from_input(speech_result="inglés")
        assert result == Language.EN

    def test_detect_english_from_speech_one(self) -> None:
        """Test that saying 'one' selects English."""
        result = detect_language_from_input(speech_result="one")
        assert result == Language.EN

    def test_detect_english_from_speech_uno(self) -> None:
        """Test that saying 'uno' selects English."""
        result = detect_language_from_input(speech_result="uno")
        assert result == Language.EN

    # Speech Tests - Spanish patterns
    def test_detect_spanish_from_speech_spanish(self) -> None:
        """Test that saying 'Spanish' selects Spanish."""
        result = detect_language_from_input(speech_result="Spanish")
        assert result == Language.ES

    def test_detect_spanish_from_speech_espanol(self) -> None:
        """Test that saying 'español' selects Spanish."""
        result = detect_language_from_input(speech_result="español")
        assert result == Language.ES

    def test_detect_spanish_from_speech_two(self) -> None:
        """Test that saying 'two' selects Spanish."""
        result = detect_language_from_input(speech_result="two")
        assert result == Language.ES

    def test_detect_spanish_from_speech_dos(self) -> None:
        """Test that saying 'dos' selects Spanish."""
        result = detect_language_from_input(speech_result="dos")
        assert result == Language.ES

    # Case insensitivity tests
    def test_speech_detection_case_insensitive(self) -> None:
        """Test that speech detection is case insensitive."""
        assert detect_language_from_input(speech_result="ENGLISH") == Language.EN
        assert detect_language_from_input(speech_result="SPANISH") == Language.ES
        assert detect_language_from_input(speech_result="english") == Language.EN
        assert detect_language_from_input(speech_result="spanish") == Language.ES
        assert detect_language_from_input(speech_result="EnGlIsH") == Language.EN

    def test_speech_with_surrounding_text(self) -> None:
        """Test that speech detection works with surrounding text."""
        assert detect_language_from_input(speech_result="I want English please") == Language.EN
        assert detect_language_from_input(speech_result="press one") == Language.EN
        assert detect_language_from_input(speech_result="número dos") == Language.ES

    # Edge cases
    def test_no_input_returns_none(self) -> None:
        """Test that no input returns None."""
        result = detect_language_from_input()
        assert result is None

    def test_dtmf_takes_precedence_over_speech(self) -> None:
        """Test that DTMF input takes precedence over speech."""
        # If both are provided, DTMF should win
        result = detect_language_from_input(digits="1", speech_result="Spanish")
        assert result == Language.EN

        result = detect_language_from_input(digits="2", speech_result="English")
        assert result == Language.ES

    def test_unrecognized_speech_returns_none(self) -> None:
        """Test that unrecognized speech returns None."""
        result = detect_language_from_input(speech_result="hello world")
        assert result is None

        result = detect_language_from_input(speech_result="I need help")
        assert result is None

    def test_speech_with_whitespace(self) -> None:
        """Test that speech detection handles whitespace."""
        assert detect_language_from_input(speech_result="  English  ") == Language.EN
        assert detect_language_from_input(speech_result="\tSpanish\n") == Language.ES


class TestLanguageDetectionConstants:
    """Tests for language detection constants."""

    def test_max_attempts_is_three(self) -> None:
        """Test that max attempts is set to 3."""
        assert MAX_LANGUAGE_ATTEMPTS == 3

    def test_english_patterns_contain_expected_values(self) -> None:
        """Test that English patterns contain expected values."""
        expected = {"english", "inglés", "ingles", "one", "uno", "1"}
        assert expected == ENGLISH_SPEECH_PATTERNS

    def test_spanish_patterns_contain_expected_values(self) -> None:
        """Test that Spanish patterns contain expected values."""
        expected = {"spanish", "español", "espanol", "two", "dos", "2"}
        assert expected == SPANISH_SPEECH_PATTERNS


class TestLanguageSelectWebhookEnhanced:
    """Enhanced tests for the language selection webhook."""

    def test_language_select_with_speech_english(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test language selection with speech input for English."""
        response = client.post(
            "/webhooks/twilio/language-select?attempt=1",
            data={
                "CallSid": "CA123456",
                "SpeechResult": "English",
            },
        )

        assert response.status_code == 200
        content = response.json()

        # Should respond in English
        assert 'language="en-US"' in content
        assert "You have selected English" in content

    def test_language_select_with_speech_spanish(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test language selection with speech input for Spanish."""
        response = client.post(
            "/webhooks/twilio/language-select?attempt=1",
            data={
                "CallSid": "CA123456",
                "SpeechResult": "español",
            },
        )

        assert response.status_code == 200
        content = response.json()

        # Should respond in Spanish
        assert 'language="es-MX"' in content
        assert "Ha seleccionado español" in content

    def test_language_select_retry_on_invalid_input(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that invalid input triggers a retry."""
        response = client.post(
            "/webhooks/twilio/language-select?attempt=1",
            data={
                "CallSid": "CA123456",
                "Digits": "5",  # Invalid digit
            },
        )

        assert response.status_code == 200
        content = response.json()

        # Should have error message and Gather for retry
        assert "did not understand" in content
        assert "<Gather" in content
        assert "attempt=2" in content

    def test_language_select_retry_on_timeout(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that timeout triggers a retry."""
        response = client.post(
            "/webhooks/twilio/language-select?attempt=1&timeout=true",
            data={
                "CallSid": "CA123456",
            },
        )

        assert response.status_code == 200
        content = response.json()

        # Should have timeout message and Gather for retry
        assert "did not receive" in content
        assert "<Gather" in content
        assert "attempt=2" in content

    def test_language_select_defaults_to_english_after_max_attempts(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that 3 failed attempts default to English."""
        response = client.post(
            "/webhooks/twilio/language-select?attempt=3",
            data={
                "CallSid": "CA123456",
                "Digits": "9",  # Invalid digit on 3rd attempt
            },
        )

        assert response.status_code == 200
        content = response.json()

        # Should default to English with message
        assert "Defaulting to English" in content
        assert 'language="en-US"' in content
        # Should NOT have another Gather
        assert "<Gather" not in content

    def test_language_select_timeout_defaults_to_english_on_attempt_3(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that timeout on attempt 3 defaults to English."""
        response = client.post(
            "/webhooks/twilio/language-select?attempt=3&timeout=true",
            data={
                "CallSid": "CA123456",
            },
        )

        assert response.status_code == 200
        content = response.json()

        # Should default to English
        assert "Defaulting to English" in content
        assert 'language="en-US"' in content

    def test_language_select_confirmation_message_english(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test confirmation message for English selection."""
        response = client.post(
            "/webhooks/twilio/language-select?attempt=1",
            data={
                "CallSid": "CA123456",
                "Digits": "1",
            },
        )

        content = response.json()

        assert "You have selected English" in content

    def test_language_select_confirmation_message_spanish(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test confirmation message for Spanish selection."""
        response = client.post(
            "/webhooks/twilio/language-select?attempt=1",
            data={
                "CallSid": "CA123456",
                "Digits": "2",
            },
        )

        content = response.json()

        assert "Ha seleccionado español" in content

    def test_language_select_stores_language_in_db(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that language selection stores language in database."""
        with patch(
            "vozbot.telephony.webhooks.twilio_webhooks._store_language_selection"
        ) as mock_store:
            response = client.post(
                "/webhooks/twilio/language-select?attempt=1",
                data={
                    "CallSid": "CA123456",
                    "Digits": "2",
                },
            )

            assert response.status_code == 200
            # Verify store function was called with correct args
            mock_store.assert_called_once()
            call_args = mock_store.call_args
            assert call_args[0][0] == "CA123456"
            assert call_args[0][1] == Language.ES

    def test_language_select_db_failure_does_not_crash(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that DB failure during language storage doesn't crash."""
        # Mock the DB session at its source module - it's imported inside
        # the _store_language_selection function
        with patch(
            "vozbot.storage.db.session.get_db_session"
        ) as mock_session:
            # Make DB session raise an exception
            mock_session.side_effect = Exception("Database connection failed")

            response = client.post(
                "/webhooks/twilio/language-select?attempt=1",
                data={
                    "CallSid": "CA123456",
                    "Digits": "1",
                },
            )

            # Should still return 200 with confirmation
            # (DB failure is caught and logged, call continues)
            assert response.status_code == 200
            content = response.json()
            assert "You have selected English" in content


class TestBilingualGreetingTwiML:
    """Tests for the bilingual greeting TwiML generation."""

    def test_voice_webhook_has_speech_input(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that voice webhook TwiML includes speech input."""
        response = client.post(
            "/webhooks/twilio/voice",
            data={
                "CallSid": "CA123456",
                "From": "+15551234567",
                "To": "+15559876543",
                "CallStatus": "ringing",
            },
        )

        # Parse JSON-encoded string to get actual XML
        content = response.json()

        # Should have speech input type
        assert 'input="dtmf speech"' in content

    def test_voice_webhook_has_speech_hints(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that voice webhook TwiML includes speech hints."""
        response = client.post(
            "/webhooks/twilio/voice",
            data={
                "CallSid": "CA123456",
                "From": "+15551234567",
                "To": "+15559876543",
                "CallStatus": "ringing",
            },
        )

        # Parse JSON-encoded string to get actual XML
        content = response.json()

        # Should have hints for speech recognition
        assert "hints=" in content
        assert "English" in content or "english" in content.lower()

    def test_voice_webhook_has_timeout(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that voice webhook TwiML has proper timeout."""
        response = client.post(
            "/webhooks/twilio/voice",
            data={
                "CallSid": "CA123456",
                "From": "+15551234567",
                "To": "+15559876543",
                "CallStatus": "ringing",
            },
        )

        # Parse JSON-encoded string to get actual XML
        content = response.json()

        # Should have timeout setting
        assert 'timeout="10"' in content

    def test_voice_webhook_action_url_includes_attempt(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that voice webhook action URL includes attempt parameter."""
        response = client.post(
            "/webhooks/twilio/voice",
            data={
                "CallSid": "CA123456",
                "From": "+15551234567",
                "To": "+15559876543",
                "CallStatus": "ringing",
            },
        )

        # Parse JSON-encoded string to get actual XML
        content = response.json()

        # Should have attempt=1 in action URL
        assert "attempt=1" in content


class TestTransferStatusWebhook:
    """Tests for the /webhooks/twilio/transfer-status endpoint."""

    def test_transfer_status_webhook_exists(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that transfer status webhook endpoint exists."""
        response = client.post(
            "/webhooks/twilio/transfer-status",
            data={
                "CallSid": "CA123456",
            },
        )

        # Should not return 404
        assert response.status_code != 404

    def test_transfer_status_completed(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test handling of completed transfer."""
        response = client.post(
            "/webhooks/twilio/transfer-status",
            data={
                "CallSid": "CA123456",
                "DialCallSid": "CA789012",
                "DialCallStatus": "completed",
                "DialCallDuration": "120",
                "Called": "+15559999999",
            },
        )

        assert response.status_code == 200
        # Empty TwiML response for completed calls
        content = response.json()
        assert "<Response" in content

    def test_transfer_status_answered(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test handling of answered (connected) transfer."""
        response = client.post(
            "/webhooks/twilio/transfer-status",
            data={
                "CallSid": "CA123456",
                "DialCallSid": "CA789012",
                "DialCallStatus": "answered",
                "Called": "+15559999999",
            },
        )

        assert response.status_code == 200
        content = response.json()
        assert "<Response" in content

    def test_transfer_status_busy(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test handling of busy transfer target."""
        response = client.post(
            "/webhooks/twilio/transfer-status",
            data={
                "CallSid": "CA123456",
                "DialCallSid": "CA789012",
                "DialCallStatus": "busy",
                "Called": "+15559999999",
            },
        )

        assert response.status_code == 200
        content = response.json()

        # Should have fallback message
        assert "unable to connect" in content.lower() or "sorry" in content.lower()
        # Should have hangup
        assert "<Hangup" in content

    def test_transfer_status_no_answer(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test handling of no-answer transfer."""
        response = client.post(
            "/webhooks/twilio/transfer-status",
            data={
                "CallSid": "CA123456",
                "DialCallSid": "CA789012",
                "DialCallStatus": "no-answer",
                "Called": "+15559999999",
            },
        )

        assert response.status_code == 200
        content = response.json()

        # Should have fallback message
        assert "unable to connect" in content.lower() or "sorry" in content.lower()

    def test_transfer_status_failed(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test handling of failed transfer."""
        response = client.post(
            "/webhooks/twilio/transfer-status",
            data={
                "CallSid": "CA123456",
                "DialCallStatus": "failed",
                "Called": "+15559999999",
            },
        )

        assert response.status_code == 200
        content = response.json()

        # Should have fallback message in both languages
        assert "sorry" in content.lower()
        assert "siento" in content.lower() or "disponible" in content.lower()

    def test_transfer_status_canceled(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test handling of canceled transfer."""
        response = client.post(
            "/webhooks/twilio/transfer-status",
            data={
                "CallSid": "CA123456",
                "DialCallStatus": "canceled",
                "Called": "+15559999999",
            },
        )

        assert response.status_code == 200
        content = response.json()

        # Should have hangup
        assert "<Hangup" in content

    def test_transfer_status_without_dial_status(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test handling transfer status without DialCallStatus."""
        response = client.post(
            "/webhooks/twilio/transfer-status",
            data={
                "CallSid": "CA123456",
                "CallStatus": "in-progress",
            },
        )

        assert response.status_code == 200
        # Empty TwiML response
        content = response.json()
        assert "<Response" in content

    def test_transfer_status_db_failure_graceful(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that DB failure during transfer status update is handled gracefully."""
        # Patch the DB session to simulate database failure
        with patch(
            "vozbot.storage.db.session.get_db_session"
        ) as mock_session:
            mock_session.side_effect = Exception("Database error")

            response = client.post(
                "/webhooks/twilio/transfer-status",
                data={
                    "CallSid": "CA123456",
                    "DialCallStatus": "completed",
                    "DialCallDuration": "60",
                },
            )

            # Should still return 200 (DB failure is caught and logged)
            assert response.status_code == 200

    def test_transfer_status_returns_bilingual_failure_message(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that failed transfer returns bilingual error message."""
        response = client.post(
            "/webhooks/twilio/transfer-status",
            data={
                "CallSid": "CA123456",
                "DialCallStatus": "no-answer",
            },
        )

        content = response.json()

        # Should have both English and Spanish messages
        assert 'language="en-US"' in content
        assert 'language="es-MX"' in content


class TestTransferFallbackToCallback:
    """Tests for transfer fallback to callback task functionality.

    When a transfer fails, the system should:
    1. Create a callback task with priority=0 (critical)
    2. Include notes: "Transfer failed - urgent callback"
    3. Play bilingual fallback messages to the caller
    """

    def test_transfer_failure_message_english(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that transfer failure plays English fallback message."""
        response = client.post(
            "/webhooks/twilio/transfer-status",
            data={
                "CallSid": "CA123456",
                "DialCallStatus": "no-answer",
                "Called": "+15559999999",
            },
        )

        content = response.json()

        # Should have the specific English fallback message
        assert "no one is available" in content
        assert "call you back within 1 hour" in content

    def test_transfer_failure_message_spanish(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that transfer failure plays Spanish fallback message."""
        response = client.post(
            "/webhooks/twilio/transfer-status",
            data={
                "CallSid": "CA123456",
                "DialCallStatus": "busy",
                "Called": "+15559999999",
            },
        )

        content = response.json()

        # Should have the specific Spanish fallback message
        assert "no hay nadie disponible" in content
        assert "dentro de 1 hora" in content

    def test_transfer_failure_creates_callback_task(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that transfer failure triggers callback task creation."""
        with patch(
            "vozbot.telephony.webhooks.twilio_webhooks._handle_transfer_failure"
        ) as mock_handler:
            response = client.post(
                "/webhooks/twilio/transfer-status",
                data={
                    "CallSid": "CA_TEST_FAILURE",
                    "DialCallStatus": "no-answer",
                    "Called": "+15559999999",
                },
            )

            assert response.status_code == 200
            # Verify the handler was called
            mock_handler.assert_called_once()
            call_args = mock_handler.call_args
            assert call_args[0][0] == "CA_TEST_FAILURE"  # call_sid
            assert call_args[0][1] == "no-answer"  # dial_status
            assert call_args[0][2] == "+15559999999"  # target_number

    def test_transfer_failure_all_failure_statuses_trigger_callback(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that all failure statuses trigger callback task creation."""
        failure_statuses = ["busy", "no-answer", "failed", "canceled"]

        for status in failure_statuses:
            with patch(
                "vozbot.telephony.webhooks.twilio_webhooks._handle_transfer_failure"
            ) as mock_handler:
                response = client.post(
                    "/webhooks/twilio/transfer-status",
                    data={
                        "CallSid": f"CA_{status}_test",
                        "DialCallStatus": status,
                        "Called": "+15559999999",
                    },
                )

                assert response.status_code == 200, f"Failed for status: {status}"
                mock_handler.assert_called_once()
                assert mock_handler.call_args[0][1] == status

    def test_transfer_success_does_not_create_callback_task(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that successful transfer does NOT create callback task."""
        with patch(
            "vozbot.telephony.webhooks.twilio_webhooks._handle_transfer_failure"
        ) as mock_handler:
            response = client.post(
                "/webhooks/twilio/transfer-status",
                data={
                    "CallSid": "CA123456",
                    "DialCallStatus": "completed",
                    "DialCallDuration": "120",
                },
            )

            assert response.status_code == 200
            # Should NOT call the failure handler
            mock_handler.assert_not_called()

    def test_transfer_answered_does_not_create_callback_task(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that answered transfer does NOT create callback task."""
        with patch(
            "vozbot.telephony.webhooks.twilio_webhooks._handle_transfer_failure"
        ) as mock_handler:
            response = client.post(
                "/webhooks/twilio/transfer-status",
                data={
                    "CallSid": "CA123456",
                    "DialCallStatus": "answered",
                },
            )

            assert response.status_code == 200
            mock_handler.assert_not_called()

    def test_transfer_failure_handler_graceful_on_error(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that failure handler error doesn't crash webhook."""
        with patch(
            "vozbot.telephony.webhooks.twilio_webhooks._handle_transfer_failure"
        ) as mock_handler:
            mock_handler.side_effect = Exception("Database exploded")

            response = client.post(
                "/webhooks/twilio/transfer-status",
                data={
                    "CallSid": "CA123456",
                    "DialCallStatus": "no-answer",
                },
            )

            # Should still return 200 with fallback message
            assert response.status_code == 200
            content = response.json()
            # Fallback message should still be present
            assert "no one is available" in content

    def test_transfer_failure_hangup_after_message(
        self, client: TestClient, mock_env_dev
    ) -> None:
        """Test that hangup occurs after fallback message."""
        response = client.post(
            "/webhooks/twilio/transfer-status",
            data={
                "CallSid": "CA123456",
                "DialCallStatus": "failed",
            },
        )

        content = response.json()

        # Should end with hangup
        assert "<Hangup" in content


class TestHandleTransferFailureFunction:
    """Unit tests for the _handle_transfer_failure function."""

    @pytest.mark.asyncio
    async def test_handle_transfer_failure_creates_critical_task(self) -> None:
        """Test that _handle_transfer_failure creates a critical priority task."""
        from unittest.mock import AsyncMock, MagicMock

        from vozbot.storage.db.models import Call, TaskPriority
        from vozbot.telephony.webhooks.twilio_webhooks import (
            TRANSFER_FAILED_NOTES,
            _handle_transfer_failure,
        )

        # Create mock call
        mock_call = MagicMock(spec=Call)
        mock_call.from_number = "+15551234567"
        mock_call.id = "CA_TEST_123"

        # Create mock session
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        # Create mock service
        mock_service = MagicMock()
        mock_service.get_call = AsyncMock(return_value=mock_call)
        mock_service.update_call_status = AsyncMock()

        # Patch at the source module where it's imported from
        with patch("vozbot.storage.db.session.get_db_session") as mock_get_session:
            # Make get_db_session return an async context manager
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_get_session.return_value = mock_context

            with patch("vozbot.storage.services.call_service.CallService") as mock_service_class:
                mock_service_class.return_value = mock_service

                await _handle_transfer_failure(
                    call_sid="CA_TEST_123",
                    dial_status="no-answer",
                    target_number="+15559999999",
                )

                # Verify task was added
                mock_session.add.assert_called_once()
                added_task = mock_session.add.call_args[0][0]

                # Verify task properties
                assert added_task.priority == TaskPriority.CRITICAL
                assert added_task.callback_number == "+15551234567"
                assert added_task.notes == TRANSFER_FAILED_NOTES
                assert added_task.call_id == "CA_TEST_123"

    @pytest.mark.asyncio
    async def test_handle_transfer_failure_call_not_found(self) -> None:
        """Test that _handle_transfer_failure handles missing call gracefully."""
        from unittest.mock import AsyncMock, MagicMock

        from vozbot.telephony.webhooks.twilio_webhooks import _handle_transfer_failure

        # Create mock service that returns None for get_call
        mock_service = MagicMock()
        mock_service.get_call = AsyncMock(return_value=None)

        mock_session = AsyncMock()

        with patch("vozbot.storage.db.session.get_db_session") as mock_get_session:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_get_session.return_value = mock_context

            with patch("vozbot.storage.services.call_service.CallService") as mock_service_class:
                mock_service_class.return_value = mock_service

                # Should not raise - handles gracefully
                await _handle_transfer_failure(
                    call_sid="CA_NONEXISTENT",
                    dial_status="no-answer",
                    target_number="+15559999999",
                )

                # Should not add any task
                mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_transfer_failure_db_error_graceful(self) -> None:
        """Test that _handle_transfer_failure handles DB errors gracefully."""
        from vozbot.telephony.webhooks.twilio_webhooks import _handle_transfer_failure

        with patch("vozbot.storage.db.session.get_db_session") as mock_get_session:
            mock_get_session.side_effect = Exception("Database connection failed")

            # Should not raise - logs error and returns
            await _handle_transfer_failure(
                call_sid="CA_TEST",
                dial_status="failed",
                target_number="+15559999999",
            )


class TestTransferFallbackConstants:
    """Tests for transfer fallback message constants."""

    def test_english_fallback_message_content(self) -> None:
        """Test English fallback message contains required elements."""
        from vozbot.telephony.webhooks.twilio_webhooks import TRANSFER_FALLBACK_MESSAGE_EN

        assert "sorry" in TRANSFER_FALLBACK_MESSAGE_EN.lower()
        assert "no one is available" in TRANSFER_FALLBACK_MESSAGE_EN.lower()
        assert "call you back" in TRANSFER_FALLBACK_MESSAGE_EN.lower()
        assert "1 hour" in TRANSFER_FALLBACK_MESSAGE_EN

    def test_spanish_fallback_message_content(self) -> None:
        """Test Spanish fallback message contains required elements."""
        from vozbot.telephony.webhooks.twilio_webhooks import TRANSFER_FALLBACK_MESSAGE_ES

        assert "siento" in TRANSFER_FALLBACK_MESSAGE_ES.lower()
        assert "disponible" in TRANSFER_FALLBACK_MESSAGE_ES.lower()
        assert "llamada" in TRANSFER_FALLBACK_MESSAGE_ES.lower()
        assert "1 hora" in TRANSFER_FALLBACK_MESSAGE_ES

    def test_transfer_failed_notes(self) -> None:
        """Test transfer failed notes constant."""
        from vozbot.telephony.webhooks.twilio_webhooks import TRANSFER_FAILED_NOTES

        assert TRANSFER_FAILED_NOTES == "Transfer failed - urgent callback"
