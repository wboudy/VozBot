"""Tests for the VozBot Dashboard Search functionality.

Verifies search returns expected results across different search types:
- Phone number partial matching
- Name fuzzy matching
- Full-text search on transcript/summary
- Result highlighting
- Pagination
- SQL injection prevention
"""

from __future__ import annotations

import time
from collections.abc import Generator
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from vozbot.storage.db.models import (
    Base,
    Call,
    CallbackTask,
    CallStatus,
    CustomerType,
    Language,
    TaskPriority,
    TaskStatus,
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
def session(engine: Engine) -> Generator[Session, None, None]:
    """Create a test database session."""
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def sample_data(session: Session) -> list[CallbackTask]:
    """Create sample data for search testing."""
    tasks = []

    # Data set with various searchable content
    test_cases = [
        {
            "from_number": "+15551234567",
            "callback_number": "+15559876543",
            "name": "John Smith",
            "transcript": "Hello, I need help with my auto insurance policy.",
            "summary": "Customer requesting auto insurance help.",
            "intent": "auto insurance inquiry",
            "notes": "Prefers morning callback",
            "priority": TaskPriority.HIGH,
            "status": TaskStatus.PENDING,
            "language": Language.EN,
        },
        {
            "from_number": "+15552223333",
            "callback_number": "+15554445555",
            "name": "Maria Garcia",
            "transcript": "Hola, necesito informacion sobre seguro de hogar.",
            "summary": "Spanish-speaking customer needs home insurance info.",
            "intent": "home insurance question",
            "notes": "Spanish preferred, afternoon callback",
            "priority": TaskPriority.URGENT,
            "status": TaskStatus.PENDING,
            "language": Language.ES,
        },
        {
            "from_number": "+15556667777",
            "callback_number": "+15558889999",
            "name": "Robert Johnson",
            "transcript": "I want to add a new driver to my policy. My son just got his license.",
            "summary": "Adding new driver to existing auto policy.",
            "intent": "policy modification",
            "notes": "Son's name is Michael, age 16",
            "priority": TaskPriority.NORMAL,
            "status": TaskStatus.IN_PROGRESS,
            "language": Language.EN,
        },
        {
            "from_number": "+15551112222",
            "callback_number": "+15553334444",
            "name": "Jane Doe",
            "transcript": "I had an accident yesterday and need to file a claim.",
            "summary": "Accident claim filing needed.",
            "intent": "accident claim",
            "notes": "Accident was minor fender bender",
            "priority": TaskPriority.URGENT,
            "status": TaskStatus.PENDING,
            "language": Language.EN,
        },
        {
            "from_number": "+15557778888",
            "callback_number": "+15550001111",
            "name": "Carlos Rodriguez",
            "transcript": "Can you help me understand my coverage options?",
            "summary": "Coverage options explanation requested.",
            "intent": "coverage inquiry",
            "notes": None,
            "priority": TaskPriority.LOW,
            "status": TaskStatus.COMPLETED,
            "language": Language.EN,
        },
    ]

    for data in test_cases:
        call = Call(
            id=str(uuid4()),
            from_number=data["from_number"],
            language=data["language"],
            customer_type=CustomerType.EXISTING,
            intent=data["intent"],
            status=CallStatus.COMPLETED,
            summary=data["summary"],
            transcript=data["transcript"],
        )
        session.add(call)
        session.commit()
        session.refresh(call)

        task = CallbackTask(
            id=str(uuid4()),
            call_id=call.id,
            priority=data["priority"],
            name=data["name"],
            callback_number=data["callback_number"],
            notes=data["notes"],
            status=data["status"],
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        tasks.append(task)

    return tasks


@pytest.fixture
def large_data_set(session: Session) -> list[CallbackTask]:
    """Create a larger data set for performance testing (100 records)."""
    tasks = []

    # Create 100 records for performance testing
    for i in range(100):
        call = Call(
            id=str(uuid4()),
            from_number=f"+1555{i:07d}",
            language=Language.EN if i % 2 == 0 else Language.ES,
            customer_type=CustomerType.EXISTING,
            intent=f"Test intent {i}",
            status=CallStatus.COMPLETED,
            summary=f"This is summary number {i} for testing search performance.",
            transcript=f"Transcript {i}: Customer called about various insurance topics including auto, home, and life insurance. The conversation covered policy details and pricing.",
        )
        session.add(call)
        session.commit()

        task = CallbackTask(
            id=str(uuid4()),
            call_id=call.id,
            priority=TaskPriority.NORMAL,
            name=f"Test User {i}",
            callback_number=f"+1666{i:07d}",
            notes=f"Note {i}: This is a test note for performance validation.",
            status=TaskStatus.PENDING,
        )
        session.add(task)
        session.commit()
        tasks.append(task)

    return tasks


# -----------------------------------------------------------------------------
# Highlighting Tests
# -----------------------------------------------------------------------------


class TestHighlighting:
    """Tests for text highlighting functions."""

    def test_highlight_single_term(self) -> None:
        """Test highlighting a single search term."""
        from vozbot.dashboard.search import highlight_matches

        text = "This is a test of insurance search."
        result = highlight_matches(text, ["insurance"])

        assert "<mark>insurance</mark>" in result
        assert "test" in result  # Unmarked text preserved

    def test_highlight_multiple_terms(self) -> None:
        """Test highlighting multiple search terms."""
        from vozbot.dashboard.search import highlight_matches

        text = "Auto insurance policy for home coverage."
        result = highlight_matches(text, ["auto", "home"])

        assert "<mark>Auto</mark>" in result or "<mark>auto</mark>" in result
        assert "<mark>home</mark>" in result

    def test_highlight_case_insensitive(self) -> None:
        """Test that highlighting is case-insensitive."""
        from vozbot.dashboard.search import highlight_matches

        text = "INSURANCE policy for Insurance needs."
        result = highlight_matches(text, ["insurance"])

        # Should highlight both occurrences regardless of case
        assert result.count("<mark>") == 2

    def test_highlight_empty_terms(self) -> None:
        """Test that empty terms are handled gracefully."""
        from vozbot.dashboard.search import highlight_matches

        text = "Some text here."
        result = highlight_matches(text, [])

        assert result == text

    def test_highlight_empty_text(self) -> None:
        """Test that empty text is handled gracefully."""
        from vozbot.dashboard.search import highlight_matches

        result = highlight_matches("", ["test"])
        assert result == ""


class TestSnippetExtraction:
    """Tests for snippet extraction functions."""

    def test_extract_snippet_with_match(self) -> None:
        """Test extracting a snippet around a matching term."""
        from vozbot.dashboard.search import extract_snippet

        text = "A" * 200 + "MATCH" + "B" * 200
        snippet = extract_snippet(text, ["MATCH"], context_chars=50)

        assert "MATCH" in snippet
        assert len(snippet) < len(text)  # Should be a subset

    def test_extract_snippet_at_beginning(self) -> None:
        """Test snippet extraction when match is at the beginning."""
        from vozbot.dashboard.search import extract_snippet

        text = "MATCH" + "A" * 200
        snippet = extract_snippet(text, ["MATCH"], context_chars=50)

        assert "MATCH" in snippet
        assert snippet.startswith("MATCH")

    def test_extract_snippet_no_match(self) -> None:
        """Test snippet extraction when there's no match."""
        from vozbot.dashboard.search import extract_snippet

        text = "This is some sample text without the search term."
        snippet = extract_snippet(text, ["notfound"], context_chars=20)

        # Should return beginning of text
        assert snippet.startswith("This is")


class TestQueryParsing:
    """Tests for search query parsing."""

    def test_parse_simple_query(self) -> None:
        """Test parsing a simple query."""
        from vozbot.dashboard.search import parse_search_query

        terms = parse_search_query("auto insurance")
        assert "auto" in terms
        assert "insurance" in terms

    def test_parse_quoted_phrase(self) -> None:
        """Test parsing a quoted phrase."""
        from vozbot.dashboard.search import parse_search_query

        terms = parse_search_query('"auto insurance" policy')
        assert "auto insurance" in terms
        assert "policy" in terms

    def test_parse_empty_query(self) -> None:
        """Test parsing an empty query."""
        from vozbot.dashboard.search import parse_search_query

        terms = parse_search_query("")
        assert terms == []

    def test_parse_single_char_ignored(self) -> None:
        """Test that single character terms are ignored."""
        from vozbot.dashboard.search import parse_search_query

        terms = parse_search_query("a b insurance")
        assert "a" not in terms
        assert "b" not in terms
        assert "insurance" in terms


# -----------------------------------------------------------------------------
# Phone Search Tests
# -----------------------------------------------------------------------------


class TestPhoneSearch:
    """Tests for phone number search functionality."""

    def test_search_by_full_phone(self, session: Session, sample_data: list) -> None:
        """Test searching by full phone number."""
        from vozbot.dashboard.search import search_by_phone

        results = search_by_phone(session, "+15551234567")
        assert len(results) == 1
        task, call = results[0]
        assert task.name == "John Smith"

    def test_search_by_partial_phone(self, session: Session, sample_data: list) -> None:
        """Test searching by partial phone number."""
        from vozbot.dashboard.search import search_by_phone

        # Search with just the last 4 digits
        results = search_by_phone(session, "1234")
        assert len(results) >= 1

    def test_search_phone_with_formatting(self, session: Session, sample_data: list) -> None:
        """Test that phone search normalizes formatting."""
        from vozbot.dashboard.search import search_by_phone

        # Search with formatted number
        results = search_by_phone(session, "(555) 123-4567")
        assert len(results) == 1

    def test_search_callback_number(self, session: Session, sample_data: list) -> None:
        """Test searching by callback number."""
        from vozbot.dashboard.search import search_by_phone

        # Search for callback number instead of from_number
        results = search_by_phone(session, "9876543")
        assert len(results) == 1
        task, call = results[0]
        assert task.name == "John Smith"

    def test_search_phone_no_results(self, session: Session, sample_data: list) -> None:
        """Test phone search with no matches."""
        from vozbot.dashboard.search import search_by_phone

        results = search_by_phone(session, "0000000000")
        assert len(results) == 0


# -----------------------------------------------------------------------------
# Name Search Tests
# -----------------------------------------------------------------------------


class TestNameSearch:
    """Tests for name search functionality."""

    def test_search_by_full_name(self, session: Session, sample_data: list) -> None:
        """Test searching by full name."""
        from vozbot.dashboard.search import search_by_name

        # Search for "John Smith" - uses OR logic so may match multiple
        results = search_by_name(session, "John Smith")
        assert len(results) >= 1

        # The exact match should be in results
        names = [task.name for task, call in results]
        assert "John Smith" in names

    def test_search_by_first_name(self, session: Session, sample_data: list) -> None:
        """Test searching by first name only."""
        from vozbot.dashboard.search import search_by_name

        results = search_by_name(session, "John")
        assert len(results) >= 1  # Should find John Smith

    def test_search_by_last_name(self, session: Session, sample_data: list) -> None:
        """Test searching by last name only."""
        from vozbot.dashboard.search import search_by_name

        results = search_by_name(session, "Garcia")
        assert len(results) == 1
        task, call = results[0]
        assert task.name == "Maria Garcia"

    def test_search_name_case_insensitive(self, session: Session, sample_data: list) -> None:
        """Test that name search is case-insensitive."""
        from vozbot.dashboard.search import search_by_name

        results = search_by_name(session, "JOHN")
        assert len(results) >= 1

    def test_search_name_partial_match(self, session: Session, sample_data: list) -> None:
        """Test partial name matching."""
        from vozbot.dashboard.search import search_by_name

        results = search_by_name(session, "Rob")
        assert len(results) >= 1  # Should find Robert Johnson


# -----------------------------------------------------------------------------
# Full-Text Search Tests
# -----------------------------------------------------------------------------


class TestFullTextSearch:
    """Tests for full-text search functionality."""

    def test_search_transcript(self, session: Session, sample_data: list) -> None:
        """Test searching within transcripts."""
        from vozbot.dashboard.search import search_full_text

        results = search_full_text(session, "accident")
        assert len(results) >= 1

        # Should find Jane Doe's accident claim
        names = [task.name for task, call, score in results]
        assert "Jane Doe" in names

    def test_search_summary(self, session: Session, sample_data: list) -> None:
        """Test searching within summaries."""
        from vozbot.dashboard.search import search_full_text

        results = search_full_text(session, "Spanish-speaking")
        assert len(results) >= 1

        names = [task.name for task, call, score in results]
        assert "Maria Garcia" in names

    def test_search_intent(self, session: Session, sample_data: list) -> None:
        """Test searching within call intents."""
        from vozbot.dashboard.search import search_full_text

        results = search_full_text(session, "policy modification")
        assert len(results) >= 1

        names = [task.name for task, call, score in results]
        assert "Robert Johnson" in names

    def test_search_notes(self, session: Session, sample_data: list) -> None:
        """Test searching within notes."""
        from vozbot.dashboard.search import search_full_text

        results = search_full_text(session, "fender bender")
        assert len(results) >= 1

        names = [task.name for task, call, score in results]
        assert "Jane Doe" in names

    def test_search_multiple_terms(self, session: Session, sample_data: list) -> None:
        """Test searching with multiple terms (AND logic)."""
        from vozbot.dashboard.search import search_full_text

        results = search_full_text(session, "insurance auto")
        assert len(results) >= 1

    def test_search_relevance_scoring(self, session: Session, sample_data: list) -> None:
        """Test that relevance scores are calculated."""
        from vozbot.dashboard.search import search_full_text

        results = search_full_text(session, "insurance")

        # All results should have a relevance score > 0
        for task, call, score in results:
            assert score > 0


# -----------------------------------------------------------------------------
# Main Search Function Tests
# -----------------------------------------------------------------------------


class TestSearchTranscripts:
    """Tests for the main search_transcripts function."""

    def test_search_returns_paginated_results(self, session: Session, sample_data: list) -> None:
        """Test that search returns paginated results."""
        from vozbot.dashboard.search import search_transcripts

        results = search_transcripts(session, "insurance", page=1, page_size=2)

        assert results.page == 1
        assert results.page_size == 2
        assert results.total_count >= 0
        assert results.query == "insurance"

    def test_search_pagination_next_page(self, session: Session, sample_data: list) -> None:
        """Test pagination to next page."""
        from vozbot.dashboard.search import search_transcripts

        # Get first page
        page1 = search_transcripts(session, "insurance", page=1, page_size=2)

        if page1.total_pages > 1:
            # Get second page
            page2 = search_transcripts(session, "insurance", page=2, page_size=2)
            assert page2.page == 2

    def test_search_with_status_filter(self, session: Session, sample_data: list) -> None:
        """Test search with status filter."""
        from vozbot.dashboard.search import search_transcripts

        results = search_transcripts(
            session,
            "insurance",
            status_filter="Pending",
        )

        # All results should have pending status
        for result in results.results:
            assert result.task["status"] == "pending"

    def test_search_empty_query(self, session: Session, sample_data: list) -> None:
        """Test search with empty query."""
        from vozbot.dashboard.search import search_transcripts

        results = search_transcripts(session, "")

        assert results.total_count == 0
        assert results.results == []

    def test_search_single_char_query(self, session: Session, sample_data: list) -> None:
        """Test search with single character query (should be rejected)."""
        from vozbot.dashboard.search import search_transcripts

        results = search_transcripts(session, "a")

        assert results.total_count == 0

    def test_search_results_include_matches(self, session: Session, sample_data: list) -> None:
        """Test that search results include match information."""
        from vozbot.dashboard.search import search_transcripts

        results = search_transcripts(session, "John")

        if results.results:
            # At least one result should have matches
            has_matches = any(len(r.matches) > 0 for r in results.results)
            assert has_matches

    def test_search_by_phone_in_unified_search(self, session: Session, sample_data: list) -> None:
        """Test that phone numbers work in unified search."""
        from vozbot.dashboard.search import search_transcripts

        results = search_transcripts(session, "555-123-4567")

        assert results.total_count >= 1

    def test_search_combines_phone_and_text(self, session: Session, sample_data: list) -> None:
        """Test that unified search combines phone and text search."""
        from vozbot.dashboard.search import search_transcripts

        # Search for part of phone number
        results = search_transcripts(session, "1234567")

        # Should find results
        assert results.total_count >= 1


# -----------------------------------------------------------------------------
# SQL Injection Prevention Tests
# -----------------------------------------------------------------------------


class TestSQLInjectionPrevention:
    """Tests to verify SQL injection is prevented."""

    def test_injection_in_phone_search(self, session: Session, sample_data: list) -> None:
        """Test SQL injection attempt in phone search is safely handled."""
        from vozbot.dashboard.search import search_by_phone

        # Attempt SQL injection
        results = search_by_phone(session, "'; DROP TABLE callback_tasks; --")

        # Should return empty results, not crash
        assert results is not None
        assert isinstance(results, list)

    def test_injection_in_name_search(self, session: Session, sample_data: list) -> None:
        """Test SQL injection attempt in name search is safely handled."""
        from vozbot.dashboard.search import search_by_name

        # Attempt SQL injection
        results = search_by_name(session, "'; DROP TABLE callback_tasks; --")

        # Should return empty results, not crash
        assert results is not None

    def test_injection_in_full_text_search(self, session: Session, sample_data: list) -> None:
        """Test SQL injection attempt in full-text search is safely handled."""
        from vozbot.dashboard.search import search_transcripts

        # Various injection attempts
        injection_attempts = [
            "'; DROP TABLE calls; --",
            "1 OR 1=1",
            "UNION SELECT * FROM users",
            "'; DELETE FROM callback_tasks WHERE '1'='1",
            "<script>alert('xss')</script>",
        ]

        for attempt in injection_attempts:
            results = search_transcripts(session, attempt)
            # Should return valid (possibly empty) results, not crash
            assert results is not None
            assert hasattr(results, "results")

    def test_injection_with_special_characters(self, session: Session, sample_data: list) -> None:
        """Test that special SQL characters are handled safely."""
        from vozbot.dashboard.search import search_transcripts

        # Test with LIKE wildcards
        results = search_transcripts(session, "100%")
        assert results is not None

        results = search_transcripts(session, "test_underscore")
        assert results is not None


# -----------------------------------------------------------------------------
# Performance Tests
# -----------------------------------------------------------------------------


class TestSearchPerformance:
    """Tests for search performance requirements."""

    def test_search_performance_under_500ms(
        self, session: Session, large_data_set: list
    ) -> None:
        """Test that search completes in under 500ms for 100 records."""
        from vozbot.dashboard.search import search_transcripts

        start_time = time.time()
        results = search_transcripts(session, "insurance")
        elapsed_ms = (time.time() - start_time) * 1000

        # Should complete in under 500ms
        assert elapsed_ms < 500, f"Search took {elapsed_ms:.2f}ms, expected < 500ms"

    def test_search_performance_with_pagination(
        self, session: Session, large_data_set: list
    ) -> None:
        """Test that paginated search maintains performance."""
        from vozbot.dashboard.search import search_transcripts

        start_time = time.time()
        results = search_transcripts(session, "test", page=1, page_size=20)
        elapsed_ms = (time.time() - start_time) * 1000

        assert elapsed_ms < 500

    def test_search_performance_complex_query(
        self, session: Session, large_data_set: list
    ) -> None:
        """Test performance with complex multi-term query."""
        from vozbot.dashboard.search import search_transcripts

        start_time = time.time()
        results = search_transcripts(session, "test insurance policy auto home")
        elapsed_ms = (time.time() - start_time) * 1000

        assert elapsed_ms < 500


# -----------------------------------------------------------------------------
# Edge Cases
# -----------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_search_with_none_fields(self, session: Session) -> None:
        """Test search handles records with None fields gracefully."""
        from vozbot.dashboard.search import search_transcripts

        # Create a call with minimal data
        call = Call(
            id=str(uuid4()),
            from_number="+15550000000",
            status=CallStatus.INIT,
            # transcript, summary, intent all None
        )
        session.add(call)
        session.commit()

        task = CallbackTask(
            id=str(uuid4()),
            call_id=call.id,
            callback_number="+15550000001",
            # name, notes all None
        )
        session.add(task)
        session.commit()

        # Search should not crash
        results = search_transcripts(session, "test")
        assert results is not None

    def test_search_unicode_characters(self, session: Session, sample_data: list) -> None:
        """Test search handles unicode characters."""
        from vozbot.dashboard.search import search_transcripts

        # Search for Spanish text
        results = search_transcripts(session, "necesito")
        # Should find Maria Garcia's Spanish transcript
        assert results.total_count >= 1

    def test_search_very_long_query(self, session: Session, sample_data: list) -> None:
        """Test search handles very long queries."""
        from vozbot.dashboard.search import search_transcripts

        long_query = "insurance " * 100
        results = search_transcripts(session, long_query)

        # Should complete without error
        assert results is not None

    def test_search_empty_database(self, session: Session) -> None:
        """Test search on empty database."""
        from vozbot.dashboard.search import search_transcripts

        results = search_transcripts(session, "test")

        assert results.total_count == 0
        assert results.results == []
