"""SQLAlchemy models for VozBot storage layer.

Defines the Call and CallbackTask models with proper relationships,
enums, indexes, and constraints per the README data model spec.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from typing import Any


class Language(str, enum.Enum):
    """Supported languages for calls."""

    EN = "en"
    ES = "es"


class CustomerType(str, enum.Enum):
    """Type of customer on the call."""

    NEW = "new"
    EXISTING = "existing"
    UNKNOWN = "unknown"


class CallStatus(str, enum.Enum):
    """Status of a call in the system."""

    INIT = "init"
    GREET = "greet"
    LANGUAGE_SELECT = "language_select"
    CLASSIFY_CUSTOMER_TYPE = "classify_customer_type"
    INTENT_DISCOVERY = "intent_discovery"
    INFO_COLLECTION = "info_collection"
    CONFIRMATION = "confirmation"
    CREATE_CALLBACK_TASK = "create_callback_task"
    TRANSFER_OR_WRAPUP = "transfer_or_wrapup"
    END = "end"
    # Additional terminal states
    COMPLETED = "completed"
    TRANSFERRED = "transferred"
    FAILED = "failed"


class TaskStatus(str, enum.Enum):
    """Status of a callback task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(int, enum.Enum):
    """Priority levels for callback tasks."""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class Call(Base):
    """Represents an inbound call handled by VozBot.

    Stores call metadata, transcript, summary, and cost information.
    Each call may have zero or one associated callback tasks.
    """

    __tablename__ = "calls"

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Caller information
    from_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Language detected or selected
    language: Mapped[Language | None] = mapped_column(
        Enum(Language, name="language_enum", create_constraint=True),
        nullable=True,
    )

    # Customer classification
    customer_type: Mapped[CustomerType | None] = mapped_column(
        Enum(CustomerType, name="customer_type_enum", create_constraint=True),
        nullable=True,
    )

    # Call intent extracted from conversation
    intent: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Current call status in state machine
    status: Mapped[CallStatus] = mapped_column(
        Enum(CallStatus, name="call_status_enum", create_constraint=True),
        nullable=False,
        default=CallStatus.INIT,
        index=True,
    )

    # AI-generated summary of the call
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Full transcript of the conversation
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Cost tracking (STT, TTS, LLM, telephony costs)
    costs: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    callback_task: Mapped[CallbackTask | None] = relationship(
        "CallbackTask",
        back_populates="call",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # Indexes defined via __table_args__
    __table_args__ = (
        Index("ix_calls_from_number_created_at", "from_number", "created_at"),
        Index("ix_calls_status_created_at", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Call(id={self.id}, from_number={self.from_number}, status={self.status})>"


class CallbackTask(Base):
    """Represents a callback task created for office staff.

    Created when VozBot completes a call and needs to notify
    Mom/Dad to call back the customer.
    """

    __tablename__ = "callback_tasks"

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Foreign key to the call that generated this task
    call_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("calls.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # One task per call
    )

    # Task priority
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority, name="task_priority_enum", create_constraint=True),
        nullable=False,
        default=TaskPriority.NORMAL,
    )

    # Staff member assigned (optional - can be assigned later)
    assignee: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Caller's name
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Number to call back
    callback_number: Mapped[str] = mapped_column(String(20), nullable=False)

    # Best time window for callback (e.g., "morning", "afternoon", "9am-12pm")
    best_time_window: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Additional notes from the call
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Task status
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status_enum", create_constraint=True),
        nullable=False,
        default=TaskStatus.PENDING,
        index=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    call: Mapped[Call] = relationship("Call", back_populates="callback_task")

    # Indexes
    __table_args__ = (
        Index("ix_callback_tasks_status_priority", "status", "priority"),
        Index("ix_callback_tasks_assignee_status", "assignee", "status"),
    )

    def __repr__(self) -> str:
        return f"<CallbackTask(id={self.id}, call_id={self.call_id}, status={self.status})>"
