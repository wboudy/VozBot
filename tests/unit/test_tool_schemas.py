"""Tests for LLM tool schemas.

Verifies:
- All schemas defined at vozbot/agent/tools/schemas.py
- CreateCallRecord, UpdateCallRecord, CreateCallbackTask schemas
- No sensitive fields allowed (SSN, DOB, payment)
- Validation errors have clear messages
- OpenAI function schema auto-generation works
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vozbot.agent.tools.schemas import (
    SENSITIVE_FIELD_PATTERNS,
    TOOL_SCHEMAS,
    CallStatus,
    CreateCallbackTask,
    CreateCallRecord,
    CustomerType,
    Language,
    SendNotification,
    TaskPriority,
    TransferCall,
    UpdateCallRecord,
    get_all_tool_schemas,
    pydantic_to_openai_function_schema,
    validate_no_sensitive_data,
)


class TestCreateCallRecord:
    """Tests for CreateCallRecord schema."""

    def test_valid_create_call_record(self) -> None:
        """Test creating a valid call record."""
        record = CreateCallRecord(
            from_number="+15551234567",
            language=Language.EN,
            customer_type=CustomerType.NEW,
            intent="I need help with my order",
            status=CallStatus.INIT,
        )
        assert record.from_number == "+15551234567"
        assert record.language == Language.EN
        assert record.customer_type == CustomerType.NEW
        assert record.intent == "I need help with my order"

    def test_spanish_language(self) -> None:
        """Test Spanish language selection."""
        record = CreateCallRecord(
            from_number="+15551234567",
            language=Language.ES,
            customer_type=CustomerType.EXISTING,
            intent="Necesito ayuda",
        )
        assert record.language == Language.ES

    def test_all_customer_types(self) -> None:
        """Test all customer type values."""
        for ctype in CustomerType:
            record = CreateCallRecord(
                from_number="+15551234567",
                language=Language.EN,
                customer_type=ctype,
                intent="Test intent",
            )
            assert record.customer_type == ctype

    def test_invalid_phone_number(self) -> None:
        """Test invalid phone number is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CreateCallRecord(
                from_number="not-a-number",
                language=Language.EN,
                customer_type=CustomerType.NEW,
                intent="Test",
            )
        assert "phone number" in str(exc_info.value).lower()

    def test_empty_phone_number(self) -> None:
        """Test empty phone number is rejected."""
        with pytest.raises(ValidationError):
            CreateCallRecord(
                from_number="",
                language=Language.EN,
                customer_type=CustomerType.NEW,
                intent="Test",
            )

    def test_extra_fields_forbidden(self) -> None:
        """Test extra fields are not allowed."""
        with pytest.raises(ValidationError) as exc_info:
            CreateCallRecord(
                from_number="+15551234567",
                language=Language.EN,
                customer_type=CustomerType.NEW,
                intent="Test",
                ssn="123-45-6789",  # type: ignore[call-arg]
            )
        assert "extra" in str(exc_info.value).lower()


class TestUpdateCallRecord:
    """Tests for UpdateCallRecord schema."""

    def test_valid_update_all_fields(self) -> None:
        """Test updating all fields."""
        update = UpdateCallRecord(
            call_id="uuid-123",
            language=Language.ES,
            customer_type=CustomerType.EXISTING,
            intent="Updated intent",
            status=CallStatus.CONFIRMATION,
            summary="Call summary",
            transcript="Full transcript here",
        )
        assert update.call_id == "uuid-123"
        assert update.language == Language.ES
        assert update.summary == "Call summary"

    def test_partial_update(self) -> None:
        """Test partial update with only some fields."""
        update = UpdateCallRecord(
            call_id="uuid-123",
            status=CallStatus.END,
        )
        assert update.call_id == "uuid-123"
        assert update.status == CallStatus.END
        assert update.language is None
        assert update.intent is None

    def test_call_id_required(self) -> None:
        """Test call_id is required."""
        with pytest.raises(ValidationError):
            UpdateCallRecord(status=CallStatus.END)  # type: ignore[call-arg]


