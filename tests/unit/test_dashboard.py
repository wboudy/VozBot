"""Tests for the VozBot Staff Dashboard.

Verifies dashboard loads without error and core functionality works.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch
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
def sample_call(session: Session) -> Call:
    """Create a sample call for testing."""
    call = Call(
        id=str(uuid4()),
        from_number="+15551234567",
        language=Language.EN,
        customer_type=CustomerType.NEW,
        intent="Request quote for auto insurance",
        status=CallStatus.COMPLETED,
        summary="New customer requesting auto insurance quote.",
        transcript="Agent: Hello... Customer: Hi, I need a quote...",
        costs={"stt": 0.05, "tts": 0.03, "llm": 0.10},
    )
    session.add(call)
    session.commit()
    session.refresh(call)
    return call


@pytest.fixture
def sample_callback_task(session: Session, sample_call: Call) -> CallbackTask:
    """Create a sample callback task for testing."""
    task = CallbackTask(
        id=str(uuid4()),
        call_id=sample_call.id,
        priority=TaskPriority.HIGH,
        assignee="Mom",
        name="John Doe",
        callback_number="+15559999999",
        best_time_window="Morning 9am-12pm",
        notes="Customer prefers callback in English.",
        status=TaskStatus.PENDING,
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@pytest.fixture
def multiple_tasks(session: Session) -> list[CallbackTask]:
    """Create multiple callback tasks with different priorities."""
    tasks = []

    # Create tasks with different priorities
    priorities = [
        (TaskPriority.URGENT, "Urgent Customer", TaskStatus.PENDING),
        (TaskPriority.HIGH, "High Priority", TaskStatus.PENDING),
        (TaskPriority.NORMAL, "Normal Task", TaskStatus.IN_PROGRESS),
        (TaskPriority.LOW, "Low Priority", TaskStatus.COMPLETED),
    ]

    for priority, name, status in priorities:
        call = Call(
            id=str(uuid4()),
            from_number=f"+1555{priority.value}000000",
            language=Language.EN,
            status=CallStatus.COMPLETED,
            summary=f"Call for {name}",
            transcript=f"Transcript for {name}",
        )
        session.add(call)
        session.commit()
        session.refresh(call)

        task = CallbackTask(
            id=str(uuid4()),
            call_id=call.id,
            priority=priority,
            name=name,
            callback_number=f"+1555{priority.value}111111",
            status=status,
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        tasks.append(task)

    return tasks


# -----------------------------------------------------------------------------
# Import Tests
# -----------------------------------------------------------------------------


class TestDashboardImports:
    """Test that dashboard module can be imported."""

    def test_dashboard_module_imports(self) -> None:
        """Test that the dashboard module can be imported."""
        # This will fail if there are import errors
        from vozbot.dashboard import app

        assert app is not None

    def test_dashboard_functions_exist(self) -> None:
        """Test that expected functions exist in the dashboard module."""
        from vozbot.dashboard import app

        # Check key functions exist
        assert hasattr(app, "main")
        assert hasattr(app, "check_password")
        assert hasattr(app, "load_callback_tasks")
        assert hasattr(app, "update_task_status")
        assert hasattr(app, "get_database_url")
        assert hasattr(app, "format_time")


# -----------------------------------------------------------------------------
# Data Loading Tests
# -----------------------------------------------------------------------------


class TestDataLoading:
    """Tests for data loading functions."""

    def test_load_callback_tasks_empty(self, session: Session) -> None:
        """Test loading tasks when database is empty."""
        from vozbot.dashboard.app import load_callback_tasks

        tasks = load_callback_tasks(session)
        assert tasks == []

    def test_load_callback_tasks_with_data(
        self, session: Session, sample_callback_task: CallbackTask
    ) -> None:
        """Test loading tasks with data in database."""
        from vozbot.dashboard.app import load_callback_tasks

        tasks = load_callback_tasks(session)

        assert len(tasks) == 1
        assert tasks[0]["name"] == "John Doe"
        assert tasks[0]["phone"] == "+15559999999"
        assert tasks[0]["priority"] == "HIGH"
        assert tasks[0]["status"] == "pending"
        assert "transcript" in tasks[0]
        assert "summary" in tasks[0]

    def test_load_callback_tasks_sort_by_priority(
        self, session: Session, multiple_tasks: list[CallbackTask]
    ) -> None:
        """Test that tasks are sorted by priority (urgent first)."""
        from vozbot.dashboard.app import load_callback_tasks

        tasks = load_callback_tasks(session, sort_by="priority")

        assert len(tasks) == 4
        # Urgent should be first
        assert tasks[0]["priority"] == "URGENT"
        # Low should be last (or later)
        priorities = [t["priority"] for t in tasks]
        assert priorities.index("URGENT") < priorities.index("LOW")

    def test_load_callback_tasks_sort_by_created_at(
        self, session: Session, multiple_tasks: list[CallbackTask]
    ) -> None:
        """Test sorting tasks by created_at."""
        from vozbot.dashboard.app import load_callback_tasks

        tasks = load_callback_tasks(session, sort_by="created_at")

        assert len(tasks) == 4
        # Should have created_at values in descending order
        for i in range(len(tasks) - 1):
            assert tasks[i]["created_at"] >= tasks[i + 1]["created_at"]

    def test_load_callback_tasks_filter_by_status(
        self, session: Session, multiple_tasks: list[CallbackTask]
    ) -> None:
        """Test filtering tasks by status."""
        from vozbot.dashboard.app import load_callback_tasks

        # Filter for pending tasks
        pending_tasks = load_callback_tasks(session, status_filter="Pending")
        assert all(t["status"] == "pending" for t in pending_tasks)

        # Filter for completed tasks
        completed_tasks = load_callback_tasks(session, status_filter="Completed")
        assert all(t["status"] == "completed" for t in completed_tasks)


# -----------------------------------------------------------------------------
# Status Update Tests
# -----------------------------------------------------------------------------


class TestStatusUpdate:
    """Tests for task status updates."""

    def test_update_task_status(
        self, session: Session, sample_callback_task: CallbackTask
    ) -> None:
        """Test updating a task's status."""
        from vozbot.dashboard.app import update_task_status

        task_id = sample_callback_task.id
        assert sample_callback_task.status == TaskStatus.PENDING

        # Update to completed
        result = update_task_status(session, task_id, TaskStatus.COMPLETED)

        assert result is True

        # Verify the update
        session.refresh(sample_callback_task)
        assert sample_callback_task.status == TaskStatus.COMPLETED

    def test_update_task_status_invalid_id(self, session: Session) -> None:
        """Test updating a non-existent task returns False."""
        from vozbot.dashboard.app import update_task_status

        fake_id = str(uuid4())
        result = update_task_status(session, fake_id, TaskStatus.COMPLETED)

        assert result is False


