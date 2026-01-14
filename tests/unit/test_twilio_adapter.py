"""Unit tests for the TwilioAdapter implementation.

Tests cover:
- TwilioAdapter class implementing TelephonyAdapter ABC
- TwiML generation methods (answer, play, transfer, record, hangup)
- Twilio status mapping
- Error handling for missing credentials
"""

import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from vozbot.telephony.adapters.base import CallInfo, CallStatus, TelephonyAdapter
from vozbot.telephony.adapters.twilio_adapter import TwilioAdapter


class TestTwilioAdapterInterface:
    """Tests that TwilioAdapter implements TelephonyAdapter correctly."""

    def test_twilio_adapter_extends_telephony_adapter(self) -> None:
        """Verify TwilioAdapter extends TelephonyAdapter ABC."""
        adapter = TwilioAdapter(
            account_sid="test_sid",
            auth_token="test_token",
            phone_number="+15551234567",
        )
        assert isinstance(adapter, TelephonyAdapter)

    def test_adapter_has_all_required_methods(self) -> None:
        """Verify TwilioAdapter implements all abstract methods."""
        adapter = TwilioAdapter(
            account_sid="test_sid",
            auth_token="test_token",
        )

        # Check all required methods exist
        assert hasattr(adapter, "answer_call")
        assert hasattr(adapter, "hangup_call")
        assert hasattr(adapter, "transfer_call")
        assert hasattr(adapter, "play_audio")
        assert hasattr(adapter, "get_call_info")

        # Check they are callable
        assert callable(adapter.answer_call)
        assert callable(adapter.hangup_call)
        assert callable(adapter.transfer_call)
        assert callable(adapter.play_audio)
        assert callable(adapter.get_call_info)


class TestTwilioAdapterInitialization:
    """Tests for TwilioAdapter initialization."""

    def test_init_with_explicit_credentials(self) -> None:
        """Test initialization with explicitly provided credentials."""
        adapter = TwilioAdapter(
            account_sid="AC123456",
            auth_token="auth_token_here",
            phone_number="+15551234567",
        )

        assert adapter.account_sid == "AC123456"
        assert adapter.auth_token == "auth_token_here"
        assert adapter.phone_number == "+15551234567"
        assert adapter._client is None  # Lazy initialization

    def test_init_with_env_vars(self) -> None:
        """Test initialization from environment variables."""
        with patch.dict(os.environ, {
            "TWILIO_ACCOUNT_SID": "AC_ENV_SID",
            "TWILIO_AUTH_TOKEN": "env_token",
            "TWILIO_PHONE_NUMBER": "+15559876543",
        }):
            adapter = TwilioAdapter()

            assert adapter.account_sid == "AC_ENV_SID"
            assert adapter.auth_token == "env_token"
            assert adapter.phone_number == "+15559876543"

    def test_explicit_credentials_override_env_vars(self) -> None:
        """Test that explicit credentials take precedence over env vars."""
        with patch.dict(os.environ, {
            "TWILIO_ACCOUNT_SID": "AC_ENV_SID",
            "TWILIO_AUTH_TOKEN": "env_token",
        }):
            adapter = TwilioAdapter(
                account_sid="AC_EXPLICIT",
                auth_token="explicit_token",
            )

            assert adapter.account_sid == "AC_EXPLICIT"
            assert adapter.auth_token == "explicit_token"


