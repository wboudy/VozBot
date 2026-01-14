"""Transcript service - business logic for call transcript operations.

Provides methods for storing, updating, and querying call transcripts
with structured JSON format including speaker turns and timestamps.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from vozbot.storage.db.models import Call, Language

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class TranscriptTurn:
    """Represents a single turn in a conversation transcript.

    A turn is a single utterance by a speaker in the conversation.

    Attributes:
        speaker: Identifier for the speaker ("agent", "caller", "system").
        text: The transcribed text of this turn.
        timestamp: ISO format timestamp when this turn occurred.
        confidence: STT confidence score for this turn (0.0-1.0).
        duration_ms: Duration of the audio for this turn in milliseconds.
    """

    def __init__(
        self,
        speaker: str,
        text: str,
        timestamp: str | None = None,
        confidence: float | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Initialize a transcript turn.

        Args:
            speaker: Speaker identifier ("agent", "caller", "system").
            text: Transcribed text content.
            timestamp: ISO format timestamp. Defaults to current time.
            confidence: STT confidence score.
            duration_ms: Audio duration in milliseconds.
        """
        self.speaker = speaker
        self.text = text
        self.timestamp = timestamp or datetime.now(UTC).isoformat().replace("+00:00", "Z")
        self.confidence = confidence
        self.duration_ms = duration_ms

    def to_dict(self) -> dict[str, Any]:
        """Convert turn to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the turn.
        """
        data: dict[str, Any] = {
            "speaker": self.speaker,
            "text": self.text,
            "timestamp": self.timestamp,
        }
        if self.confidence is not None:
            data["confidence"] = self.confidence
        if self.duration_ms is not None:
            data["duration_ms"] = self.duration_ms
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TranscriptTurn:
        """Create a TranscriptTurn from a dictionary.

        Args:
            data: Dictionary with turn data.

        Returns:
            TranscriptTurn instance.
        """
        return cls(
            speaker=data["speaker"],
            text=data["text"],
            timestamp=data.get("timestamp"),
            confidence=data.get("confidence"),
            duration_ms=data.get("duration_ms"),
        )


