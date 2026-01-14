"""Tests for transcript service functionality.

Verifies transcript storage, JSON format, incremental updates,
large transcript handling, and cost tracking.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from vozbot.storage.db.models import (
    Base,
    Call,
    CallStatus,
    Language,
)
from vozbot.storage.services.transcript_service import (
    TranscriptData,
    TranscriptService,
    TranscriptTurn,
)


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
    """Enable foreign key support for SQLite."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
def engine() -> Engine:
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine: Engine) -> Session:
    """Create a test database session."""
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def sample_call(session: Session) -> Call:
    """Create a sample call for testing."""
    call = Call(
        id=str(uuid4()),
        from_number="+15551234567",
        language=Language.EN,
        status=CallStatus.INIT,
    )
    session.add(call)
    session.commit()
    session.refresh(call)
    return call


@pytest.fixture
def sample_call_with_transcript(session: Session) -> Call:
    """Create a sample call with an existing transcript."""
    transcript = TranscriptData(language="en")
    transcript.add_turn("agent", "Hello, how can I help you?", confidence=0.95)
    transcript.add_turn("caller", "I need insurance information.", confidence=0.92)

    call = Call(
        id=str(uuid4()),
        from_number="+15559876543",
        language=Language.EN,
        status=CallStatus.INTENT_DISCOVERY,
        transcript=transcript.to_json(),
    )
    session.add(call)
    session.commit()
    session.refresh(call)
    return call


# -----------------------------------------------------------------------------
# TranscriptTurn Tests
# -----------------------------------------------------------------------------


class TestTranscriptTurn:
    """Tests for TranscriptTurn class."""

    def test_create_turn_minimal(self) -> None:
        """Test creating a turn with minimal fields."""
        turn = TranscriptTurn(speaker="agent", text="Hello")

        assert turn.speaker == "agent"
        assert turn.text == "Hello"
        assert turn.timestamp is not None
        assert turn.confidence is None
        assert turn.duration_ms is None

    def test_create_turn_full(self) -> None:
        """Test creating a turn with all fields."""
        turn = TranscriptTurn(
            speaker="caller",
            text="I need help",
            timestamp="2026-01-14T12:00:00Z",
            confidence=0.95,
            duration_ms=2500,
        )

        assert turn.speaker == "caller"
        assert turn.text == "I need help"
        assert turn.timestamp == "2026-01-14T12:00:00Z"
        assert turn.confidence == 0.95
        assert turn.duration_ms == 2500

    def test_turn_to_dict(self) -> None:
        """Test turn serialization to dictionary."""
        turn = TranscriptTurn(
            speaker="agent",
            text="Welcome",
            timestamp="2026-01-14T12:00:00Z",
            confidence=0.98,
            duration_ms=1500,
        )

        data = turn.to_dict()

        assert data["speaker"] == "agent"
        assert data["text"] == "Welcome"
        assert data["timestamp"] == "2026-01-14T12:00:00Z"
        assert data["confidence"] == 0.98
        assert data["duration_ms"] == 1500

    def test_turn_to_dict_minimal(self) -> None:
        """Test turn serialization with minimal fields."""
        turn = TranscriptTurn(
            speaker="system",
            text="Call started",
            timestamp="2026-01-14T12:00:00Z",
        )

        data = turn.to_dict()

        assert "confidence" not in data
        assert "duration_ms" not in data

    def test_turn_from_dict(self) -> None:
        """Test turn deserialization from dictionary."""
        data = {
            "speaker": "caller",
            "text": "Thank you",
            "timestamp": "2026-01-14T12:05:00Z",
            "confidence": 0.91,
            "duration_ms": 1000,
        }

        turn = TranscriptTurn.from_dict(data)

        assert turn.speaker == "caller"
        assert turn.text == "Thank you"
        assert turn.timestamp == "2026-01-14T12:05:00Z"
        assert turn.confidence == 0.91
        assert turn.duration_ms == 1000


# -----------------------------------------------------------------------------
# TranscriptData Tests
# -----------------------------------------------------------------------------