class TestTwilioClientProperty:
    """Tests for the lazy-loaded Twilio client property."""

    def test_client_raises_without_credentials(self) -> None:
        """Test that accessing client without credentials raises ValueError."""
        adapter = TwilioAdapter(account_sid="", auth_token="")

        with pytest.raises(ValueError) as exc_info:
            _ = adapter.client

        assert "credentials not configured" in str(exc_info.value).lower()

    def test_client_raises_with_partial_credentials(self) -> None:
        """Test that partial credentials raise ValueError."""
        adapter = TwilioAdapter(account_sid="AC123", auth_token="")

        with pytest.raises(ValueError):
            _ = adapter.client

    @patch("vozbot.telephony.adapters.twilio_adapter.Client")
    def test_client_lazy_initialization(self, mock_client_class: MagicMock) -> None:
        """Test that client is lazily initialized."""
        mock_client_class.return_value = MagicMock()

        adapter = TwilioAdapter(
            account_sid="AC123456",
            auth_token="auth_token",
        )

        # Client not created yet
        mock_client_class.assert_not_called()

        # Access client
        _ = adapter.client

        # Now it should be created
        mock_client_class.assert_called_once_with("AC123456", "auth_token")

    @patch("vozbot.telephony.adapters.twilio_adapter.Client")
    def test_client_cached_after_first_access(self, mock_client_class: MagicMock) -> None:
        """Test that client is cached after first access."""
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance

        adapter = TwilioAdapter(
            account_sid="AC123456",
            auth_token="auth_token",
        )

        # Access client multiple times
        client1 = adapter.client
        client2 = adapter.client
        client3 = adapter.client

        # Should only create once
        mock_client_class.assert_called_once()
        assert client1 is client2 is client3


class TestTwilioAdapterMethods:
    """Tests for TwilioAdapter async methods with mocked Twilio client."""

    @pytest.fixture
    def mock_twilio_client(self) -> MagicMock:
        """Create a mock Twilio client."""
        client = MagicMock()
        return client

    @pytest.fixture
    def adapter_with_mock_client(self, mock_twilio_client: MagicMock) -> TwilioAdapter:
        """Create a TwilioAdapter with a mocked client."""
        adapter = TwilioAdapter(
            account_sid="AC123456",
            auth_token="auth_token",
        )
        adapter._client = mock_twilio_client
        return adapter

    async def test_answer_call(self, adapter_with_mock_client: TwilioAdapter) -> None:
        """Test answer_call method (no-op for Twilio, handled by webhook)."""
        result = await adapter_with_mock_client.answer_call("CA123456")

        # For Twilio, answer is handled by webhook returning TwiML
        assert result is None

    async def test_hangup_call(
        self,
        adapter_with_mock_client: TwilioAdapter,
        mock_twilio_client: MagicMock,
    ) -> None:
        """Test hangup_call updates call status to completed."""
        await adapter_with_mock_client.hangup_call("CA123456")

        mock_twilio_client.calls.assert_called_once_with("CA123456")
        mock_twilio_client.calls().update.assert_called_once_with(status="completed")

    async def test_transfer_call(
        self,
        adapter_with_mock_client: TwilioAdapter,
        mock_twilio_client: MagicMock,
    ) -> None:
        """Test transfer_call updates call with Dial TwiML."""
        result = await adapter_with_mock_client.transfer_call("CA123456", "+15559999999")

        assert result is True
        mock_twilio_client.calls.assert_called_with("CA123456")

        # Check that TwiML was passed to update
        update_call = mock_twilio_client.calls().update
        update_call.assert_called_once()
        twiml_arg = update_call.call_args[1]["twiml"]

        # Verify TwiML contains Dial verb
        assert "<Dial" in twiml_arg
        assert "+15559999999" in twiml_arg

    async def test_play_audio(
        self,
        adapter_with_mock_client: TwilioAdapter,
        mock_twilio_client: MagicMock,
    ) -> None:
        """Test play_audio updates call with Play TwiML."""
        audio_url = "https://example.com/audio.mp3"

        await adapter_with_mock_client.play_audio("CA123456", audio_url)

        mock_twilio_client.calls.assert_called_with("CA123456")

        # Check that TwiML was passed to update
        update_call = mock_twilio_client.calls().update
        update_call.assert_called_once()
        twiml_arg = update_call.call_args[1]["twiml"]

        # Verify TwiML contains Play verb with URL
        assert "<Play" in twiml_arg
        assert audio_url in twiml_arg

    async def test_get_call_info(
        self,
        adapter_with_mock_client: TwilioAdapter,
        mock_twilio_client: MagicMock,
    ) -> None:
        """Test get_call_info retrieves and maps call data."""
        # Setup mock call
        mock_call = MagicMock()
        mock_call.sid = "CA123456"
        mock_call.from_ = "+15551234567"
        mock_call.from_formatted = "+1 (555) 123-4567"
        mock_call.to = "+15559876543"
        mock_call.to_formatted = "+1 (555) 987-6543"
        mock_call.status = "in-progress"
        mock_call.start_time = datetime(2024, 1, 15, 10, 30, 0)

        mock_twilio_client.calls().fetch.return_value = mock_call

        result = await adapter_with_mock_client.get_call_info("CA123456")

        assert isinstance(result, CallInfo)
        assert result.call_id == "CA123456"
        assert result.from_number == "+1 (555) 123-4567"  # Uses formatted
        assert result.to_number == "+1 (555) 987-6543"
        assert result.status == CallStatus.IN_PROGRESS
        assert result.started_at == datetime(2024, 1, 15, 10, 30, 0)

    async def test_get_call_info_without_formatted(
        self,
        adapter_with_mock_client: TwilioAdapter,
        mock_twilio_client: MagicMock,
    ) -> None:
        """Test get_call_info falls back to raw numbers if no formatted."""
        mock_call = MagicMock()
        mock_call.sid = "CA123456"
        mock_call.from_ = "+15551234567"
        mock_call.from_formatted = None
        mock_call.to = "+15559876543"
        mock_call.to_formatted = None
        mock_call.status = "ringing"
        mock_call.start_time = None  # Can be None for queued calls

        mock_twilio_client.calls().fetch.return_value = mock_call

        result = await adapter_with_mock_client.get_call_info("CA123456")

        assert result.from_number == "+15551234567"
        assert result.to_number == "+15559876543"


