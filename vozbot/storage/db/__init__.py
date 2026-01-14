"""Database models and connection management."""

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
    CallbackTaskWithCall,
    CallCreate,
    CallResponse,
    CallUpdate,
    CallWithTask,
    CreateCallbackTaskInput,
    CreateCallRecordInput,
    UpdateCallRecordInput,
)

__all__ = [
    # Models
    "Base",
    "Call",
    "CallbackTask",
    # Enums
    "Language",
    "CustomerType",
    "CallStatus",
    "TaskStatus",
    "TaskPriority",
    # Pydantic Schemas
    "CallCreate",
    "CallUpdate",
    "CallResponse",
    "CallWithTask",
    "CallbackTaskCreate",
    "CallbackTaskUpdate",
    "CallbackTaskResponse",
    "CallbackTaskWithCall",
    # Tool Schemas
    "CreateCallRecordInput",
    "UpdateCallRecordInput",
    "CreateCallbackTaskInput",
]