# -----------------------------------------------------------------------------
# Helper Function Tests
# -----------------------------------------------------------------------------


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_format_time(self) -> None:
        """Test datetime formatting."""
        from vozbot.dashboard.app import format_time

        # Test with None
        assert format_time(None) == "-"

        # Test with datetime
        dt = datetime(2024, 1, 15, 14, 30, 0, tzinfo=UTC)
        formatted = format_time(dt)
        assert "Jan" in formatted
        assert "15" in formatted
        assert "2024" in formatted

    def test_priority_badge(self) -> None:
        """Test priority badge generation."""
        from vozbot.dashboard.app import priority_badge

        # Test urgent badge (should be red)
        urgent = priority_badge("URGENT")
        assert "#dc3545" in urgent  # Red color
        assert "URGENT" in urgent

        # Test normal badge (should be blue)
        normal = priority_badge("NORMAL")
        assert "#0d6efd" in normal  # Blue color
        assert "NORMAL" in normal

    def test_status_badge(self) -> None:
        """Test status badge generation."""
        from vozbot.dashboard.app import status_badge

        # Test pending badge (should be yellow)
        pending = status_badge("pending")
        assert "#ffc107" in pending  # Yellow color
        assert "PENDING" in pending

        # Test completed badge (should be green)
        completed = status_badge("completed")
        assert "#198754" in completed  # Green color
        assert "COMPLETED" in completed

    def test_get_database_url_converts_async(self) -> None:
        """Test that async database URLs are converted to sync."""
        from vozbot.dashboard.app import get_database_url

        # Set async URL
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db"},
        ):
            url = get_database_url()
            assert url.startswith("postgresql://")
            assert "asyncpg" not in url

    def test_get_database_url_preserves_sync(self) -> None:
        """Test that sync database URLs are preserved."""
        from vozbot.dashboard.app import get_database_url

        # Set sync URL
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://user:pass@localhost/db"},
        ):
            url = get_database_url()
            assert url == "postgresql://user:pass@localhost/db"

    def test_get_dashboard_password_default(self) -> None:
        """Test default dashboard password."""
        from vozbot.dashboard.app import get_dashboard_password

        # Clear environment variable
        with patch.dict(os.environ, {}, clear=True):
            password = get_dashboard_password()
            assert password == "vozbot2024"

    def test_get_dashboard_password_custom(self) -> None:
        """Test custom dashboard password from environment."""
        from vozbot.dashboard.app import get_dashboard_password

        with patch.dict(os.environ, {"DASHBOARD_PASSWORD": "custom123"}):
            password = get_dashboard_password()
            assert password == "custom123"


