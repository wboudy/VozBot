"""Pydantic schemas for LLM tool calling.

Defines the input schemas for all tools that the LLM can call.
Schemas include validation and can auto-generate OpenAI function schemas.

SECURITY NOTE: No sensitive fields (SSN, DOB, payment info) are allowed.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Language(str, Enum):
    """Supported languages for calls."""

    EN = "en"
    ES = "es"


class CustomerType(str, Enum):
    """Type of customer on the call."""

    NEW = "new"
    EXISTING = "existing"
    UNKNOWN = "unknown"


class CallStatus(str, Enum):
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
    COMPLETED = "completed"
    TRANSFERRED = "transferred"
    FAILED = "failed"


class TaskPriority(str, Enum):
    """Priority levels for callback tasks."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


# Blocklist of sensitive field patterns
SENSITIVE_FIELD_PATTERNS = [
    "ssn",
    "social_security",
    "dob",
    "date_of_birth",
    "birth_date",
    "birthdate",
    "credit_card",
    "card_number",
    "cvv",
    "expiry",
    "payment",
    "bank_account",
    "routing_number",
    "pin",
    "password",
]


def validate_no_sensitive_data(value: str, field_name: str) -> str:
    """Validate that field values don't contain sensitive data patterns.

    Args:
        value: The value to check.
        field_name: Name of the field being validated.

    Returns:
        The validated value.

    Raises:
        ValueError: If sensitive data pattern detected.
    """
    lower_value = value.lower()
    for pattern in SENSITIVE_FIELD_PATTERNS:
        if pattern in lower_value:
            raise ValueError(
                f"Field '{field_name}' appears to contain sensitive information. "
                f"Do not collect SSN, DOB, or payment information."
            )
    return value


class CreateCallRecord(BaseModel):
    """Schema for creating a new call record.

    Used by the LLM to create a record of the call with
    essential information about the caller and their intent.

    Note: Does NOT include any sensitive fields (SSN, DOB, payment info).
    """

    model_config = ConfigDict(extra="forbid")

    from_number: str = Field(
        ...,
        description="The caller's phone number in E.164 format (e.g., +15551234567)",
        min_length=10,
        max_length=20,
    )
    language: Language = Field(
        ...,
        description="The language selected by the caller (en or es)",
    )
    customer_type: CustomerType = Field(
        ...,
        description="Whether caller is new, existing, or unknown customer",
    )
    intent: str = Field(
        ...,
        description="The caller's stated intent/reason for calling",
        min_length=1,
        max_length=1000,
    )
    status: CallStatus = Field(
        default=CallStatus.INIT,
        description="Current status of the call",
    )

    @field_validator("from_number")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        """Validate phone number format."""
        v = v.strip()
        if not v:
            raise ValueError("Phone number cannot be empty")
        # Allow + prefix and digits only
        cleaned = v.lstrip("+")
        if not cleaned.replace("-", "").replace(" ", "").isdigit():
            raise ValueError("Phone number must contain only digits, +, -, and spaces")
        return v

    @field_validator("intent")
    @classmethod
    def validate_intent(cls, v: str) -> str:
        """Validate intent doesn't contain sensitive data."""
        return validate_no_sensitive_data(v, "intent")


class UpdateCallRecord(BaseModel):
    """Schema for updating an existing call record.

    All fields are optional to allow partial updates.
    """

    model_config = ConfigDict(extra="forbid")

    call_id: str = Field(
        ...,
        description="The UUID of the call record to update",
    )
    language: Language | None = Field(
        default=None,
        description="Updated language preference",
    )
    customer_type: CustomerType | None = Field(
        default=None,
        description="Updated customer type classification",
    )
    intent: str | None = Field(
        default=None,
        description="Updated intent/reason for calling",
        max_length=1000,
    )
    status: CallStatus | None = Field(
        default=None,
        description="Updated call status",
    )
    summary: str | None = Field(
        default=None,
        description="AI-generated summary of the call",
        max_length=5000,
    )
    transcript: str | None = Field(
        default=None,
        description="Full transcript of the conversation",
    )

    @field_validator("intent")
    @classmethod
    def validate_intent(cls, v: str | None) -> str | None:
        """Validate intent doesn't contain sensitive data."""
        if v is None:
            return v
        return validate_no_sensitive_data(v, "intent")

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, v: str | None) -> str | None:
        """Validate summary doesn't contain sensitive data."""
        if v is None:
            return v
        return validate_no_sensitive_data(v, "summary")


class CreateCallbackTask(BaseModel):
    """Schema for creating a callback task for office staff.

    Creates a task that notifies Mom/Dad to call back the customer.

    Note: Does NOT include any sensitive fields (SSN, DOB, payment info).
    """

    model_config = ConfigDict(extra="forbid")

    call_id: str = Field(
        ...,
        description="The UUID of the associated call record",
    )
    priority: TaskPriority = Field(
        default=TaskPriority.NORMAL,
        description="Priority of the callback task (low, normal, high, urgent)",
    )
    name: str | None = Field(
        default=None,
        description="The caller's name",
        max_length=200,
    )
    callback_number: str = Field(
        ...,
        description="Phone number to call back in E.164 format",
        min_length=10,
        max_length=20,
    )
    best_time_window: str | None = Field(
        default=None,
        description="Best time to call back (e.g., 'morning', 'afternoon', '9am-12pm')",
        max_length=100,
    )
    notes: str | None = Field(
        default=None,
        description="Additional notes about the callback request",
        max_length=2000,
    )

    @field_validator("callback_number")
    @classmethod
    def validate_callback_number(cls, v: str) -> str:
        """Validate callback phone number format."""
        v = v.strip()
        if not v:
            raise ValueError("Callback number cannot be empty")
        cleaned = v.lstrip("+")
        if not cleaned.replace("-", "").replace(" ", "").isdigit():
            raise ValueError("Callback number must contain only digits, +, -, and spaces")
        return v

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v: str | None) -> str | None:
        """Validate notes don't contain sensitive data."""
        if v is None:
            return v
        return validate_no_sensitive_data(v, "notes")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        """Validate name doesn't contain sensitive data patterns."""
        if v is None:
            return v
        return validate_no_sensitive_data(v, "name")