class TestTranscriptData:
    """Tests for TranscriptData class."""

    def test_create_transcript_minimal(self) -> None:
        """Test creating empty transcript."""
        transcript = TranscriptData()

        assert transcript.version == "1.0"
        assert transcript.language is None
        assert transcript.started_at is not None
        assert transcript.turns == []
        assert len(transcript) == 0

    def test_create_transcript_with_language(self) -> None:
        """Test creating transcript with language."""
        transcript = TranscriptData(language="es")

        assert transcript.language == "es"

    def test_add_turn(self) -> None:
        """Test adding turns to transcript."""
        transcript = TranscriptData(language="en")

        turn1 = transcript.add_turn("agent", "Hello", confidence=0.95)
        turn2 = transcript.add_turn("caller", "Hi there", confidence=0.92)

        assert len(transcript) == 2
        assert transcript.turns[0].speaker == "agent"
        assert transcript.turns[1].speaker == "caller"
        assert turn1.text == "Hello"
        assert turn2.text == "Hi there"

    def test_metadata_updates(self) -> None:
        """Test that metadata updates correctly."""
        transcript = TranscriptData(language="en")

        transcript.add_turn("agent", "Hello", confidence=0.90, duration_ms=1000)
        transcript.add_turn("caller", "Hi", confidence=0.80, duration_ms=500)

        assert transcript.metadata["total_turns"] == 2
        assert transcript.metadata["total_duration_ms"] == 1500
        assert transcript.metadata["avg_confidence"] == 0.85

    def test_to_json(self) -> None:
        """Test JSON serialization."""
        transcript = TranscriptData(language="en")
        transcript.add_turn("agent", "Hello", confidence=0.95)

        json_str = transcript.to_json()
        data = json.loads(json_str)

        assert data["version"] == "1.0"
        assert data["language"] == "en"
        assert len(data["turns"]) == 1
        assert data["turns"][0]["speaker"] == "agent"
        assert data["turns"][0]["text"] == "Hello"

    def test_from_json(self) -> None:
        """Test JSON deserialization."""
        json_str = json.dumps({
            "version": "1.0",
            "language": "es",
            "started_at": "2026-01-14T12:00:00Z",
            "turns": [
                {"speaker": "agent", "text": "Hola", "timestamp": "2026-01-14T12:00:01Z"},
                {"speaker": "caller", "text": "Necesito ayuda", "timestamp": "2026-01-14T12:00:05Z"},
            ],
            "metadata": {"total_turns": 2},
        })

        transcript = TranscriptData.from_json(json_str)

        assert transcript.language == "es"
        assert len(transcript.turns) == 2
        assert transcript.turns[0].text == "Hola"
        assert transcript.turns[1].text == "Necesito ayuda"

    def test_get_full_text(self) -> None:
        """Test getting plain text transcript."""
        transcript = TranscriptData(language="en")
        transcript.add_turn("agent", "Hello, how can I help?")
        transcript.add_turn("caller", "I need insurance info.")
        transcript.add_turn("agent", "Sure, let me help you with that.")

        full_text = transcript.get_full_text()

        expected = (
            "Agent: Hello, how can I help?\n"
            "Caller: I need insurance info.\n"
            "Agent: Sure, let me help you with that."
        )
        assert full_text == expected

    def test_roundtrip_serialization(self) -> None:
        """Test that serialization and deserialization preserve data."""
        original = TranscriptData(language="en")
        original.add_turn("agent", "Welcome", confidence=0.98, duration_ms=2000)
        original.add_turn("caller", "Thanks", confidence=0.95, duration_ms=800)
        original.add_turn("agent", "How can I help?", confidence=0.97, duration_ms=1500)

        # Roundtrip
        json_str = original.to_json()
        restored = TranscriptData.from_json(json_str)

        assert restored.language == original.language
        assert len(restored.turns) == len(original.turns)
        for i in range(len(original.turns)):
            assert restored.turns[i].speaker == original.turns[i].speaker
            assert restored.turns[i].text == original.turns[i].text
            assert restored.turns[i].confidence == original.turns[i].confidence

    def test_unicode_text(self) -> None:
        """Test handling of unicode/Spanish text."""
        transcript = TranscriptData(language="es")
        transcript.add_turn("agent", "Hola, soy VozBot")
        transcript.add_turn("caller", "Necesito informacion sobre mi poliza")

        json_str = transcript.to_json()
        restored = TranscriptData.from_json(json_str)

        assert restored.turns[0].text == "Hola, soy VozBot"
        assert "poliza" in restored.turns[1].text


