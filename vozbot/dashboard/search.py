"""Transcript search functionality for VozBot Dashboard.

Provides full-text search across callback tasks, including:
- Phone number partial matching
- Fuzzy name matching (trigram similarity)
- Full-text search on transcript and summary
- Highlighted results with matching terms
- Pagination support

Uses SQLAlchemy parameterized queries to prevent SQL injection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from vozbot.storage.db.models import Call, CallbackTask

# -----------------------------------------------------------------------------
# Search Result Types
# -----------------------------------------------------------------------------


@dataclass
class SearchMatch:
    """Represents a matching snippet with highlighting."""

    field: str
    snippet: str
    highlighted: str


@dataclass
class SearchResult:
    """A single search result with task data and highlights."""

    task: dict[str, Any]
    matches: list[SearchMatch]
    relevance_score: float


@dataclass
class PaginatedSearchResults:
    """Paginated search results."""

    results: list[SearchResult]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    query: str


# -----------------------------------------------------------------------------
# Highlighting Utilities
# -----------------------------------------------------------------------------


def highlight_matches(text: str, search_terms: list[str], tag: str = "mark") -> str:
    """Highlight search terms in text with HTML tags.

    Args:
        text: The text to highlight
        search_terms: List of terms to highlight
        tag: HTML tag to use for highlighting (default: "mark")

    Returns:
        Text with matching terms wrapped in HTML tags
    """
    if not text or not search_terms:
        return text

    result = text
    for term in search_terms:
        if not term:
            continue
        # Case-insensitive replacement preserving original case
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        result = pattern.sub(lambda m: f"<{tag}>{m.group()}</{tag}>", result)

    return result


def extract_snippet(text: str, search_terms: list[str], context_chars: int = 100) -> str:
    """Extract a relevant snippet from text around the first match.

    Args:
        text: The full text to search
        search_terms: Terms to find in text
        context_chars: Number of characters to show around match

    Returns:
        Snippet of text containing the match with surrounding context
    """
    if not text:
        return ""

    if not search_terms:
        # Return beginning of text if no search terms
        return text[:context_chars * 2] + ("..." if len(text) > context_chars * 2 else "")

    # Find the first matching term
    text_lower = text.lower()
    first_match_pos = -1

    for term in search_terms:
        if not term:
            continue
        pos = text_lower.find(term.lower())
        if pos != -1 and (first_match_pos == -1 or pos < first_match_pos):
            first_match_pos = pos

    if first_match_pos == -1:
        # No match found, return beginning
        return text[:context_chars * 2] + ("..." if len(text) > context_chars * 2 else "")

    # Calculate snippet boundaries
    start = max(0, first_match_pos - context_chars)
    end = min(len(text), first_match_pos + context_chars + len(search_terms[0]))

    # Build snippet
    snippet = ""
    if start > 0:
        snippet += "..."
    snippet += text[start:end]
    if end < len(text):
        snippet += "..."

    return snippet


def parse_search_query(query: str) -> list[str]:
    """Parse a search query into individual search terms.

    Handles quoted phrases and splits on whitespace.

    Args:
        query: Raw search query string

    Returns:
        List of search terms
    """
    if not query:
        return []

    terms = []

    # Extract quoted phrases first
    quoted_pattern = re.compile(r'"([^"]+)"')
    for match in quoted_pattern.finditer(query):
        terms.append(match.group(1))

    # Remove quoted phrases from query
    remaining = quoted_pattern.sub("", query)

    # Split remaining text on whitespace
    for term in remaining.split():
        term = term.strip()
        if term and len(term) >= 2:  # Minimum 2 chars
            terms.append(term)

    return terms


# -----------------------------------------------------------------------------
# Search Functions
# -----------------------------------------------------------------------------


def search_by_phone(
    session: Session,
    phone_query: str,
) -> list[tuple[CallbackTask, Call]]:
    """Search for tasks by phone number (partial match).

    Uses parameterized query with LIKE operator for partial matching.
    Phone numbers are normalized to remove common formatting characters.

    Args:
        session: Database session
        phone_query: Phone number to search for (partial)

    Returns:
        List of (CallbackTask, Call) tuples matching the phone number
    """
    # Normalize phone query - remove common formatting
    normalized = re.sub(r"[^\d+]", "", phone_query)

    if not normalized:
        return []

    # Use parameterized LIKE query (safe from SQL injection)
    search_pattern = f"%{normalized}%"

    query = (
        session.query(CallbackTask, Call)
        .join(Call, CallbackTask.call_id == Call.id)
        .filter(
            or_(
                CallbackTask.callback_number.like(search_pattern),
                Call.from_number.like(search_pattern),
            )
        )
        .order_by(desc(CallbackTask.created_at))
    )

    return query.all()


def search_by_name(
    session: Session,
    name_query: str,
) -> list[tuple[CallbackTask, Call]]:
    """Search for tasks by name (fuzzy match).

    Uses ILIKE for case-insensitive partial matching.
    For true fuzzy matching (Levenshtein distance), this would need
    PostgreSQL pg_trgm extension - falling back to ILIKE for SQLite compatibility.

    Args:
        session: Database session
        name_query: Name to search for

    Returns:
        List of (CallbackTask, Call) tuples matching the name
    """
    if not name_query or len(name_query) < 2:
        return []

    # Split name into parts for flexible matching
    name_parts = name_query.strip().split()

    # Build conditions for each name part
    conditions = []
    for part in name_parts:
        if len(part) >= 2:
            pattern = f"%{part}%"
            conditions.append(CallbackTask.name.ilike(pattern))

    if not conditions:
        return []

    # Match any part of the name
    query = (
        session.query(CallbackTask, Call)
        .join(Call, CallbackTask.call_id == Call.id)
        .filter(or_(*conditions))
        .order_by(desc(CallbackTask.created_at))
    )

    return query.all()


def search_full_text(
    session: Session,
    search_query: str,
) -> list[tuple[CallbackTask, Call, float]]:
    """Full-text search on transcript and summary.

    Searches across transcript, summary, call intent, and notes.
    Returns results with a simple relevance score based on number of matches.

    Args:
        session: Database session
        search_query: Text to search for

    Returns:
        List of (CallbackTask, Call, score) tuples
    """
    terms = parse_search_query(search_query)

    if not terms:
        return []

    # Build conditions for each term
    conditions = []
    for term in terms:
        pattern = f"%{term}%"
        term_conditions = [
            Call.transcript.ilike(pattern),
            Call.summary.ilike(pattern),
            Call.intent.ilike(pattern),
            CallbackTask.notes.ilike(pattern),
            CallbackTask.name.ilike(pattern),
        ]
        conditions.append(or_(*term_conditions))

    # All terms must match (AND)
    query = (
        session.query(CallbackTask, Call)
        .join(Call, CallbackTask.call_id == Call.id)
        .filter(*conditions)
        .order_by(desc(CallbackTask.created_at))
    )

    results = query.all()

    # Calculate simple relevance score based on match count
    scored_results = []
    for task, call in results:
        score = _calculate_relevance_score(task, call, terms)
        scored_results.append((task, call, score))

    # Sort by relevance score descending
    scored_results.sort(key=lambda x: x[2], reverse=True)

    return scored_results


def _calculate_relevance_score(
    task: CallbackTask,
    call: Call,
    terms: list[str],
) -> float:
    """Calculate a relevance score for a search result.

    Score is based on:
    - Number of term occurrences
    - Where terms appear (name weighted higher than transcript)

    Args:
        task: The callback task
        call: The associated call
        terms: Search terms

    Returns:
        Relevance score (higher is more relevant)
    """
    score = 0.0

    # Weight factors for different fields
    weights = {
        "name": 3.0,
        "intent": 2.0,
        "summary": 1.5,
        "notes": 1.5,
        "transcript": 1.0,
    }

    for term in terms:
        term_lower = term.lower()

        # Check name
        if task.name and term_lower in task.name.lower():
            score += weights["name"]

        # Check intent
        if call.intent and term_lower in call.intent.lower():
            score += weights["intent"]

        # Check summary
        if call.summary and term_lower in call.summary.lower():
            score += weights["summary"]

        # Check notes
        if task.notes and term_lower in task.notes.lower():
            score += weights["notes"]

        # Check transcript (count occurrences)
        if call.transcript:
            count = call.transcript.lower().count(term_lower)
            score += weights["transcript"] * min(count, 5)  # Cap at 5 occurrences

    return score


def search_transcripts(
    session: Session,
    query: str,
    page: int = 1,
    page_size: int = 20,
    status_filter: str | None = None,
) -> PaginatedSearchResults:
    """Main search function combining all search types.

    Performs a unified search across:
    - Phone numbers (partial match)
    - Names (fuzzy match)
    - Full-text on transcript, summary, intent, notes

    Args:
        session: Database session
        query: Search query string
        page: Page number (1-indexed)
        page_size: Results per page (default 20)
        status_filter: Optional status filter

    Returns:
        PaginatedSearchResults with highlighted matches
    """
    from vozbot.storage.db.models import TaskStatus

    if not query or len(query.strip()) < 2:
        return PaginatedSearchResults(
            results=[],
            total_count=0,
            page=page,
            page_size=page_size,
            total_pages=0,
            query=query or "",
        )

    query = query.strip()
    terms = parse_search_query(query)

    # Normalize phone query for phone search
    phone_normalized = re.sub(r"[^\d+]", "", query)

    # Build comprehensive search conditions
    conditions = []

    # Phone number search (if query looks like a phone number)
    if phone_normalized and len(phone_normalized) >= 3:
        phone_pattern = f"%{phone_normalized}%"
        conditions.append(CallbackTask.callback_number.like(phone_pattern))
        conditions.append(Call.from_number.like(phone_pattern))

    # Name search
    for term in terms:
        name_pattern = f"%{term}%"
        conditions.append(CallbackTask.name.ilike(name_pattern))

    # Full-text search on transcript/summary
    for term in terms:
        pattern = f"%{term}%"
        conditions.extend([
            Call.transcript.ilike(pattern),
            Call.summary.ilike(pattern),
            Call.intent.ilike(pattern),
            CallbackTask.notes.ilike(pattern),
        ])

    if not conditions:
        return PaginatedSearchResults(
            results=[],
            total_count=0,
            page=page,
            page_size=page_size,
            total_pages=0,
            query=query,
        )

    # Build base query with OR across all conditions
    base_query = (
        session.query(CallbackTask, Call)
        .join(Call, CallbackTask.call_id == Call.id)
        .filter(or_(*conditions))
    )

    # Apply status filter if provided
    if status_filter and status_filter != "All":
        try:
            status_enum = TaskStatus(status_filter.lower())
            base_query = base_query.filter(CallbackTask.status == status_enum)
        except ValueError:
            pass

    # Get total count
    total_count = base_query.count()

    # Calculate pagination
    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0
    page = max(1, min(page, total_pages)) if total_pages > 0 else 1
    offset = (page - 1) * page_size

    # Get paginated results
    results = (
        base_query
        .order_by(desc(CallbackTask.created_at))
        .offset(offset)
        .limit(page_size)
        .all()
    )

    # Build search results with highlighting
    search_results = []
    for task, call in results:
        # Calculate relevance score
        score = _calculate_relevance_score(task, call, terms)

        # Build task dictionary
        task_dict = _task_to_dict(task, call)

        # Find matches and create highlighted snippets
        matches = _find_matches(task, call, terms)

        search_results.append(SearchResult(
            task=task_dict,
            matches=matches,
            relevance_score=score,
        ))

    # Sort by relevance score
    search_results.sort(key=lambda x: x.relevance_score, reverse=True)

    return PaginatedSearchResults(
        results=search_results,
        total_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        query=query,
    )


def _task_to_dict(task: CallbackTask, call: Call) -> dict[str, Any]:
    """Convert a task and call to a dictionary for display.

    Args:
        task: The callback task
        call: The associated call

    Returns:
        Dictionary with task data
    """
    return {
        "id": task.id,
        "name": task.name or "Unknown",
        "phone": task.callback_number,
        "priority": task.priority.name if task.priority else "NORMAL",
        "priority_value": task.priority.value if task.priority else 2,
        "created_at": task.created_at,
        "status": task.status.value if task.status else "pending",
        "best_time": task.best_time_window or "-",
        "notes": task.notes or "",
        "assignee": task.assignee or "-",
        "transcript": call.transcript or "No transcript available",
        "summary": call.summary or "No summary available",
        "call_intent": call.intent or "-",
        "language": call.language.value if call.language else "-",
        "from_number": call.from_number,
    }


def _find_matches(
    task: CallbackTask,
    call: Call,
    terms: list[str],
) -> list[SearchMatch]:
    """Find and highlight matches in task/call fields.

    Args:
        task: The callback task
        call: The associated call
        terms: Search terms to highlight

    Returns:
        List of SearchMatch objects with snippets and highlighting
    """
    matches = []

    # Check name
    if task.name:
        for term in terms:
            if term.lower() in task.name.lower():
                matches.append(SearchMatch(
                    field="Name",
                    snippet=task.name,
                    highlighted=highlight_matches(task.name, terms),
                ))
                break

    # Check phone numbers
    phone_terms = [re.sub(r"[^\d+]", "", t) for t in terms if re.sub(r"[^\d+]", "", t)]
    if phone_terms:
        for phone in [task.callback_number, call.from_number]:
            if phone:
                phone_normalized = re.sub(r"[^\d+]", "", phone)
                for term in phone_terms:
                    if term in phone_normalized:
                        matches.append(SearchMatch(
                            field="Phone",
                            snippet=phone,
                            highlighted=highlight_matches(phone, [term]),
                        ))
                        break

    # Check intent
    if call.intent:
        for term in terms:
            if term.lower() in call.intent.lower():
                matches.append(SearchMatch(
                    field="Intent",
                    snippet=call.intent,
                    highlighted=highlight_matches(call.intent, terms),
                ))
                break

    # Check summary
    if call.summary:
        for term in terms:
            if term.lower() in call.summary.lower():
                snippet = extract_snippet(call.summary, terms)
                matches.append(SearchMatch(
                    field="Summary",
                    snippet=snippet,
                    highlighted=highlight_matches(snippet, terms),
                ))
                break

    # Check transcript
    if call.transcript:
        for term in terms:
            if term.lower() in call.transcript.lower():
                snippet = extract_snippet(call.transcript, terms)
                matches.append(SearchMatch(
                    field="Transcript",
                    snippet=snippet,
                    highlighted=highlight_matches(snippet, terms),
                ))
                break

    # Check notes
    if task.notes:
        for term in terms:
            if term.lower() in task.notes.lower():
                snippet = extract_snippet(task.notes, terms)
                matches.append(SearchMatch(
                    field="Notes",
                    snippet=snippet,
                    highlighted=highlight_matches(snippet, terms),
                ))
                break

    return matches
