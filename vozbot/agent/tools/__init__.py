"""LLM tool definitions and handlers for VozBot agent."""

from .schemas import (
    CreateCallRecord,
    UpdateCallRecord,
    CreateCallbackTask,
    TransferCall,
    SendNotification,
    Language,
    CustomerType,
    CallStatus,
    TaskPriority,
    TOOL_SCHEMAS,
    get_all_tool_schemas,
    pydantic_to_openai_function_schema,
)
from .handlers import (
    HandlerResult,
    HandlerStatus,
    ToolHandler,
)

__all__ = [
    # Schemas
    "CreateCallRecord",
    "UpdateCallRecord",
    "CreateCallbackTask",
    "TransferCall",
    "SendNotification",
    "Language",
    "CustomerType",
    "CallStatus",
    "TaskPriority",
    "TOOL_SCHEMAS",
    "get_all_tool_schemas",
    "pydantic_to_openai_function_schema",
    # Handlers
    "HandlerResult",
    "HandlerStatus",
    "ToolHandler",
]
