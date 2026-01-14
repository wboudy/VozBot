"""Pydantic schemas for API serialization of storage models.

Provides validation and serialization for Call and CallbackTask
entities, matching the SQLAlchemy models in models.py.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from vozbot.storage.db.models import (
    CallStatus,
    CustomerType,
    Language,
    TaskPriority,
    TaskStatus,
)

# -----------------------------------------------------------------------------
# Base Schemas
# -----------------------------------------------------------------------------


class TimestampMixin(BaseModel):
    """Mixin providing timestamp fields for models."""

    created_at: datetime
    updated_at: datetime


# -----------------------------------------------------------------------------
# Call Schemas
# -----------------------------------------------------------------------------


class CallBase(BaseModel):
    """Base schema for Call with common fields."""

    from_number: str = Field(..., min_length=1, max_length=20, description="Caller phone number")
    language: Language | None = Field(None, description="Detected or selected language (en/es)")
    customer_type: CustomerType | None = Field(None, description="Customer classification")
    intent: str | None = Field(None, description="Extracted call intent")
    status: CallStatus = Field(CallStatus.INIT, description="Current call status")
    summary: str | None = Field(None, description="AI-generated call summary")
    transcript: str | None = Field(None, description="Full conversation transcript")
    costs: dict[str, Any] | None = Field(None, description="Cost breakdown (STT, TTS, LLM, etc.)")

    @field_validator("from_number")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        """Basic phone number validation."""
        # Strip whitespace
        v = v.strip()
        if not v:
            raise ValueError("Phone number cannot be empty")
        # Allow + prefix and digits only (basic validation)
        cleaned = v.lstrip("+")
        if not cleaned.replace("-", "").replace(" ", "").isdigit():
            raise ValueError("Phone number must contain only digits, +, -, and spaces")
        return v


class CallCreate(CallBase):
    """Schema for creating a new Call."""

    # Override to make some fields optional at creation time
    status: CallStatus = Field(CallStatus.INIT, description="Initial call status")


class CallUpdate(BaseModel):
    """Schema for updating an existing Call (partial update)."""

    language: Language | None = None
    customer_type: CustomerType | None = None
    intent: str | None = None
    status: CallStatus | None = None
    summary: str | None = None
    transcript: str | None = None
    costs: dict[str, Any] | None = None

    model_config = ConfigDict(extra="forbid")


class CallResponse(CallBase, TimestampMixin):
    """Schema for Call responses (includes id and timestamps)."""

    id: str = Field(..., description="Unique call identifier (UUID)")

    model_config = ConfigDict(from_attributes=True)


class CallWithTask(CallResponse):
    """Schema for Call responses including the callback task."""

    callback_task: CallbackTaskResponse | None = None

    model_config = ConfigDict(from_attributes=True)


# -----------------------------------------------------------------------------
# CallbackTask Schemas
# -----------------------------------------------------------------------------


class CallbackTaskBase(BaseModel):
    """Base schema for CallbackTask with common fields."""

    priority: TaskPriority = Field(TaskPriority.NORMAL, description="Task priority level")
    assignee: str | None = Field(None, max_length=100, description="Assigned staff member")
    name: str | None = Field(None, max_length=200, description="Caller name")
    callback_number: str = Field(
        ..., min_length=1, max_length=20, description="Number to call back"
    )
    best_time_window: str | None = Field(
        None, max_length=100, description="Best time window for callback"
    )
    notes: str | None = Field(None, description="Additional notes")
    status: TaskStatus = Field(TaskStatus.PENDING, description="Task status")

    @field_validator("callback_number")
    @classmethod
    def validate_callback_number(cls, v: str) -> str:
        """Basic phone number validation for callback number."""
        v = v.strip()
        if not v:
            raise ValueError("Callback number cannot be empty")
        cleaned = v.lstrip("+")
        if not cleaned.replace("-", "").replace(" ", "").isdigit():
            raise ValueError("Callback number must contain only digits, +, -, and spaces")
        return v


class CallbackTaskCreate(CallbackTaskBase):
    """Schema for creating a new CallbackTask."""

    call_id: str = Field(..., description="ID of the associated call")


class CallbackTaskUpdate(BaseModel):
    """Schema for updating an existing CallbackTask (partial update)."""

    priority: TaskPriority | None = None
    assignee: str | None = None
    name: str | None = None
    callback_number: str | None = None
    best_time_window: str | None = None
    notes: str | None = None
    status: TaskStatus | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("callback_number")
    @classmethod
    def validate_callback_number(cls, v: str | None) -> str | None:
        """Basic phone number validation for callback number."""
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Callback number cannot be empty")
        cleaned = v.lstrip("+")
        if not cleaned.replace("-", "").replace(" ", "").isdigit():
            raise ValueError("Callback number must contain only digits, +, -, and spaces")
        return v


class CallbackTaskResponse(CallbackTaskBase, TimestampMixin):
    """Schema for CallbackTask responses (includes id and timestamps)."""

    id: str = Field(..., description="Unique task identifier (UUID)")
    call_id: str = Field(..., description="ID of the associated call")

    model_config = ConfigDict(from_attributes=True)


class CallbackTaskWithCall(CallbackTaskResponse):
    """Schema for CallbackTask responses including the parent call."""

    call: CallResponse

    model_config = ConfigDict(from_attributes=True)


# -----------------------------------------------------------------------------
# Tool Schemas (for LLM tool calling)
# -----------------------------------------------------------------------------


class CreateCallRecordInput(BaseModel):
    """Input schema for create_call_record tool."""

    from_number: str = Field(..., description="Caller phone number")
    language: Language = Field(..., description="Language (en or es)")
    customer_type: CustomerType = Field(..., description="Customer type classification")
    intent: str = Field(..., description="Call intent extracted from conversation")
    status: CallStatus = Field(..., description="Call status")
    transcript: str = Field(..., description="Full conversation transcript")
    summary: str = Field(..., description="AI-generated call summary")


class UpdateCallRecordInput(BaseModel):
    """Input schema for update_call_record tool."""

    call_id: str = Field(..., description="ID of the call to update")
    language: Language | None = None
    customer_type: CustomerType | None = None
    intent: str | None = None
    status: CallStatus | None = None
    transcript: str | None = None
    summary: str | None = None
    costs: dict[str, Any] | None = None


class CreateCallbackTaskInput(BaseModel):
    """Input schema for create_callback_task tool."""

    call_id: str = Field(..., description="ID of the associated call")
    priority: TaskPriority = Field(TaskPriority.NORMAL, description="Task priority")
    name: str | None = Field(None, description="Caller name")
    callback_number: str = Field(..., description="Number to call back")
    best_time_window: str | None = Field(None, description="Best time to call back")
    notes: str | None = Field(None, description="Additional notes")


# Fix forward reference for CallWithTask
CallWithTask.model_rebuild()