# -----------------------------------------------------------------------------
# TranscriptService Tests (Sync Session Wrapper)
# -----------------------------------------------------------------------------


class TestTranscriptFormat:
    """Tests for transcript JSON format compliance."""

    def test_transcript_stored_in_calls_transcript_column(
        self, session: Session, sample_call: Call
    ) -> None:
        """Test that transcript is stored in calls.transcript column."""
        transcript = TranscriptData(language="en")
        transcript.add_turn("agent", "Hello")

        sample_call.transcript = transcript.to_json()
        session.commit()
        session.refresh(sample_call)

        assert sample_call.transcript is not None
        assert "Hello" in sample_call.transcript

    def test_transcript_json_format_with_speaker_turns(
        self, session: Session, sample_call: Call
    ) -> None:
        """Test transcript format includes speaker turns and timestamps."""
        transcript = TranscriptData(language="en")
        transcript.add_turn("agent", "Welcome", confidence=0.95)
        transcript.add_turn("caller", "Hi", confidence=0.92)

        sample_call.transcript = transcript.to_json()
        session.commit()

        # Parse and verify format
        data = json.loads(sample_call.transcript)

        assert "turns" in data
        assert len(data["turns"]) == 2
        assert data["turns"][0]["speaker"] == "agent"
        assert data["turns"][0]["text"] == "Welcome"
        assert "timestamp" in data["turns"][0]
        assert data["turns"][1]["speaker"] == "caller"

    def test_language_stored_in_calls_language_column(
        self, session: Session, sample_call: Call
    ) -> None:
        """Test that language is stored in calls.language column."""
        sample_call.language = Language.ES
        session.commit()
        session.refresh(sample_call)

        assert sample_call.language == Language.ES
        assert sample_call.language.value == "es"

    def test_large_transcript_handling(self, session: Session, sample_call: Call) -> None:
        """Test handling of large transcripts (>10k chars)."""
        transcript = TranscriptData(language="en")

        # Add many turns to create a large transcript
        for i in range(200):
            text = f"This is turn number {i} with some additional text to increase size. " * 5
            transcript.add_turn(
                speaker="agent" if i % 2 == 0 else "caller",
                text=text,
                confidence=0.95,
            )

        json_str = transcript.to_json()

        # Verify it's large enough
        assert len(json_str) > 10000, f"Transcript should be >10k chars, got {len(json_str)}"

        # Verify it can be stored
        sample_call.transcript = json_str
        session.commit()
        session.refresh(sample_call)

        assert sample_call.transcript == json_str

        # Verify it can be parsed back
        restored = TranscriptData.from_json(sample_call.transcript)
        assert len(restored.turns) == 200

    def test_query_transcript_by_call_id(
        self, session: Session, sample_call_with_transcript: Call
    ) -> None:
        """Test querying transcript by call_id."""
        call_id = sample_call_with_transcript.id

        # Query the call
        call = session.get(Call, call_id)

        assert call is not None
        assert call.transcript is not None

        # Parse transcript
        transcript = TranscriptData.from_json(call.transcript)

        assert len(transcript.turns) == 2
        assert transcript.turns[0].speaker == "agent"

    def test_storage_cost_tracked_in_calls_costs(
        self, session: Session, sample_call: Call
    ) -> None:
        """Test that storage cost is tracked in calls.costs."""
        transcript = TranscriptData(language="en")
        transcript.add_turn("agent", "Hello")
        transcript.add_turn("caller", "Hi")

        json_str = transcript.to_json()
        sample_call.transcript = json_str

        # Track storage cost
        storage_bytes = len(json_str)
        sample_call.costs = {
            "storage_bytes": storage_bytes,
            "storage_cost_usd": storage_bytes * 0.023 / (1024 * 1024 * 1024),
        }

        session.commit()
        session.refresh(sample_call)

        assert sample_call.costs is not None
        assert "storage_bytes" in sample_call.costs
        assert sample_call.costs["storage_bytes"] == storage_bytes


