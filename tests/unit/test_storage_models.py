"""Tests for SQLAlchemy models and Pydantic schemas.

Verifies model constraints (not null, foreign keys), enum validations,
and Pydantic schema serialization.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
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
from vozbot.storage.db.schemas import (
    CallbackTaskCreate,
    CallbackTaskResponse,
    CallbackTaskUpdate,
    CallCreate,
    CallResponse,
    CallUpdate,
    CallWithTask,
    CreateCallbackTaskInput,
    CreateCallRecordInput,
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


# -----------------------------------------------------------------------------
# Model Tests
# -----------------------------------------------------------------------------


class TestCallModel:
    """Tests for the Call model."""

    def test_create_call_minimal(self, session: Session) -> None:
        """Test creating a call with only required fields."""
        call = Call(from_number="+15551234567")
        session.add(call)
        session.commit()
        session.refresh(call)

        assert call.id is not None
        assert call.from_number == "+15551234567"
        assert call.status == CallStatus.INIT
        assert call.language is None
        assert call.customer_type is None
        assert call.created_at is not None
        assert call.updated_at is not None

    def test_create_call_full(self, session: Session) -> None:
        """Test creating a call with all fields populated."""
        call = Call(
            from_number="+15559876543",
            language=Language.ES,
            customer_type=CustomerType.EXISTING,
            intent="Pregunta sobre poliza existente",
            status=CallStatus.COMPLETED,
            summary="Cliente existente con pregunta sobre su poliza.",
            transcript="Agente: Hola... Cliente: Tengo una pregunta...",
            costs={"stt": 0.05, "tts": 0.03, "llm": 0.08, "telephony": 0.02},
        )
        session.add(call)
        session.commit()
        session.refresh(call)

        assert call.language == Language.ES
        assert call.customer_type == CustomerType.EXISTING
        assert call.intent == "Pregunta sobre poliza existente"
        assert call.costs["llm"] == 0.08

    def test_call_from_number_required(self, session: Session) -> None:
        """Test that from_number is required (not null constraint)."""
        call = Call()  # Missing from_number
        session.add(call)

        with pytest.raises(IntegrityError):
            session.commit()

    def test_call_status_default(self, session: Session) -> None:
        """Test that status defaults to INIT."""
        call = Call(from_number="+15551111111")
        session.add(call)
        session.commit()
        session.refresh(call)

        assert call.status == CallStatus.INIT

    def test_call_enum_values(self, session: Session) -> None:
        """Test that all enum values work correctly."""
        # Test all Language values
        for lang in Language:
            call = Call(from_number="+15550000001", language=lang)
            session.add(call)
            session.commit()
            assert call.language == lang
            session.delete(call)
            session.commit()

        # Test all CustomerType values
        for ct in CustomerType:
            call = Call(from_number="+15550000002", customer_type=ct)
            session.add(call)
            session.commit()
            assert call.customer_type == ct
            session.delete(call)
            session.commit()

        # Test all CallStatus values
        for status in CallStatus:
            call = Call(from_number="+15550000003", status=status)
            session.add(call)
            session.commit()
            assert call.status == status
            session.delete(call)
            session.commit()

    def test_call_repr(self, session: Session) -> None:
        """Test Call string representation."""
        call = Call(from_number="+15551234567", status=CallStatus.GREET)
        session.add(call)
        session.commit()

        repr_str = repr(call)
        assert "Call" in repr_str
        assert call.id in repr_str
        assert "+15551234567" in repr_str


class TestCallbackTaskModel:
    """Tests for the CallbackTask model."""

    def test_create_callback_task(self, session: Session, sample_call: Call) -> None:
        """Test creating a callback task linked to a call."""
        task = CallbackTask(
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

        assert task.id is not None
        assert task.call_id == sample_call.id
        assert task.priority == TaskPriority.HIGH
        assert task.assignee == "Mom"
        assert task.status == TaskStatus.PENDING

    def test_callback_task_defaults(self, session: Session, sample_call: Call) -> None:
        """Test callback task default values."""
        task = CallbackTask(
            call_id=sample_call.id,
            callback_number="+15558888888",
        )
        session.add(task)
        session.commit()
        session.refresh(task)

        assert task.priority == TaskPriority.NORMAL
        assert task.status == TaskStatus.PENDING
        assert task.assignee is None
        assert task.name is None

    def test_callback_task_requires_call_id(self, session: Session) -> None:
        """Test that call_id is required (not null constraint)."""
        task = CallbackTask(callback_number="+15557777777")
        session.add(task)

        with pytest.raises(IntegrityError):
            session.commit()

    def test_callback_task_requires_callback_number(
        self, session: Session, sample_call: Call
    ) -> None:
        """Test that callback_number is required (not null constraint)."""
        task = CallbackTask(call_id=sample_call.id)
        session.add(task)

        with pytest.raises(IntegrityError):
            session.commit()

    def test_callback_task_foreign_key_constraint(self, session: Session) -> None:
        """Test that callback task requires valid call_id (FK constraint)."""
        fake_call_id = str(uuid4())
        task = CallbackTask(
            call_id=fake_call_id,
            callback_number="+15556666666",
        )
        session.add(task)

        with pytest.raises(IntegrityError):
            session.commit()

    def test_callback_task_unique_per_call(
        self, session: Session, sample_call: Call
    ) -> None:
        """Test that only one callback task can exist per call."""
        task1 = CallbackTask(
            call_id=sample_call.id,
            callback_number="+15551111111",
        )
        session.add(task1)
        session.commit()

        task2 = CallbackTask(
            call_id=sample_call.id,  # Same call_id
            callback_number="+15552222222",
        )
        session.add(task2)

        with pytest.raises(IntegrityError):
            session.commit()

    def test_callback_task_cascade_delete(
        self, session: Session, sample_call: Call
    ) -> None:
        """Test that deleting a call cascades to delete the callback task."""
        task = CallbackTask(
            call_id=sample_call.id,
            callback_number="+15553333333",
        )
        session.add(task)
        session.commit()
        task_id = task.id

        # Delete the call
        session.delete(sample_call)
        session.commit()

        # Task should be deleted too
        deleted_task = session.get(CallbackTask, task_id)
        assert deleted_task is None

    def test_callback_task_enum_values(
        self, session: Session, sample_call: Call
    ) -> None:
        """Test all TaskStatus and TaskPriority enum values."""
        # Test all TaskStatus values
        for status in TaskStatus:
            task = CallbackTask(
                call_id=sample_call.id,
                callback_number="+15550000001",
                status=status,
            )
            session.add(task)
            session.commit()
            assert task.status == status
            session.delete(task)
            session.commit()

        # Test all TaskPriority values
        for priority in TaskPriority:
            task = CallbackTask(
                call_id=sample_call.id,
                callback_number="+15550000002",
                priority=priority,
            )
            session.add(task)
            session.commit()
            assert task.priority == priority
            session.delete(task)
            session.commit()


class TestModelRelationships:
    """Tests for model relationships."""

    def test_call_to_task_relationship(
        self, session: Session, sample_call: Call
    ) -> None:
        """Test Call -> CallbackTask relationship."""
        task = CallbackTask(
            call_id=sample_call.id,
            callback_number="+15554444444",
            name="Jane Doe",
        )
        session.add(task)
        session.commit()

        # Access task through call relationship
        session.refresh(sample_call)
        assert sample_call.callback_task is not None
        assert sample_call.callback_task.name == "Jane Doe"

    def test_task_to_call_relationship(
        self, session: Session, sample_call: Call
    ) -> None:
        """Test CallbackTask -> Call relationship."""
        task = CallbackTask(
            call_id=sample_call.id,
            callback_number="+15555555555",
        )
        session.add(task)
        session.commit()
        session.refresh(task)

        # Access call through task relationship
        assert task.call is not None
        assert task.call.id == sample_call.id
        assert task.call.from_number == "+15551234567"


# -----------------------------------------------------------------------------
# Pydantic Schema Tests
# -----------------------------------------------------------------------------


class TestCallSchemas:
    """Tests for Call Pydantic schemas."""

    def test_call_create_schema(self) -> None:
        """Test CallCreate schema validation."""
        call_data = CallCreate(
            from_number="+15551234567",
            language=Language.EN,
            customer_type=CustomerType.NEW,
            intent="Get insurance quote",
            status=CallStatus.INIT,
        )
        assert call_data.from_number == "+15551234567"
        assert call_data.language == Language.EN

    def test_call_create_minimal(self) -> None:
        """Test CallCreate with only required fields."""
        call_data = CallCreate(from_number="+15559876543")
        assert call_data.from_number == "+15559876543"
        assert call_data.status == CallStatus.INIT

    def test_call_create_invalid_phone(self) -> None:
        """Test CallCreate rejects invalid phone numbers."""
        with pytest.raises(ValidationError) as exc_info:
            CallCreate(from_number="not-a-phone")

        assert "Phone number" in str(exc_info.value)

    def test_call_create_empty_phone(self) -> None:
        """Test CallCreate rejects empty phone numbers."""
        with pytest.raises(ValidationError):
            CallCreate(from_number="")

    def test_call_update_schema(self) -> None:
        """Test CallUpdate schema for partial updates."""
        update_data = CallUpdate(
            status=CallStatus.COMPLETED,
            summary="Call completed successfully.",
        )
        assert update_data.status == CallStatus.COMPLETED
        assert update_data.language is None  # Not provided

    def test_call_update_extra_fields_rejected(self) -> None:
        """Test CallUpdate rejects extra fields."""
        with pytest.raises(ValidationError):
            CallUpdate(status=CallStatus.COMPLETED, unknown_field="test")

    def test_call_response_from_model(self, session: Session) -> None:
        """Test CallResponse serializes from SQLAlchemy model."""
        call = Call(
            from_number="+15551234567",
            language=Language.ES,
            status=CallStatus.COMPLETED,
        )
        session.add(call)
        session.commit()
        session.refresh(call)

        response = CallResponse.model_validate(call)
        assert response.id == call.id
        assert response.from_number == "+15551234567"
        assert response.language == Language.ES

    def test_call_with_task_serialization(
        self, session: Session, sample_call: Call
    ) -> None:
        """Test CallWithTask includes nested task."""
        task = CallbackTask(
            call_id=sample_call.id,
            callback_number="+15559999999",
            name="Test User",
        )
        session.add(task)
        session.commit()
        session.refresh(sample_call)

        response = CallWithTask.model_validate(sample_call)
        assert response.callback_task is not None
        assert response.callback_task.name == "Test User"


class TestCallbackTaskSchemas:
    """Tests for CallbackTask Pydantic schemas."""

    def test_callback_task_create(self) -> None:
        """Test CallbackTaskCreate schema validation."""
        task_data = CallbackTaskCreate(
            call_id=str(uuid4()),
            priority=TaskPriority.HIGH,
            name="John Doe",
            callback_number="+15551234567",
            best_time_window="Afternoon",
            notes="Prefers Spanish",
            status=TaskStatus.PENDING,
        )
        assert task_data.priority == TaskPriority.HIGH
        assert task_data.name == "John Doe"

    def test_callback_task_create_minimal(self) -> None:
        """Test CallbackTaskCreate with only required fields."""
        task_data = CallbackTaskCreate(
            call_id=str(uuid4()),
            callback_number="+15559876543",
        )
        assert task_data.priority == TaskPriority.NORMAL
        assert task_data.status == TaskStatus.PENDING

    def test_callback_task_create_invalid_phone(self) -> None:
        """Test CallbackTaskCreate rejects invalid callback numbers."""
        with pytest.raises(ValidationError):
            CallbackTaskCreate(
                call_id=str(uuid4()),
                callback_number="invalid-number",
            )

    def test_callback_task_update(self) -> None:
        """Test CallbackTaskUpdate schema for partial updates."""
        update_data = CallbackTaskUpdate(
            status=TaskStatus.COMPLETED,
            assignee="Dad",
        )
        assert update_data.status == TaskStatus.COMPLETED
        assert update_data.assignee == "Dad"
        assert update_data.priority is None

    def test_callback_task_response_from_model(
        self, session: Session, sample_call: Call
    ) -> None:
        """Test CallbackTaskResponse serializes from SQLAlchemy model."""
        task = CallbackTask(
            call_id=sample_call.id,
            callback_number="+15551111111",
            priority=TaskPriority.URGENT,
            name="Urgent Customer",
        )
        session.add(task)
        session.commit()
        session.refresh(task)

        response = CallbackTaskResponse.model_validate(task)
        assert response.id == task.id
        assert response.priority == TaskPriority.URGENT
        assert response.name == "Urgent Customer"


class TestToolSchemas:
    """Tests for LLM tool input schemas."""

    def test_create_call_record_input(self) -> None:
        """Test CreateCallRecordInput validation."""
        input_data = CreateCallRecordInput(
            from_number="+15551234567",
            language=Language.EN,
            customer_type=CustomerType.NEW,
            intent="Get auto insurance quote",
            status=CallStatus.COMPLETED,
            transcript="Full transcript here...",
            summary="Customer wants auto insurance quote.",
        )
        assert input_data.language == Language.EN
        assert input_data.customer_type == CustomerType.NEW

    def test_create_callback_task_input(self) -> None:
        """Test CreateCallbackTaskInput validation."""
        input_data = CreateCallbackTaskInput(
            call_id=str(uuid4()),
            priority=TaskPriority.HIGH,
            name="Test Customer",
            callback_number="+15559999999",
            best_time_window="Morning",
            notes="Spanish speaking customer",
        )
        assert input_data.priority == TaskPriority.HIGH
        assert input_data.best_time_window == "Morning"


# -----------------------------------------------------------------------------
# Enum Tests
# -----------------------------------------------------------------------------


class TestEnums:
    """Tests for enum types."""

    def test_language_values(self) -> None:
        """Test Language enum has expected values."""
        assert Language.EN.value == "en"
        assert Language.ES.value == "es"
        assert len(Language) == 2

    def test_customer_type_values(self) -> None:
        """Test CustomerType enum has expected values."""
        assert CustomerType.NEW.value == "new"
        assert CustomerType.EXISTING.value == "existing"
        assert CustomerType.UNKNOWN.value == "unknown"
        assert len(CustomerType) == 3

    def test_call_status_includes_state_machine_states(self) -> None:
        """Test CallStatus includes all state machine states from README."""
        expected_states = {
            "init",
            "greet",
            "language_select",
            "classify_customer_type",
            "intent_discovery",
            "info_collection",
            "confirmation",
            "create_callback_task",
            "transfer_or_wrapup",
            "end",
        }
        actual_states = {s.value for s in CallStatus}
        assert expected_states.issubset(actual_states)

    def test_task_status_values(self) -> None:
        """Test TaskStatus enum has expected values."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.CANCELLED.value == "cancelled"
        assert len(TaskStatus) == 4

    def test_task_priority_ordering(self) -> None:
        """Test TaskPriority enum has correct numeric ordering."""
        assert TaskPriority.LOW.value < TaskPriority.NORMAL.value
        assert TaskPriority.NORMAL.value < TaskPriority.HIGH.value
        assert TaskPriority.HIGH.value < TaskPriority.URGENT.value