# -----------------------------------------------------------------------------
# Integration-style Tests (without Streamlit runtime)
# -----------------------------------------------------------------------------


class TestDashboardIntegration:
    """Integration tests for dashboard data flow."""

    def test_full_task_workflow(
        self, session: Session, sample_call: Call
    ) -> None:
        """Test creating a task, loading it, and marking complete."""
        from vozbot.dashboard.app import load_callback_tasks, update_task_status

        # Create a task
        task = CallbackTask(
            id=str(uuid4()),
            call_id=sample_call.id,
            priority=TaskPriority.URGENT,
            name="Workflow Test",
            callback_number="+15551112222",
            status=TaskStatus.PENDING,
        )
        session.add(task)
        session.commit()

        # Load tasks
        tasks = load_callback_tasks(session)
        assert len(tasks) == 1
        assert tasks[0]["name"] == "Workflow Test"
        assert tasks[0]["status"] == "pending"

        # Mark as complete
        result = update_task_status(session, task.id, TaskStatus.COMPLETED)
        assert result is True

        # Verify update
        tasks = load_callback_tasks(session)
        assert tasks[0]["status"] == "completed"

    def test_multiple_status_transitions(
        self, session: Session, sample_callback_task: CallbackTask
    ) -> None:
        """Test multiple status transitions."""
        from vozbot.dashboard.app import update_task_status

        task_id = sample_callback_task.id

        # Pending -> In Progress
        update_task_status(session, task_id, TaskStatus.IN_PROGRESS)
        session.refresh(sample_callback_task)
        assert sample_callback_task.status == TaskStatus.IN_PROGRESS

        # In Progress -> Completed
        update_task_status(session, task_id, TaskStatus.COMPLETED)
        session.refresh(sample_callback_task)
        assert sample_callback_task.status == TaskStatus.COMPLETED

    def test_task_data_includes_call_info(
        self, session: Session, sample_callback_task: CallbackTask
    ) -> None:
        """Test that loaded tasks include associated call information."""
        from vozbot.dashboard.app import load_callback_tasks

        tasks = load_callback_tasks(session)

        assert len(tasks) == 1
        task = tasks[0]

        # Check task fields
        assert task["name"] == "John Doe"
        assert task["phone"] == "+15559999999"

        # Check call fields are included
        assert "transcript" in task
        assert "summary" in task
        assert "call_intent" in task
        assert "language" in task

        # Verify call data values
        assert "Hello" in task["transcript"]
        assert "insurance" in task["summary"].lower()