class TranscriptData:
    """Structured transcript data with speaker turns and metadata.

    The transcript format is:
    {
        "version": "1.0",
        "language": "en",
        "started_at": "2026-01-14T12:00:00Z",
        "turns": [
            {
                "speaker": "agent",
                "text": "Hello, how can I help you?",
                "timestamp": "2026-01-14T12:00:01Z",
                "confidence": 0.95,
                "duration_ms": 2500
            },
            ...
        ],
        "metadata": {
            "total_turns": 10,
            "total_duration_ms": 180000,
            "avg_confidence": 0.92
        }
    }

    Attributes:
        version: Schema version for the transcript format.
        language: Language code of the conversation.
        started_at: ISO timestamp when the conversation started.
        turns: List of TranscriptTurn objects.
        metadata: Additional metadata about the transcript.
    """

    VERSION = "1.0"

    def __init__(
        self,
        language: str | None = None,
        started_at: str | None = None,
    ) -> None:
        """Initialize transcript data.

        Args:
            language: Language code ("en" or "es").
            started_at: ISO timestamp for conversation start.
        """
        self.version = self.VERSION
        self.language = language
        self.started_at = started_at or datetime.now(UTC).isoformat().replace("+00:00", "Z")
        self.turns: list[TranscriptTurn] = []
        self.metadata: dict[str, Any] = {}

    def add_turn(
        self,
        speaker: str,
        text: str,
        confidence: float | None = None,
        duration_ms: int | None = None,
    ) -> TranscriptTurn:
        """Add a new turn to the transcript.

        Args:
            speaker: Speaker identifier ("agent", "caller", "system").
            text: Transcribed text.
            confidence: STT confidence score.
            duration_ms: Audio duration in milliseconds.

        Returns:
            The created TranscriptTurn.
        """
        turn = TranscriptTurn(
            speaker=speaker,
            text=text,
            confidence=confidence,
            duration_ms=duration_ms,
        )
        self.turns.append(turn)
        self._update_metadata()
        return turn

    def _update_metadata(self) -> None:
        """Update metadata based on current turns."""
        if not self.turns:
            self.metadata = {
                "total_turns": 0,
                "total_duration_ms": 0,
                "avg_confidence": 0.0,
            }
            return

        total_duration = sum(
            t.duration_ms for t in self.turns if t.duration_ms is not None
        )
        confidences = [t.confidence for t in self.turns if t.confidence is not None]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        self.metadata = {
            "total_turns": len(self.turns),
            "total_duration_ms": total_duration,
            "avg_confidence": round(avg_conf, 4),
        }

    def to_json(self) -> str:
        """Serialize transcript to JSON string.

        Returns:
            JSON string representation.
        """
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation.
        """
        return {
            "version": self.version,
            "language": self.language,
            "started_at": self.started_at,
            "turns": [t.to_dict() for t in self.turns],
            "metadata": self.metadata,
        }

    @classmethod
    def from_json(cls, json_str: str) -> TranscriptData:
        """Parse transcript from JSON string.

        Args:
            json_str: JSON string representation.

        Returns:
            TranscriptData instance.
        """
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TranscriptData:
        """Create TranscriptData from dictionary.

        Args:
            data: Dictionary with transcript data.

        Returns:
            TranscriptData instance.
        """
        transcript = cls(
            language=data.get("language"),
            started_at=data.get("started_at"),
        )
        transcript.version = data.get("version", cls.VERSION)
        transcript.turns = [
            TranscriptTurn.from_dict(t) for t in data.get("turns", [])
        ]
        transcript.metadata = data.get("metadata", {})
        return transcript

    def get_full_text(self) -> str:
        """Get full transcript as plain text.

        Returns:
            Plain text transcript with speaker labels.
        """
        lines = []
        for turn in self.turns:
            lines.append(f"{turn.speaker.capitalize()}: {turn.text}")
        return "\n".join(lines)

    def __len__(self) -> int:
        """Return number of turns in transcript."""
        return len(self.turns)


class TranscriptService:
    """Service for managing call transcripts in the database.

    Handles storage and retrieval of structured transcript data
    with support for incremental updates during active calls.
    """

    # Maximum transcript size to store (characters)
    MAX_TRANSCRIPT_SIZE = 100_000  # ~100KB, handles >10k chars requirement

    def __init__(self, session: AsyncSession) -> None:
        """Initialize transcript service.

        Args:
            session: Async SQLAlchemy session.
        """
        self.session = session

    async def get_transcript(self, call_id: str) -> TranscriptData | None:
        """Get transcript for a call.

        Args:
            call_id: Call ID to get transcript for.

        Returns:
            TranscriptData if found, None otherwise.
        """
        result = await self.session.execute(
            select(Call).where(Call.id == call_id)
        )
        call = result.scalar_one_or_none()

        if call is None or call.transcript is None:
            return None

        try:
            return TranscriptData.from_json(call.transcript)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(
                "Failed to parse transcript JSON",
                extra={"call_id": call_id, "error": str(e)},
            )
            return None

    async def initialize_transcript(
        self,
        call_id: str,
        language: str | None = None,
    ) -> TranscriptData | None:
        """Initialize a new transcript for a call.

        Args:
            call_id: Call ID to initialize transcript for.
            language: Language code ("en" or "es").

        Returns:
            Created TranscriptData if successful, None otherwise.
        """
        result = await self.session.execute(
            select(Call).where(Call.id == call_id)
        )
        call = result.scalar_one_or_none()

        if call is None:
            logger.warning(
                "Call not found for transcript initialization",
                extra={"call_id": call_id},
            )
            return None

        # Get language from call if not provided
        if language is None and call.language is not None:
            language = call.language.value

        transcript = TranscriptData(language=language)
        call.transcript = transcript.to_json()
        call.updated_at = datetime.now(UTC)
        await self.session.flush()

        logger.info(
            "Initialized transcript",
            extra={"call_id": call_id, "language": language},
        )

        return transcript

    async def add_turn(
        self,
        call_id: str,
        speaker: str,
        text: str,
        confidence: float | None = None,
        duration_ms: int | None = None,
    ) -> TranscriptData | None:
        """Add a turn to a call's transcript (incremental update).

        If no transcript exists, one will be created.

        Args:
            call_id: Call ID to add turn to.
            speaker: Speaker identifier ("agent", "caller", "system").
            text: Transcribed text.
            confidence: STT confidence score.
            duration_ms: Audio duration in milliseconds.

        Returns:
            Updated TranscriptData if successful, None otherwise.
        """
        result = await self.session.execute(
            select(Call).where(Call.id == call_id)
        )
        call = result.scalar_one_or_none()

        if call is None:
            logger.warning(
                "Call not found for transcript update",
                extra={"call_id": call_id},
            )
            return None

        # Get or create transcript
        if call.transcript:
            try:
                transcript = TranscriptData.from_json(call.transcript)
            except (json.JSONDecodeError, KeyError):
                # Invalid JSON, create new transcript
                language = call.language.value if call.language else None
                transcript = TranscriptData(language=language)
        else:
            language = call.language.value if call.language else None
            transcript = TranscriptData(language=language)

        # Add the turn
        transcript.add_turn(
            speaker=speaker,
            text=text,
            confidence=confidence,
            duration_ms=duration_ms,
        )

        # Check size limit
        json_str = transcript.to_json()
        if len(json_str) > self.MAX_TRANSCRIPT_SIZE:
            logger.warning(
                "Transcript exceeds size limit",
                extra={
                    "call_id": call_id,
                    "size": len(json_str),
                    "max_size": self.MAX_TRANSCRIPT_SIZE,
                },
            )
            # Still save but truncate old turns if needed
            while len(json_str) > self.MAX_TRANSCRIPT_SIZE and len(transcript.turns) > 1:
                transcript.turns.pop(0)
                json_str = transcript.to_json()

        call.transcript = json_str
        call.updated_at = datetime.now(UTC)
        await self.session.flush()

        logger.debug(
            "Added transcript turn",
            extra={
                "call_id": call_id,
                "speaker": speaker,
                "turn_count": len(transcript.turns),
            },
        )

        return transcript

    async def save_final_transcript(
        self,
        call_id: str,
        transcript: TranscriptData,
    ) -> bool:
        """Save final transcript at call end.

        Args:
            call_id: Call ID to save transcript for.
            transcript: Complete transcript data.

        Returns:
            True if saved successfully, False otherwise.
        """
        result = await self.session.execute(
            select(Call).where(Call.id == call_id)
        )
        call = result.scalar_one_or_none()

        if call is None:
            logger.warning(
                "Call not found for final transcript save",
                extra={"call_id": call_id},
            )
            return False

        call.transcript = transcript.to_json()
        call.updated_at = datetime.now(UTC)
        await self.session.flush()

        logger.info(
            "Saved final transcript",
            extra={
                "call_id": call_id,
                "turns": len(transcript.turns),
                "size": len(call.transcript),
            },
        )

        return True

    async def update_language(
        self,
        call_id: str,
        language: str,
    ) -> bool:
        """Update the language in both the call and its transcript.

        Args:
            call_id: Call ID to update.
            language: Language code ("en" or "es").

        Returns:
            True if updated successfully, False otherwise.
        """
        result = await self.session.execute(
            select(Call).where(Call.id == call_id)
        )
        call = result.scalar_one_or_none()

        if call is None:
            return False

        # Update call language
        if language == "en":
            call.language = Language.EN
        elif language == "es":
            call.language = Language.ES

        # Update transcript language if exists
        if call.transcript:
            try:
                transcript = TranscriptData.from_json(call.transcript)
                transcript.language = language
                call.transcript = transcript.to_json()
            except (json.JSONDecodeError, KeyError):
                pass

        call.updated_at = datetime.now(UTC)
        await self.session.flush()

        logger.info(
            "Updated call and transcript language",
            extra={"call_id": call_id, "language": language},
        )

        return True

    async def track_storage_cost(
        self,
        call_id: str,
        storage_bytes: int | None = None,
    ) -> bool:
        """Track storage cost for the transcript in the call's costs.

        Args:
            call_id: Call ID to update.
            storage_bytes: Override storage size (defaults to transcript size).

        Returns:
            True if updated successfully, False otherwise.
        """
        result = await self.session.execute(
            select(Call).where(Call.id == call_id)
        )
        call = result.scalar_one_or_none()

        if call is None:
            return False

        # Calculate storage bytes from transcript if not provided
        if storage_bytes is None:
            storage_bytes = len(call.transcript) if call.transcript else 0

        # Update costs
        if call.costs is None:
            call.costs = {}

        call.costs["storage_bytes"] = storage_bytes

        # Simple cost estimation (e.g., $0.023 per GB for S3-like storage)
        # Using Decimal for precision, but storing as float for JSON compatibility
        cost_per_byte = Decimal("0.023") / Decimal("1073741824")  # $0.023/GB
        storage_cost = float(Decimal(storage_bytes) * cost_per_byte)
        call.costs["storage_cost_usd"] = round(storage_cost, 10)

        call.updated_at = datetime.now(UTC)
        await self.session.flush()

        logger.info(
            "Updated storage cost",
            extra={
                "call_id": call_id,
                "storage_bytes": storage_bytes,
                "storage_cost_usd": call.costs["storage_cost_usd"],
            },
        )

        return True


async def get_transcript_by_call_id(
    session: AsyncSession,
    call_id: str,
) -> TranscriptData | None:
    """Get transcript for a call (convenience function).

    Args:
        session: Database session.
        call_id: Call ID to get transcript for.

    Returns:
        TranscriptData if found, None otherwise.
    """
    try:
        service = TranscriptService(session)
        return await service.get_transcript(call_id)
    except SQLAlchemyError as e:
        logger.error(
            "Failed to get transcript",
            extra={"call_id": call_id, "error": str(e)},
        )
        return None


async def add_transcript_turn_safe(
    session: AsyncSession,
    call_id: str,
    speaker: str,
    text: str,
    confidence: float | None = None,
    duration_ms: int | None = None,
) -> bool:
    """Add a transcript turn with error handling.

    Args:
        session: Database session.
        call_id: Call ID to add turn to.
        speaker: Speaker identifier.
        text: Transcribed text.
        confidence: STT confidence score.
        duration_ms: Audio duration in milliseconds.

    Returns:
        True if successful, False otherwise.
    """
    try:
        service = TranscriptService(session)
        result = await service.add_turn(
            call_id=call_id,
            speaker=speaker,
            text=text,
            confidence=confidence,
            duration_ms=duration_ms,
        )
        return result is not None
    except SQLAlchemyError as e:
        logger.error(
            "Failed to add transcript turn",
            extra={
                "call_id": call_id,
                "speaker": speaker,
                "error": str(e),
            },
        )
        return False
