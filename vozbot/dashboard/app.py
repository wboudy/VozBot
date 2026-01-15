"""VozBot Staff Dashboard - Streamlit Application.

A simple, responsive dashboard for office staff to manage callback tasks.
Features:
- View callback tasks with sorting by priority, created_at, status
- Expand rows to see transcript and summary
- Mark tasks as complete
- Auto-refresh every 30 seconds
- Basic password protection
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import streamlit as st
from sqlalchemy import create_engine, desc, select
from sqlalchemy.orm import Session, sessionmaker

from vozbot.dashboard.search import (
    PaginatedSearchResults,
    SearchResult,
    search_transcripts,
)
from vozbot.storage.db.models import (
    Call,
    CallbackTask,
    TaskStatus,
)

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

# Page config must be first Streamlit command
st.set_page_config(
    page_title="VozBot Dashboard",
    page_icon="phone",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def get_database_url() -> str:
    """Get database URL from environment, converting to sync driver."""
    db_url = os.getenv("DATABASE_URL") or os.getenv("DB_URL", "")

    # Convert async URL to sync for Streamlit
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)

    return db_url


def get_dashboard_password() -> str:
    """Get dashboard password from environment."""
    return os.getenv("DASHBOARD_PASSWORD", "vozbot2024")


# -----------------------------------------------------------------------------
# Database Session Management
# -----------------------------------------------------------------------------

@st.cache_resource
def get_engine():
    """Create and cache database engine."""
    db_url = get_database_url()
    if not db_url:
        return None
    return create_engine(db_url, pool_pre_ping=True)


def get_session() -> Session | None:
    """Get a database session."""
    engine = get_engine()
    if engine is None:
        return None
    session_factory = sessionmaker(bind=engine)
    return session_factory()


# -----------------------------------------------------------------------------
# Authentication
# -----------------------------------------------------------------------------

def check_password() -> bool:
    """Returns True if the user has entered the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state.get("password") == get_dashboard_password():
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password
        else:
            st.session_state["password_correct"] = False

    # First run or password not yet correct
    if "password_correct" not in st.session_state:
        st.text_input(
            "Password",
            type="password",
            on_change=password_entered,
            key="password",
            placeholder="Enter dashboard password",
        )
        st.info("Please enter the dashboard password to continue.")
        return False

    # Password was entered incorrectly
    if not st.session_state["password_correct"]:
        st.text_input(
            "Password",
            type="password",
            on_change=password_entered,
            key="password",
            placeholder="Enter dashboard password",
        )
        st.error("Incorrect password. Please try again.")
        return False

    return True


# -----------------------------------------------------------------------------
# Data Loading
# -----------------------------------------------------------------------------