class TestTwilioStatusMapping:
    """Tests for Twilio status to CallStatus mapping."""

    def test_map_queued_status(self) -> None:
        """Test mapping 'queued' status."""
        adapter = TwilioAdapter(account_sid="test", auth_token="test")
        assert adapter._map_twilio_status("queued") == CallStatus.QUEUED

    def test_map_ringing_status(self) -> None:
        """Test mapping 'ringing' status."""
        adapter = TwilioAdapter(account_sid="test", auth_token="test")
        assert adapter._map_twilio_status("ringing") == CallStatus.RINGING

    def test_map_in_progress_status(self) -> None:
        """Test mapping 'in-progress' status (note hyphen)."""
        adapter = TwilioAdapter(account_sid="test", auth_token="test")
        assert adapter._map_twilio_status("in-progress") == CallStatus.IN_PROGRESS

    def test_map_completed_status(self) -> None:
        """Test mapping 'completed' status."""
        adapter = TwilioAdapter(account_sid="test", auth_token="test")
        assert adapter._map_twilio_status("completed") == CallStatus.COMPLETED

    def test_map_busy_status(self) -> None:
        """Test mapping 'busy' status."""
        adapter = TwilioAdapter(account_sid="test", auth_token="test")
        assert adapter._map_twilio_status("busy") == CallStatus.BUSY

    def test_map_failed_status(self) -> None:
        """Test mapping 'failed' status."""
        adapter = TwilioAdapter(account_sid="test", auth_token="test")
        assert adapter._map_twilio_status("failed") == CallStatus.FAILED

    def test_map_no_answer_status(self) -> None:
        """Test mapping 'no-answer' status (note hyphen)."""
        adapter = TwilioAdapter(account_sid="test", auth_token="test")
        assert adapter._map_twilio_status("no-answer") == CallStatus.NO_ANSWER

    def test_map_canceled_status(self) -> None:
        """Test mapping 'canceled' status."""
        adapter = TwilioAdapter(account_sid="test", auth_token="test")
        assert adapter._map_twilio_status("canceled") == CallStatus.CANCELED

    def test_map_unknown_status_defaults_to_in_progress(self) -> None:
        """Test that unknown status defaults to IN_PROGRESS."""
        adapter = TwilioAdapter(account_sid="test", auth_token="test")
        assert adapter._map_twilio_status("unknown-status") == CallStatus.IN_PROGRESS