class TransferCall(BaseModel):
    """Schema for transferring a call to another number or queue.

    Used when escalation to a human is needed.
    """

    model_config = ConfigDict(extra="forbid")

    call_id: str = Field(
        ...,
        description="The UUID of the call to transfer",
    )
    target_number: str | None = Field(
        default=None,
        description="Phone number to transfer to (if direct transfer)",
        max_length=20,
    )
    queue_name: str | None = Field(
        default=None,
        description="Queue name to transfer to (if queue-based)",
        max_length=100,
    )
    reason: str = Field(
        ...,
        description="Reason for the transfer",
        max_length=500,
    )


class SendNotification(BaseModel):
    """Schema for sending a notification (SMS, email, etc.).

    Used to notify office staff about urgent matters.
    """

    model_config = ConfigDict(extra="forbid")

    call_id: str = Field(
        ...,
        description="The UUID of the associated call",
    )
    notification_type: str = Field(
        ...,
        description="Type of notification (sms, email)",
        pattern="^(sms|email)$",
    )
    recipient: str = Field(
        ...,
        description="Recipient phone number or email address",
        max_length=200,
    )
    message: str = Field(
        ...,
        description="Notification message content",
        max_length=1000,
    )

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        """Validate message doesn't contain sensitive data."""
        return validate_no_sensitive_data(v, "message")


def pydantic_to_openai_function_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Convert a Pydantic model to OpenAI function calling schema.

    Args:
        model: The Pydantic model class to convert.

    Returns:
        OpenAI-compatible function schema dict.

    Example:
        >>> schema = pydantic_to_openai_function_schema(CreateCallRecord)
        >>> # Returns dict with 'name', 'description', 'parameters'
    """
    json_schema = model.model_json_schema()

    # Extract required fields
    required = json_schema.get("required", [])

    # Build parameters schema
    properties = {}
    for prop_name, prop_schema in json_schema.get("properties", {}).items():
        # Clean up pydantic-specific fields
        cleaned_prop = {
            k: v
            for k, v in prop_schema.items()
            if k not in ("title", "default")  # Keep description, type, enum, etc.
        }

        # Handle enum types
        if "allOf" in cleaned_prop:
            # Pydantic puts enums in allOf with $ref
            for ref in cleaned_prop["allOf"]:
                if "$ref" in ref:
                    ref_name = ref["$ref"].split("/")[-1]
                    if ref_name in json_schema.get("$defs", {}):
                        enum_def = json_schema["$defs"][ref_name]
                        cleaned_prop = {
                            "type": "string",
                            "enum": enum_def.get("enum", []),
                            "description": prop_schema.get("description", ""),
                        }
                        break

        # Handle anyOf (for optional enum fields)
        if "anyOf" in cleaned_prop:
            for option in cleaned_prop["anyOf"]:
                if "$ref" in option:
                    ref_name = option["$ref"].split("/")[-1]
                    if ref_name in json_schema.get("$defs", {}):
                        enum_def = json_schema["$defs"][ref_name]
                        cleaned_prop = {
                            "type": "string",
                            "enum": enum_def.get("enum", []),
                            "description": prop_schema.get("description", ""),
                        }
                        break
                elif option.get("type") != "null":
                    cleaned_prop = option.copy()
                    cleaned_prop["description"] = prop_schema.get("description", "")
                    break

        properties[prop_name] = cleaned_prop

    # Get model docstring for description
    description = model.__doc__ or f"Schema for {model.__name__}"
    # Clean up the docstring - take first paragraph
    description = description.strip().split("\n\n")[0].replace("\n", " ").strip()

    return {
        "name": _camel_to_snake(model.__name__),
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


def _camel_to_snake(name: str) -> str:
    """Convert CamelCase to snake_case.

    Args:
        name: CamelCase string.

    Returns:
        snake_case string.
    """
    import re

    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


# Pre-generated OpenAI function schemas for all tools
TOOL_SCHEMAS = {
    "create_call_record": pydantic_to_openai_function_schema(CreateCallRecord),
    "update_call_record": pydantic_to_openai_function_schema(UpdateCallRecord),
    "create_callback_task": pydantic_to_openai_function_schema(CreateCallbackTask),
    "transfer_call": pydantic_to_openai_function_schema(TransferCall),
    "send_notification": pydantic_to_openai_function_schema(SendNotification),
}


def get_all_tool_schemas() -> list[dict[str, Any]]:
    """Get all tool schemas in OpenAI function calling format.

    Returns:
        List of tool schema dicts.
    """
    return [
        {"type": "function", "function": schema}
        for schema in TOOL_SCHEMAS.values()
    ]