def load_callback_tasks(
    session: Session,
    sort_by: str = "priority",
    status_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Load callback tasks with associated call data.

    Args:
        session: Database session
        sort_by: Field to sort by (priority, created_at, status)
        status_filter: Optional status filter

    Returns:
        List of task dictionaries with call data
    """
    # Build query
    query = select(CallbackTask, Call).join(Call, CallbackTask.call_id == Call.id)

    # Apply status filter
    if status_filter and status_filter != "All":
        try:
            status_enum = TaskStatus(status_filter.lower())
            query = query.where(CallbackTask.status == status_enum)
        except ValueError:
            pass

    # Apply sorting
    if sort_by == "priority":
        # Sort by priority descending (urgent first), then by created_at
        query = query.order_by(desc(CallbackTask.priority), desc(CallbackTask.created_at))
    elif sort_by == "created_at":
        query = query.order_by(desc(CallbackTask.created_at))
    elif sort_by == "status":
        query = query.order_by(CallbackTask.status, desc(CallbackTask.created_at))
    else:
        query = query.order_by(desc(CallbackTask.created_at))

    # Execute query
    results = session.execute(query).all()

    # Convert to dictionaries
    tasks = []
    for task, call in results:
        tasks.append({
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
        })

    return tasks


def update_task_status(session: Session, task_id: str, new_status: TaskStatus) -> bool:
    """Update a task's status.

    Args:
        session: Database session
        task_id: Task ID to update
        new_status: New status to set

    Returns:
        True if successful, False otherwise
    """
    try:
        task = session.get(CallbackTask, task_id)
        if task:
            task.status = new_status
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        st.error(f"Error updating task: {e}")
        return False


# -----------------------------------------------------------------------------
# UI Components
# -----------------------------------------------------------------------------

def priority_badge(priority: str) -> str:
    """Return HTML for a colored priority badge."""
    colors = {
        "URGENT": "#dc3545",  # Red
        "HIGH": "#fd7e14",    # Orange
        "NORMAL": "#0d6efd",  # Blue
        "LOW": "#6c757d",     # Gray
    }
    color = colors.get(priority, "#6c757d")
    return f'<span style="background-color: {color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.85em;">{priority}</span>'


def status_badge(status: str) -> str:
    """Return HTML for a colored status badge."""
    colors = {
        "pending": "#ffc107",      # Yellow
        "in_progress": "#0dcaf0",  # Cyan
        "completed": "#198754",    # Green
        "cancelled": "#6c757d",    # Gray
    }
    color = colors.get(status, "#6c757d")
    return f'<span style="background-color: {color}; color: {"black" if status in ["pending", "in_progress"] else "white"}; padding: 2px 8px; border-radius: 4px; font-size: 0.85em;">{status.upper()}</span>'


def format_time(dt: datetime | None) -> str:
    """Format datetime for display."""
    if dt is None:
        return "-"
    return dt.strftime("%b %d, %Y %I:%M %p")


def render_task_row(task: dict[str, Any], index: int) -> None:
    """Render a single task row with expandable details."""

    # Create expander for each task
    with st.expander(
        f"**{task['name']}** | {task['phone']} | {task['priority']} | {task['status'].upper()}",
        expanded=False,
    ):
        # Main info columns
        col1, col2, col3 = st.columns([2, 2, 1])

        with col1:
            st.markdown("**Contact Info**")
            st.write(f"Name: {task['name']}")
            st.write(f"Phone: {task['phone']}")
            st.write(f"Best Time: {task['best_time']}")
            st.write(f"Language: {task['language']}")

        with col2:
            st.markdown("**Task Details**")
            st.write(f"Priority: {task['priority']}")
            st.write(f"Status: {task['status']}")
            st.write(f"Assignee: {task['assignee']}")
            st.write(f"Created: {format_time(task['created_at'])}")

        with col3:
            st.markdown("**Actions**")
            if task['status'] != "completed" and st.button(
                "Mark Complete", key=f"complete_{task['id']}"
            ):
                session = get_session()
                if session:
                    if update_task_status(session, task['id'], TaskStatus.COMPLETED):
                        st.success("Task marked as complete!")
                        st.rerun()
                    session.close()

        # Intent
        if task['call_intent'] != "-":
            st.markdown("**Call Intent**")
            st.info(task['call_intent'])

        # Notes
        if task['notes']:
            st.markdown("**Notes**")
            st.info(task['notes'])

        # Summary
        st.markdown("**Summary**")
        st.write(task['summary'])

        # Transcript
        st.markdown("**Transcript**")
        st.text_area(
            "Full Conversation",
            value=task['transcript'],
            height=200,
            key=f"transcript_{task['id']}",
            disabled=True,
        )


def render_task_table(tasks: list[dict[str, Any]]) -> None:
    """Render tasks in a responsive table format."""
    if not tasks:
        st.info("No callback tasks found.")
        return

    # Summary stats
    col1, col2, col3, col4, col5 = st.columns(5)
    pending_count = sum(1 for t in tasks if t['status'] == 'pending')
    in_progress_count = sum(1 for t in tasks if t['status'] == 'in_progress')
    completed_count = sum(1 for t in tasks if t['status'] == 'completed')
    urgent_count = sum(1 for t in tasks if t['priority'] == 'URGENT')

    with col1:
        st.metric("Total", len(tasks))
    with col2:
        st.metric("Pending", pending_count)
    with col3:
        st.metric("In Progress", in_progress_count)
    with col4:
        st.metric("Completed", completed_count)
    with col5:
        st.metric("Urgent", urgent_count)

    st.divider()

    # Render each task
    for i, task in enumerate(tasks):
        render_task_row(task, i)


# -----------------------------------------------------------------------------
# Search UI Components
# -----------------------------------------------------------------------------


def render_search_result_row(result: SearchResult, index: int) -> None:
    """Render a single search result row with highlighted matches."""
    task = result.task

    # Create expander for each result
    with st.expander(
        f"**{task['name']}** | {task['phone']} | {task['priority']} | Score: {result.relevance_score:.1f}",
        expanded=False,
    ):
        # Show match highlights first
        if result.matches:
            st.markdown("**Matching Terms:**")
            for match in result.matches:
                st.markdown(
                    f"- **{match.field}**: {match.highlighted}",
                    unsafe_allow_html=True,
                )
            st.divider()

        # Main info columns
        col1, col2, col3 = st.columns([2, 2, 1])

        with col1:
            st.markdown("**Contact Info**")
            st.write(f"Name: {task['name']}")
            st.write(f"Phone: {task['phone']}")
            st.write(f"Best Time: {task['best_time']}")
            st.write(f"Language: {task['language']}")

        with col2:
            st.markdown("**Task Details**")
            st.write(f"Priority: {task['priority']}")
            st.write(f"Status: {task['status']}")
            st.write(f"Assignee: {task['assignee']}")
            st.write(f"Created: {format_time(task['created_at'])}")

        with col3:
            st.markdown("**Actions**")
            if task['status'] != "completed" and st.button(
                "Mark Complete", key=f"search_complete_{task['id']}_{index}"
            ):
                session = get_session()
                if session:
                    if update_task_status(session, task['id'], TaskStatus.COMPLETED):
                        st.success("Task marked as complete!")
                        st.rerun()
                    session.close()

        # Intent
        if task['call_intent'] != "-":
            st.markdown("**Call Intent**")
            st.info(task['call_intent'])

        # Notes
        if task['notes']:
            st.markdown("**Notes**")
            st.info(task['notes'])

        # Summary
        st.markdown("**Summary**")
        st.write(task['summary'])

        # Transcript
        st.markdown("**Transcript**")
        st.text_area(
            "Full Conversation",
            value=task['transcript'],
            height=200,
            key=f"search_transcript_{task['id']}_{index}",
            disabled=True,
        )


def render_search_results(results: PaginatedSearchResults) -> None:
    """Render paginated search results."""
    if not results.results:
        st.info(f"No results found for '{results.query}'")
        return

    # Results header
    st.markdown(
        f"**Found {results.total_count} result{'s' if results.total_count != 1 else ''}** "
        f"for '{results.query}'"
    )

    # Render each result
    for i, result in enumerate(results.results):
        render_search_result_row(result, i)

    # Pagination controls
    if results.total_pages > 1:
        st.divider()
        col1, col2, col3 = st.columns([1, 2, 1])

        with col1:
            if results.page > 1 and st.button("Previous", key="search_prev"):
                st.session_state["search_page"] = results.page - 1
                st.rerun()

        with col2:
            st.markdown(
                f"<div style='text-align: center'>Page {results.page} of {results.total_pages}</div>",
                unsafe_allow_html=True,
            )

        with col3:
            if results.page < results.total_pages and st.button("Next", key="search_next"):
                st.session_state["search_page"] = results.page + 1
                st.rerun()


# -----------------------------------------------------------------------------
# Main Application
# -----------------------------------------------------------------------------

def main():
    """Main application entry point."""

    # Title and header
    st.title("VozBot Staff Dashboard")
    st.markdown("Manage callback requests from customer calls")

    # Check authentication
    if not check_password():
        return

    # Check database connection
    session = get_session()
    if session is None:
        st.error(
            "Database not configured. Please set DATABASE_URL or DB_URL environment variable."
        )
        st.info(
            "For local development, you can use:\n"
            "`export DATABASE_URL=postgresql://user:pass@localhost:5432/vozbot`"
        )
        return

    try:
        # Initialize session state for search
        if "search_query" not in st.session_state:
            st.session_state["search_query"] = ""
        if "search_page" not in st.session_state:
            st.session_state["search_page"] = 1
        if "search_active" not in st.session_state:
            st.session_state["search_active"] = False

        # Sidebar for search, filters and settings
        with st.sidebar:
            # Search section
            st.header("Search")

            # Search input
            search_query = st.text_input(
                "Search transcripts",
                value=st.session_state.get("search_query", ""),
                placeholder="Name, phone, or keywords...",
                key="search_input",
                help="Search by phone number, name, or full-text across transcripts and summaries",
            )

            # Search button
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Search", type="primary", use_container_width=True):
                    st.session_state["search_query"] = search_query
                    st.session_state["search_page"] = 1
                    st.session_state["search_active"] = bool(search_query.strip())
                    st.rerun()

            with col2:
                if st.button("Clear", use_container_width=True):
                    st.session_state["search_query"] = ""
                    st.session_state["search_page"] = 1
                    st.session_state["search_active"] = False
                    st.rerun()

            st.divider()

            st.header("Filters")

            # Sort options
            sort_by = st.selectbox(
                "Sort by",
                options=["priority", "created_at", "status"],
                index=0,
                format_func=lambda x: {
                    "priority": "Priority (Urgent First)",
                    "created_at": "Date Created (Newest)",
                    "status": "Status",
                }.get(x, x),
            )

            # Status filter
            status_filter = st.selectbox(
                "Status",
                options=["All", "Pending", "In Progress", "Completed", "Cancelled"],
                index=0,
            )

            st.divider()

            # Auto-refresh toggle (disable during search)
            auto_refresh_disabled = st.session_state.get("search_active", False)
            auto_refresh = st.checkbox(
                "Auto-refresh (30s)",
                value=not auto_refresh_disabled,
                disabled=auto_refresh_disabled,
                help="Disabled during search" if auto_refresh_disabled else None,
            )

            if st.button("Refresh Now"):
                st.rerun()

            st.divider()

            # Logout
            if st.button("Logout"):
                del st.session_state["password_correct"]
                st.rerun()

        # Auto-refresh using st.fragment and sleep
        if auto_refresh and not st.session_state.get("search_active", False):
            # Use st.empty() with time-based rerun
            import time

            # Store last refresh time
            if "last_refresh" not in st.session_state:
                st.session_state["last_refresh"] = time.time()

            # Check if 30 seconds have passed
            elapsed = time.time() - st.session_state["last_refresh"]
            if elapsed >= 30:
                st.session_state["last_refresh"] = time.time()
                st.rerun()

        # Main content area - either search results or task list
        if st.session_state.get("search_active", False):
            # Show search results
            st.subheader("Search Results")

            search_results = search_transcripts(
                session,
                st.session_state["search_query"],
                page=st.session_state.get("search_page", 1),
                page_size=20,
                status_filter=status_filter,
            )

            render_search_results(search_results)

        else:
            # Show normal task list
            tasks = load_callback_tasks(
                session,
                sort_by=sort_by,
                status_filter=status_filter,
            )

            render_task_table(tasks)

        # Auto-refresh script (only when not searching)
        if auto_refresh and not st.session_state.get("search_active", False):
            st.markdown(
                """
                <script>
                    setTimeout(function() {
                        window.location.reload();
                    }, 30000);
                </script>
                """,
                unsafe_allow_html=True,
            )

    finally:
        session.close()


# -----------------------------------------------------------------------------
# Custom CSS for responsive design
# -----------------------------------------------------------------------------

def inject_custom_css():
    """Inject custom CSS for responsive design."""
    st.markdown(
        """
        <style>
        /* Responsive adjustments */
        @media (max-width: 768px) {
            .stExpander {
                font-size: 0.9rem;
            }
            .stMetric {
                font-size: 0.8rem;
            }
            [data-testid="column"] {
                width: 100% !important;
                flex: 100% !important;
                min-width: 100% !important;
            }
        }

        /* Better mobile touch targets */
        .stButton > button {
            min-height: 44px;
            padding: 0.5rem 1rem;
        }

        /* Improve readability */
        .stExpander {
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            margin-bottom: 0.5rem;
        }

        /* Priority colors in expander header */
        .urgent-task {
            border-left: 4px solid #dc3545 !important;
        }
        .high-task {
            border-left: 4px solid #fd7e14 !important;
        }

        /* Better text area styling */
        .stTextArea textarea {
            font-family: monospace;
            font-size: 0.85rem;
        }

        /* Metric styling */
        [data-testid="stMetricValue"] {
            font-size: 1.5rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# Entry point
if __name__ == "__main__":
    inject_custom_css()
    main()