class TestIncrementalTranscriptUpdate:
    """Tests for incremental transcript updates during calls."""

    def test_incremental_turn_addition(
        self, session: Session, sample_call: Call
    ) -> None:
        """Test adding turns incrementally (after each turn)."""
        # Start with empty transcript
        transcript = TranscriptData(language="en")
        sample_call.transcript = transcript.to_json()
        session.commit()

        # Add first turn
        transcript.add_turn("agent", "Hello, this is VozBot.")
        sample_call.transcript = transcript.to_json()
        session.commit()
        session.refresh(sample_call)

        # Verify first turn saved
        restored = TranscriptData.from_json(sample_call.transcript)
        assert len(restored.turns) == 1

        # Add second turn
        restored.add_turn("caller", "I need help with my policy.")
        sample_call.transcript = restored.to_json()
        session.commit()
        session.refresh(sample_call)

        # Verify both turns saved
        final = TranscriptData.from_json(sample_call.transcript)
        assert len(final.turns) == 2
        assert final.turns[0].text == "Hello, this is VozBot."
        assert final.turns[1].text == "I need help with my policy."

    def test_final_transcript_saved_on_call_end(
        self, session: Session, sample_call: Call
    ) -> None:
        """Test that final complete transcript is saved when call ends."""
        transcript = TranscriptData(language="en")
        transcript.add_turn("agent", "Hello")
        transcript.add_turn("caller", "Hi")
        transcript.add_turn("agent", "How can I help?")
        transcript.add_turn("caller", "I need insurance.")
        transcript.add_turn("agent", "Goodbye")

        # Save final transcript
        sample_call.transcript = transcript.to_json()
        sample_call.status = CallStatus.COMPLETED
        session.commit()
        session.refresh(sample_call)

        # Verify complete transcript saved
        restored = TranscriptData.from_json(sample_call.transcript)
        assert len(restored.turns) == 5
        assert sample_call.status == CallStatus.COMPLETED


class TestTranscriptServiceCoverage:
    """Additional tests for transcript service coverage."""

    def test_transcript_with_all_speaker_types(
        self, session: Session, sample_call: Call
    ) -> None:
        """Test transcript with agent, caller, and system speakers."""
        transcript = TranscriptData(language="en")
        transcript.add_turn("system", "Call started")
        transcript.add_turn("agent", "Hello")
        transcript.add_turn("caller", "Hi")
        transcript.add_turn("system", "Language selected: English")
        transcript.add_turn("agent", "How can I help?")

        sample_call.transcript = transcript.to_json()
        session.commit()

        restored = TranscriptData.from_json(sample_call.transcript)

        speakers = [t.speaker for t in restored.turns]
        assert "system" in speakers
        assert "agent" in speakers
        assert "caller" in speakers

    def test_transcript_metadata_accuracy(self) -> None:
        """Test that transcript metadata is accurate."""
        transcript = TranscriptData(language="en")
        transcript.add_turn("agent", "Hello", confidence=0.90, duration_ms=1000)
        transcript.add_turn("caller", "Hi", confidence=0.80, duration_ms=500)
        transcript.add_turn("agent", "Help?", confidence=0.85, duration_ms=750)

        # Average confidence: (0.90 + 0.80 + 0.85) / 3 = 0.85
        # Total duration: 1000 + 500 + 750 = 2250

        assert transcript.metadata["total_turns"] == 3
        assert transcript.metadata["total_duration_ms"] == 2250
        assert transcript.metadata["avg_confidence"] == 0.85

    def test_empty_transcript_metadata(self) -> None:
        """Test metadata for empty transcript."""
        transcript = TranscriptData()

        # Force metadata update
        transcript._update_metadata()

        assert transcript.metadata["total_turns"] == 0
        assert transcript.metadata["total_duration_ms"] == 0
        assert transcript.metadata["avg_confidence"] == 0.0

    def test_transcript_version(self) -> None:
        """Test transcript version is included."""
        transcript = TranscriptData()

        data = transcript.to_dict()

        assert data["version"] == "1.0"

    def test_from_dict_handles_missing_fields(self) -> None:
        """Test from_dict handles missing optional fields gracefully."""
        data = {
            "turns": [
                {"speaker": "agent", "text": "Hello"},
            ],
        }

        transcript = TranscriptData.from_dict(data)

        assert transcript.version == "1.0"
        assert transcript.language is None
        assert len(transcript.turns) == 1
