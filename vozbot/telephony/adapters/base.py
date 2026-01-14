"""Base telephony adapter interface.

This module defines the abstract base class for telephony providers,
enabling pluggable implementations for different telephony services
(e.g., Twilio, Vonage, SignalWire).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class CallStatus(Enum):
    """Enumeration of possible call states."""

    QUEUED = "queued"
    RINGING = "ringing"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BUSY = "busy"
    FAILED = "failed"
    NO_ANSWER = "no_answer"
    CANCELED = "canceled"


@dataclass
class CallInfo:
    """Information about a telephone call.

    Attributes:
        call_id: Unique identifier for the call from the telephony provider.
        from_number: The phone number that initiated the call (E.164 format).
        to_number: The phone number that received the call (E.164 format).
        status: Current status of the call.
        started_at: Timestamp when the call was initiated.
    """

    call_id: str
    from_number: str
    to_number: str
    status: CallStatus
    started_at: datetime


class TelephonyAdapter(ABC):
    """Abstract base class for telephony provider adapters.

    This interface defines the contract that all telephony provider
    implementations must follow. Implementations should handle
    provider-specific API calls and error handling.

    All methods are async to support non-blocking I/O operations
    with telephony APIs.

    Example:
        ```python
        class TwilioAdapter(TelephonyAdapter):
            async def answer_call(self, call_id: str) -> None:
                # Twilio-specific implementation
                ...
        ```
    """

    @abstractmethod
    async def answer_call(self, call_id: str) -> None:
        """Answer an incoming call.

        Args:
            call_id: The unique identifier for the call to answer.

        Raises:
            TelephonyError: If the call cannot be answered.
        """
        ...

    @abstractmethod
    async def hangup_call(self, call_id: str) -> None:
        """Terminate an active call.

        Args:
            call_id: The unique identifier for the call to hang up.

        Raises:
            TelephonyError: If the call cannot be terminated.
        """
        ...

    @abstractmethod
    async def transfer_call(self, call_id: str, target_number: str) -> bool:
        """Transfer an active call to another phone number.

        Args:
            call_id: The unique identifier for the call to transfer.
            target_number: The destination phone number (E.164 format).

        Returns:
            True if the transfer was initiated successfully, False otherwise.

        Raises:
            TelephonyError: If the transfer fails due to an error.
        """
        ...

    @abstractmethod
    async def play_audio(self, call_id: str, audio_url: str) -> None:
        """Play an audio file to the caller.

        Args:
            call_id: The unique identifier for the call.
            audio_url: URL of the audio file to play (must be publicly accessible).

        Raises:
            TelephonyError: If the audio cannot be played.
        """
        ...

    @abstractmethod
    async def get_call_info(self, call_id: str) -> CallInfo:
        """Retrieve information about a call.

        Args:
            call_id: The unique identifier for the call.

        Returns:
            CallInfo object containing details about the call.

        Raises:
            TelephonyError: If call information cannot be retrieved.
        """
        ...