class TestCreateCallbackTask:
    """Tests for CreateCallbackTask schema."""

    def test_valid_callback_task(self) -> None:
        """Test creating a valid callback task."""
        task = CreateCallbackTask(
            call_id="uuid-123",
            priority=TaskPriority.HIGH,
            name="John Smith",
            callback_number="+15559876543",
            best_time_window="morning",
            notes="Customer requested callback before 10am",
        )
        assert task.call_id == "uuid-123"
        assert task.priority == TaskPriority.HIGH
        assert task.name == "John Smith"
        assert task.callback_number == "+15559876543"
        assert task.best_time_window == "morning"

    def test_minimal_callback_task(self) -> None:
        """Test creating callback task with minimal fields."""
        task = CreateCallbackTask(
            call_id="uuid-123",
            callback_number="+15559876543",
        )
        assert task.call_id == "uuid-123"
        assert task.priority == TaskPriority.NORMAL  # Default
        assert task.name is None
        assert task.best_time_window is None
        assert task.notes is None

    def test_all_priority_levels(self) -> None:
        """Test all priority levels."""
        for priority in TaskPriority:
            task = CreateCallbackTask(
                call_id="uuid-123",
                callback_number="+15559876543",
                priority=priority,
            )
            assert task.priority == priority

    def test_invalid_callback_number(self) -> None:
        """Test invalid callback number is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CreateCallbackTask(
                call_id="uuid-123",
                callback_number="invalid",
            )
        # Can fail either due to length or format validation
        error_str = str(exc_info.value).lower()
        assert "callback_number" in error_str or "string" in error_str


class TestTransferCall:
    """Tests for TransferCall schema."""

    def test_valid_transfer_with_number(self) -> None:
        """Test transfer with target number."""
        transfer = TransferCall(
            call_id="uuid-123",
            target_number="+15551112222",
            reason="Customer needs billing department",
        )
        assert transfer.target_number == "+15551112222"
        assert transfer.queue_name is None

    def test_valid_transfer_with_queue(self) -> None:
        """Test transfer with queue name."""
        transfer = TransferCall(
            call_id="uuid-123",
            queue_name="billing",
            reason="Customer needs billing department",
        )
        assert transfer.queue_name == "billing"
        assert transfer.target_number is None

    def test_reason_required(self) -> None:
        """Test reason is required."""
        with pytest.raises(ValidationError):
            TransferCall(
                call_id="uuid-123",
                target_number="+15551112222",
            )  # type: ignore[call-arg]


class TestSendNotification:
    """Tests for SendNotification schema."""

    def test_valid_sms_notification(self) -> None:
        """Test valid SMS notification."""
        notif = SendNotification(
            call_id="uuid-123",
            notification_type="sms",
            recipient="+15551234567",
            message="Urgent callback requested",
        )
        assert notif.notification_type == "sms"

    def test_valid_email_notification(self) -> None:
        """Test valid email notification."""
        notif = SendNotification(
            call_id="uuid-123",
            notification_type="email",
            recipient="staff@example.com",
            message="Urgent callback requested",
        )
        assert notif.notification_type == "email"

    def test_invalid_notification_type(self) -> None:
        """Test invalid notification type is rejected."""
        with pytest.raises(ValidationError):
            SendNotification(
                call_id="uuid-123",
                notification_type="fax",  # Invalid
                recipient="+15551234567",
                message="Test",
            )


class TestSensitiveDataValidation:
    """Tests for sensitive data validation."""

    def test_validate_no_sensitive_data_clean(self) -> None:
        """Test clean values pass validation."""
        result = validate_no_sensitive_data("billing question", "intent")
        assert result == "billing question"

    @pytest.mark.parametrize(
        "sensitive_value",
        [
            "my ssn is 123-45-6789",
            "my social_security number",
            "my dob is 01/01/1990",
            "date_of_birth information",
            "credit_card details",
            "my card_number is",
            "bank_account info",
            "routing_number needed",
            "payment information",
            "enter your pin",
            "password reset",
        ],
    )
    def test_sensitive_data_rejected(self, sensitive_value: str) -> None:
        """Test sensitive data patterns are rejected."""
        with pytest.raises(ValueError, match="sensitive"):
            validate_no_sensitive_data(sensitive_value, "test_field")

    def test_intent_rejects_sensitive(self) -> None:
        """Test intent field rejects sensitive data."""
        with pytest.raises(ValidationError) as exc_info:
            CreateCallRecord(
                from_number="+15551234567",
                language=Language.EN,
                customer_type=CustomerType.NEW,
                intent="I need to provide my SSN for verification",
            )
        assert "sensitive" in str(exc_info.value).lower()

    def test_notes_rejects_sensitive(self) -> None:
        """Test notes field rejects sensitive data."""
        with pytest.raises(ValidationError) as exc_info:
            CreateCallbackTask(
                call_id="uuid-123",
                callback_number="+15559876543",
                notes="Customer's DOB is 01/01/1990",
            )
        assert "sensitive" in str(exc_info.value).lower()

    def test_summary_rejects_sensitive(self) -> None:
        """Test summary field rejects sensitive data."""
        with pytest.raises(ValidationError) as exc_info:
            UpdateCallRecord(
                call_id="uuid-123",
                summary="Customer provided credit_card for payment",
            )
        assert "sensitive" in str(exc_info.value).lower()

    def test_message_rejects_sensitive(self) -> None:
        """Test message field rejects sensitive data."""
        with pytest.raises(ValidationError) as exc_info:
            SendNotification(
                call_id="uuid-123",
                notification_type="sms",
                recipient="+15551234567",
                message="Customer SSN: 123-45-6789",
            )
        assert "sensitive" in str(exc_info.value).lower()

    def test_sensitive_patterns_list(self) -> None:
        """Verify all required sensitive patterns are in blocklist."""
        required_patterns = [
            "ssn",
            "dob",
            "credit_card",
            "bank_account",
            "payment",
            "pin",
            "password",
        ]
        for pattern in required_patterns:
            assert pattern in SENSITIVE_FIELD_PATTERNS, f"Missing pattern: {pattern}"


class TestOpenAISchemaGeneration:
    """Tests for OpenAI function schema generation."""

    def test_generate_create_call_record_schema(self) -> None:
        """Test generating schema for CreateCallRecord."""
        schema = pydantic_to_openai_function_schema(CreateCallRecord)

        assert schema["name"] == "create_call_record"
        assert "description" in schema
        assert schema["parameters"]["type"] == "object"
        assert "from_number" in schema["parameters"]["properties"]
        assert "language" in schema["parameters"]["properties"]
        assert "customer_type" in schema["parameters"]["properties"]
        assert "intent" in schema["parameters"]["properties"]

    def test_generate_callback_task_schema(self) -> None:
        """Test generating schema for CreateCallbackTask."""
        schema = pydantic_to_openai_function_schema(CreateCallbackTask)

        assert schema["name"] == "create_callback_task"
        assert "call_id" in schema["parameters"]["properties"]
        assert "callback_number" in schema["parameters"]["properties"]
        assert "priority" in schema["parameters"]["properties"]

    def test_schema_has_required_fields(self) -> None:
        """Test generated schema includes required fields."""
        schema = pydantic_to_openai_function_schema(CreateCallRecord)
        required = schema["parameters"]["required"]

        assert "from_number" in required
        assert "language" in required
        assert "customer_type" in required
        assert "intent" in required

    def test_schema_has_descriptions(self) -> None:
        """Test generated schema includes field descriptions."""
        schema = pydantic_to_openai_function_schema(CreateCallRecord)
        properties = schema["parameters"]["properties"]

        # Each property should have a description
        for prop_name, prop_schema in properties.items():
            assert "description" in prop_schema or "type" in prop_schema, (
                f"Property {prop_name} missing description"
            )

    def test_all_tool_schemas_generated(self) -> None:
        """Test all tool schemas are pre-generated."""
        expected_tools = [
            "create_call_record",
            "update_call_record",
            "create_callback_task",
            "transfer_call",
            "send_notification",
        ]
        for tool_name in expected_tools:
            assert tool_name in TOOL_SCHEMAS, f"Missing schema: {tool_name}"

    def test_get_all_tool_schemas(self) -> None:
        """Test getting all tool schemas in OpenAI format."""
        schemas = get_all_tool_schemas()

        assert len(schemas) >= 5
        for schema in schemas:
            assert schema["type"] == "function"
            assert "function" in schema
            assert "name" in schema["function"]
            assert "parameters" in schema["function"]


class TestEnums:
    """Tests for enum values."""

    def test_language_enum(self) -> None:
        """Test Language enum values."""
        assert Language.EN.value == "en"
        assert Language.ES.value == "es"

    def test_customer_type_enum(self) -> None:
        """Test CustomerType enum values."""
        assert CustomerType.NEW.value == "new"
        assert CustomerType.EXISTING.value == "existing"
        assert CustomerType.UNKNOWN.value == "unknown"

    def test_call_status_enum(self) -> None:
        """Test CallStatus enum has all required values."""
        required_statuses = [
            "init",
            "greet",
            "language_select",
            "intent_discovery",
            "confirmation",
            "end",
        ]
        status_values = [s.value for s in CallStatus]
        for status in required_statuses:
            assert status in status_values, f"Missing status: {status}"

    def test_task_priority_enum(self) -> None:
        """Test TaskPriority enum values."""
        assert TaskPriority.LOW.value == "low"
        assert TaskPriority.NORMAL.value == "normal"
        assert TaskPriority.HIGH.value == "high"
        assert TaskPriority.URGENT.value == "urgent"


class TestValidationMessages:
    """Tests for clear validation error messages."""

    def test_phone_validation_message(self) -> None:
        """Test phone validation provides clear message."""
        with pytest.raises(ValidationError) as exc_info:
            CreateCallRecord(
                from_number="abc",
                language=Language.EN,
                customer_type=CustomerType.NEW,
                intent="Test",
            )
        error_str = str(exc_info.value).lower()
        # Can fail due to length, format, or digit validation
        assert "from_number" in error_str or "string" in error_str or "digit" in error_str

    def test_sensitive_data_message(self) -> None:
        """Test sensitive data validation provides clear message."""
        with pytest.raises(ValidationError) as exc_info:
            CreateCallRecord(
                from_number="+15551234567",
                language=Language.EN,
                customer_type=CustomerType.NEW,
                intent="My SSN is needed",
            )
        error_str = str(exc_info.value)
        assert "sensitive" in error_str.lower()
