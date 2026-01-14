"""Tests for the TelephonyAdapter abstract base class."""

import asyncio
from datetime import datetime

import pytest

from vozbot.telephony.adapters.base import CallInfo, CallStatus, TelephonyAdapter


class TestCallInfo:
    """Tests for the CallInfo dataclass."""

    def test_create_call_info(self) -> None:
        """Test creating a CallInfo instance with all fields."""
        started = datetime(2024, 1, 15, 10, 30, 0)
        info = CallInfo(
            call_id="call_123",
            from_number="+15551234567",
            to_number="+15559876543",
            status=CallStatus.IN_PROGRESS,
            started_at=started,
        )

        assert info.call_id == "call_123"
        assert info.from_number == "+15551234567"
        assert info.to_number == "+15559876543"
        assert info.status == CallStatus.IN_PROGRESS
        assert info.started_at == started

    def test_call_info_equality(self) -> None:
        """Test that two CallInfo instances with same values are equal."""
        started = datetime(2024, 1, 15, 10, 30, 0)
        info1 = CallInfo(
            call_id="call_123",
            from_number="+15551234567",
            to_number="+15559876543",
            status=CallStatus.RINGING,
            started_at=started,
        )
        info2 = CallInfo(
            call_id="call_123",
            from_number="+15551234567",
            to_number="+15559876543",
            status=CallStatus.RINGING,
            started_at=started,
        )

        assert info1 == info2


class TestCallStatus:
    """Tests for the CallStatus enum."""

    def test_all_status_values_exist(self) -> None:
        """Verify all expected call status values are defined."""
        expected_statuses = [
            "queued",
            "ringing",
            "in_progress",
            "completed",
            "busy",
            "failed",
            "no_answer",
            "canceled",
        ]

        for status_value in expected_statuses:
            assert CallStatus(status_value) is not None

    def test_status_value_access(self) -> None:
        """Test accessing enum values."""
        assert CallStatus.IN_PROGRESS.value == "in_progress"
        assert CallStatus.COMPLETED.value == "completed"


class TestTelephonyAdapterABC:
    """Tests for the TelephonyAdapter abstract base class."""

    def test_cannot_instantiate_directly(self) -> None:
        """Verify that TelephonyAdapter cannot be instantiated directly."""
        with pytest.raises(TypeError) as exc_info:
            TelephonyAdapter()  # type: ignore[abstract]

        # Check that the error mentions abstract methods
        error_message = str(exc_info.value)
        assert "abstract" in error_message.lower() or "instantiate" in error_message.lower()

    def test_subclass_must_implement_all_methods(self) -> None:
        """Verify that a subclass missing methods cannot be instantiated."""

        class IncompleteAdapter(TelephonyAdapter):
            """Incomplete implementation missing required methods."""

            async def answer_call(self, call_id: str) -> None:
                pass

            # Missing: hangup_call, transfer_call, play_audio, get_call_info

        with pytest.raises(TypeError) as exc_info:
            IncompleteAdapter()  # type: ignore[abstract]

        error_message = str(exc_info.value)
        assert "abstract" in error_message.lower()

    def test_complete_subclass_can_be_instantiated(self) -> None:
        """Verify that a complete implementation can be instantiated."""

        class CompleteAdapter(TelephonyAdapter):
            """Complete implementation of all required methods."""

            async def answer_call(self, call_id: str) -> None:
                pass

            async def hangup_call(self, call_id: str) -> None:
                pass

            async def transfer_call(self, call_id: str, target_number: str) -> bool:
                return True

            async def play_audio(self, call_id: str, audio_url: str) -> None:
                pass

            async def get_call_info(self, call_id: str) -> CallInfo:
                return CallInfo(
                    call_id=call_id,
                    from_number="+15551234567",
                    to_number="+15559876543",
                    status=CallStatus.IN_PROGRESS,
                    started_at=datetime.now(),
                )

        # Should not raise
        adapter = CompleteAdapter()
        assert isinstance(adapter, TelephonyAdapter)


class MockAdapter(TelephonyAdapter):
    """Mock implementation for testing async methods."""

    def __init__(self) -> None:
        self.calls_answered: list[str] = []
        self.calls_hungup: list[str] = []
        self.transfers: list[tuple[str, str]] = []
        self.audio_played: list[tuple[str, str]] = []

    async def answer_call(self, call_id: str) -> None:
        self.calls_answered.append(call_id)

    async def hangup_call(self, call_id: str) -> None:
        self.calls_hungup.append(call_id)

    async def transfer_call(self, call_id: str, target_number: str) -> bool:
        self.transfers.append((call_id, target_number))
        return True

    async def play_audio(self, call_id: str, audio_url: str) -> None:
        self.audio_played.append((call_id, audio_url))

    async def get_call_info(self, call_id: str) -> CallInfo:
        return CallInfo(
            call_id=call_id,
            from_number="+15551234567",
            to_number="+15559876543",
            status=CallStatus.IN_PROGRESS,
            started_at=datetime.now(),
        )


class TestTelephonyAdapterMethods:
    """Tests for TelephonyAdapter method signatures and behavior."""

    @pytest.fixture
    def mock_adapter(self) -> MockAdapter:
        """Create a mock adapter for testing method signatures."""
        return MockAdapter()

    def test_answer_call(self, mock_adapter: MockAdapter) -> None:
        """Test answer_call method signature and basic behavior."""
        result = asyncio.run(mock_adapter.answer_call("call_123"))
        assert result is None
        assert "call_123" in mock_adapter.calls_answered

    def test_hangup_call(self, mock_adapter: MockAdapter) -> None:
        """Test hangup_call method signature and basic behavior."""
        result = asyncio.run(mock_adapter.hangup_call("call_123"))
        assert result is None
        assert "call_123" in mock_adapter.calls_hungup

    def test_transfer_call(self, mock_adapter: MockAdapter) -> None:
        """Test transfer_call method returns bool."""
        result = asyncio.run(mock_adapter.transfer_call("call_123", "+15559999999"))
        assert isinstance(result, bool)
        assert result is True
        assert ("call_123", "+15559999999") in mock_adapter.transfers

    def test_play_audio(self, mock_adapter: MockAdapter) -> None:
        """Test play_audio method signature and basic behavior."""
        result = asyncio.run(
            mock_adapter.play_audio("call_123", "https://example.com/audio.mp3")
        )
        assert result is None
        assert ("call_123", "https://example.com/audio.mp3") in mock_adapter.audio_played

    def test_get_call_info(self, mock_adapter: MockAdapter) -> None:
        """Test get_call_info returns CallInfo."""
        result = asyncio.run(mock_adapter.get_call_info("call_123"))

        assert isinstance(result, CallInfo)
        assert result.call_id == "call_123"
        assert isinstance(result.status, CallStatus)
        assert isinstance(result.started_at, datetime)