class TestTwiMLGenerationAnswerCall:
    """Tests for TwiML generation - answer_call."""

    def test_generate_answer_twiml_with_greeting_url(self) -> None:
        """Test answer TwiML with audio greeting URL."""
        response = TwilioAdapter.generate_answer_twiml(
            greeting_url="https://example.com/greeting.mp3"
        )
        twiml = str(response)

        assert "<?xml version" in twiml
        assert "<Response>" in twiml
        assert "<Play>" in twiml
        assert "https://example.com/greeting.mp3" in twiml

    def test_generate_answer_twiml_with_greeting_text(self) -> None:
        """Test answer TwiML with TTS greeting."""
        response = TwilioAdapter.generate_answer_twiml(
            greeting_text="Hello and welcome!",
            language="en-US",
        )
        twiml = str(response)

        assert "<Say" in twiml
        assert "Hello and welcome!" in twiml
        assert 'language="en-US"' in twiml

    def test_generate_answer_twiml_with_spanish_language(self) -> None:
        """Test answer TwiML with Spanish TTS."""
        response = TwilioAdapter.generate_answer_twiml(
            greeting_text="Hola y bienvenido!",
            language="es-MX",
        )
        twiml = str(response)

        assert 'language="es-MX"' in twiml
        assert "Hola y bienvenido!" in twiml

    def test_generate_answer_twiml_default_greeting(self) -> None:
        """Test answer TwiML uses default greeting when none provided."""
        response = TwilioAdapter.generate_answer_twiml()
        twiml = str(response)

        assert "<Say" in twiml
        assert "thank you for calling" in twiml.lower()


class TestTwiMLGenerationPlayAudio:
    """Tests for TwiML generation - play_audio."""

    def test_generate_play_twiml_single_loop(self) -> None:
        """Test play TwiML with single loop."""
        response = TwilioAdapter.generate_play_twiml(
            audio_url="https://example.com/hold_music.mp3"
        )
        twiml = str(response)

        assert "<Play" in twiml
        assert "https://example.com/hold_music.mp3" in twiml
        assert 'loop="1"' in twiml

    def test_generate_play_twiml_multiple_loops(self) -> None:
        """Test play TwiML with multiple loops."""
        response = TwilioAdapter.generate_play_twiml(
            audio_url="https://example.com/hold_music.mp3",
            loop=5,
        )
        twiml = str(response)

        assert 'loop="5"' in twiml

    def test_generate_play_twiml_valid_xml(self) -> None:
        """Test that generated Play TwiML is valid XML."""
        response = TwilioAdapter.generate_play_twiml(
            audio_url="https://example.com/audio.mp3"
        )
        twiml = str(response)

        assert twiml.startswith("<?xml version")
        assert "</Response>" in twiml


