"""Integration tests for Twilio adapter with test credentials.

These tests use Twilio's test credentials to verify integration with
the actual Twilio API without making real calls or incurring charges.

Twilio Test Credentials:
- Account SID: ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx (test)
- Auth Token: your_test_auth_token
- Test phone numbers: +15005550006 (valid), +15005550001 (invalid)

Environment variables required:
- TWILIO_TEST_ACCOUNT_SID: Twilio test account SID
- TWILIO_TEST_AUTH_TOKEN: Twilio test auth token

To run these tests:
    pytest tests/integration/test_twilio_integration.py -v

Reference: https://www.twilio.com/docs/iam/test-credentials
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from vozbot.telephony.adapters.twilio_adapter import TwilioAdapter


# Skip all tests if test credentials are not available
pytestmark = pytest.mark.skipif(
    not os.getenv("TWILIO_TEST_ACCOUNT_SID") or not os.getenv("TWILIO_TEST_AUTH_TOKEN"),
    reason="Twilio test credentials not configured. "
    "Set TWILIO_TEST_ACCOUNT_SID and TWILIO_TEST_AUTH_TOKEN to run integration tests.",
)


@pytest.fixture
def twilio_test_adapter() -> TwilioAdapter:
    """Create a TwilioAdapter with test credentials."""
    return TwilioAdapter(
        account_sid=os.getenv("TWILIO_TEST_ACCOUNT_SID", ""),
        auth_token=os.getenv("TWILIO_TEST_AUTH_TOKEN", ""),
        phone_number="+15005550006",  # Twilio magic test number
    )


class TestTwilioTestCredentialsConnection:
    """Tests for connection with Twilio test credentials."""

    def test_client_initialization_with_test_credentials(
        self, twilio_test_adapter: TwilioAdapter
    ) -> None:
        """Test that client initializes with test credentials."""
        # Accessing client should not raise
        client = twilio_test_adapter.client
        assert client is not None

    def test_adapter_credentials_are_set(
        self, twilio_test_adapter: TwilioAdapter
    ) -> None:
        """Test that test credentials are properly configured."""
        assert twilio_test_adapter.account_sid.startswith("AC")
        assert len(twilio_test_adapter.auth_token) > 0


class TestTwilioTestCredentialsCallOperations:
    """Tests for call operations with test credentials.

    Note: These tests use mocked responses since we cannot make actual
    calls with test credentials. The integration point is verifying
    the adapter correctly formats requests for Twilio's API.
    """

    async def test_get_call_info_format(
        self, twilio_test_adapter: TwilioAdapter
    ) -> None:
        """Test that get_call_info makes properly formatted request.

        Note: With test credentials, we can verify the API call format
        but not retrieve actual call data.
        """
        # Mock the client's calls method since test creds can't fetch real calls
        mock_call = MagicMock()
        mock_call.sid = "CA_TEST_123"
        mock_call.from_ = "+15005550006"
        mock_call.from_formatted = None
        mock_call.to = "+15005550006"
        mock_call.to_formatted = None
        mock_call.status = "completed"
        mock_call.start_time = None

        with patch.object(
            twilio_test_adapter.client.calls("CA_TEST_123"),
            "fetch",
            return_value=mock_call,
        ):
            call_info = await twilio_test_adapter.get_call_info("CA_TEST_123")
            assert call_info.call_id == "CA_TEST_123"

    async def test_hangup_call_request_format(
        self, twilio_test_adapter: TwilioAdapter
    ) -> None:
        """Test that hangup_call sends correctly formatted request."""
        # Mock the client's calls method
        mock_update = MagicMock()

        with patch.object(
            twilio_test_adapter.client.calls("CA_TEST_123"),
            "update",
            mock_update,
        ):
            await twilio_test_adapter.hangup_call("CA_TEST_123")
            mock_update.assert_called_once_with(status="completed")


class TestTwilioTwiMLWithTestCredentials:
    """Tests for TwiML generation (no credentials needed for static methods)."""

    def test_generate_valid_twiml_for_twilio(self) -> None:
        """Test that generated TwiML is valid for Twilio."""
        # Generate various TwiML responses
        answer_twiml = TwilioAdapter.generate_answer_twiml(
            greeting_text="Test greeting"
        )
        play_twiml = TwilioAdapter.generate_play_twiml(
            audio_url="https://example.com/test.mp3"
        )
        transfer_twiml = TwilioAdapter.generate_transfer_twiml(
            target_number="+15005550006"  # Twilio test number
        )

        # All should produce valid XML starting with declaration
        for twiml in [answer_twiml, play_twiml, transfer_twiml]:
            xml_str = str(twiml)
            assert xml_str.startswith('<?xml version="1.0"')
            assert "<Response>" in xml_str

    def test_twiml_uses_correct_twilio_verbs(self) -> None:
        """Test that TwiML uses correct Twilio verb elements."""
        # Test Say verb
        say_twiml = str(
            TwilioAdapter.generate_answer_twiml(greeting_text="Hello")
        )
        assert "<Say" in say_twiml

        # Test Play verb
        play_twiml = str(
            TwilioAdapter.generate_play_twiml("https://example.com/audio.mp3")
        )
        assert "<Play" in play_twiml

        # Test Dial verb
        dial_twiml = str(
            TwilioAdapter.generate_transfer_twiml("+15005550006")
        )
        assert "<Dial" in dial_twiml

        # Test Record verb
        record_twiml = str(
            TwilioAdapter.generate_record_twiml("https://example.com/callback")
        )
        assert "<Record" in record_twiml

        # Test Hangup verb
        hangup_twiml = str(TwilioAdapter.generate_hangup_twiml())
        assert "<Hangup" in hangup_twiml

        # Test Gather verb
        gather_twiml = str(
            TwilioAdapter.generate_bilingual_greeting_twiml(
                "English", "Spanish", "https://example.com/action"
            )
        )
        assert "<Gather" in gather_twiml


class TestTwilioWebhookIntegration:
    """Integration tests for webhook handling with FastAPI."""

    def test_webhook_router_prefix(self) -> None:
        """Test that webhook router has correct prefix."""
        from vozbot.telephony.webhooks.twilio_webhooks import router

        assert router.prefix == "/webhooks/twilio"

    def test_webhook_routes_are_registered(self) -> None:
        """Test that all expected webhook routes are registered."""
        from vozbot.telephony.webhooks.twilio_webhooks import router

        route_paths = [route.path for route in router.routes]

        expected_paths = ["/voice", "/language-select", "/status", "/recording"]
        for expected in expected_paths:
            assert expected in route_paths, f"Route {expected} not found"

    def test_webhook_methods_are_post(self) -> None:
        """Test that all webhook routes accept POST method."""
        from vozbot.telephony.webhooks.twilio_webhooks import router

        for route in router.routes:
            if hasattr(route, "methods"):
                assert "POST" in route.methods, f"Route {route.path} should accept POST"


class TestTwilioMagicNumbers:
    """Tests using Twilio magic test numbers.

    Twilio provides special "magic" numbers that simulate different scenarios:
    - +15005550006: Valid number
    - +15005550001: Invalid number
    - +15005550009: Number that causes call to fail

    Reference: https://www.twilio.com/docs/iam/test-credentials#test-voice-calls-and-messages
    """

    def test_valid_test_number_format(self) -> None:
        """Test that Twilio valid test number is properly formatted."""
        valid_test_number = "+15005550006"

        # Should be E.164 format
        assert valid_test_number.startswith("+")
        assert len(valid_test_number) == 12  # +1 + 10 digits

    def test_transfer_twiml_with_test_number(self) -> None:
        """Test transfer TwiML generation with Twilio test number."""
        test_number = "+15005550006"

        twiml = TwilioAdapter.generate_transfer_twiml(target_number=test_number)
        xml_str = str(twiml)

        assert test_number in xml_str
        assert "<Dial" in xml_str
