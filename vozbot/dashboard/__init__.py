"""VozBot Staff Dashboard.

Streamlit-based dashboard for viewing and managing callback tasks.
"""

from vozbot.dashboard.search import (
    PaginatedSearchResults,
    SearchMatch,
    SearchResult,
    highlight_matches,
    search_transcripts,
)

__all__ = [
    "PaginatedSearchResults",
    "SearchMatch",
    "SearchResult",
    "highlight_matches",
    "search_transcripts",
]