class TestTwiMLGenerationTransferCall:
    """Tests for TwiML generation - transfer_call."""

    def test_generate_transfer_twiml_basic(self) -> None:
        """Test transfer TwiML with basic dial."""
        response = TwilioAdapter.generate_transfer_twiml(
            target_number="+15559999999"
        )
        twiml = str(response)

        assert "<Dial" in twiml
        assert "+15559999999" in twiml
        assert 'timeout="30"' in twiml  # Default timeout

    def test_generate_transfer_twiml_with_caller_id(self) -> None:
        """Test transfer TwiML with custom caller ID."""
        response = TwilioAdapter.generate_transfer_twiml(
            target_number="+15559999999",
            caller_id="+15551111111",
        )
        twiml = str(response)

        assert 'callerId="+15551111111"' in twiml

    def test_generate_transfer_twiml_with_custom_timeout(self) -> None:
        """Test transfer TwiML with custom timeout."""
        response = TwilioAdapter.generate_transfer_twiml(
            target_number="+15559999999",
            timeout=45,
        )
        twiml = str(response)

        assert 'timeout="45"' in twiml

    def test_generate_transfer_twiml_with_recording(self) -> None:
        """Test transfer TwiML with call recording enabled."""
        response = TwilioAdapter.generate_transfer_twiml(
            target_number="+15559999999",
            record=True,
        )
        twiml = str(response)

        assert 'record="record-from-answer-dual"' in twiml


class TestTwiMLGenerationRecord:
    """Tests for TwiML generation - record."""

    def test_generate_record_twiml_basic(self) -> None:
        """Test record TwiML with basic settings."""
        response = TwilioAdapter.generate_record_twiml(
            action_url="https://example.com/recording-callback"
        )
        twiml = str(response)

        assert "<Record" in twiml
        assert 'action="https://example.com/recording-callback"' in twiml
        assert 'maxLength="300"' in twiml  # Default max length
        assert 'playBeep="true"' in twiml  # Default play beep

    def test_generate_record_twiml_with_custom_length(self) -> None:
        """Test record TwiML with custom max length."""
        response = TwilioAdapter.generate_record_twiml(
            action_url="https://example.com/callback",
            max_length=60,
        )
        twiml = str(response)

        assert 'maxLength="60"' in twiml

    def test_generate_record_twiml_with_transcription(self) -> None:
        """Test record TwiML with transcription enabled."""
        response = TwilioAdapter.generate_record_twiml(
            action_url="https://example.com/callback",
            transcribe=True,
        )
        twiml = str(response)

        assert 'transcribe="true"' in twiml

    def test_generate_record_twiml_without_beep(self) -> None:
        """Test record TwiML without beep."""
        response = TwilioAdapter.generate_record_twiml(
            action_url="https://example.com/callback",
            play_beep=False,
        )
        twiml = str(response)

        assert 'playBeep="false"' in twiml


class TestTwiMLGenerationHangup:
    """Tests for TwiML generation - hangup."""

    def test_generate_hangup_twiml(self) -> None:
        """Test hangup TwiML generation."""
        response = TwilioAdapter.generate_hangup_twiml()
        twiml = str(response)

        assert "<Hangup" in twiml or "<Hangup/>" in twiml


class TestTwiMLGenerationBilingualGreeting:
    """Tests for TwiML generation - bilingual greeting."""

    def test_generate_bilingual_greeting_twiml(self) -> None:
        """Test bilingual greeting TwiML with both languages."""
        response = TwilioAdapter.generate_bilingual_greeting_twiml(
            english_text="Press 1 for English.",
            spanish_text="Presione 2 para espanol.",
            gather_action_url="https://example.com/language-select",
        )
        twiml = str(response)

        # Should have Gather verb
        assert "<Gather" in twiml
        assert 'numDigits="1"' in twiml
        assert 'action="https://example.com/language-select"' in twiml

        # Should have both languages
        assert "Press 1 for English." in twiml
        assert "Presione 2 para espanol." in twiml
        assert 'language="en-US"' in twiml
        assert 'language="es-MX"' in twiml

    def test_generate_bilingual_greeting_has_redirect_fallback(self) -> None:
        """Test bilingual greeting includes redirect for no input."""
        response = TwilioAdapter.generate_bilingual_greeting_twiml(
            english_text="Press 1",
            spanish_text="Presione 2",
            gather_action_url="https://example.com/select",
        )
        twiml = str(response)

        # Should have Redirect for default action
        assert "<Redirect>" in twiml
        assert "Digits=1" in twiml  # Default to English
