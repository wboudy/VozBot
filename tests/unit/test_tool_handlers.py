"""Tests for tool handlers."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from vozbot.agent.tools.handlers import HandlerResult, HandlerStatus, ToolHandler
from vozbot.storage.db.models import (
    Call,
    CallbackTask,
    CallStatus,
    CustomerType,
    Language,
    TaskPriority,
    TaskStatus,
)


class TestHandlerResult:
    """Tests for HandlerResult dataclass."""

    def test_success_result_to_llm_response(self) -> None:
        """Test success result formatting."""
        result = HandlerResult(
            status=HandlerStatus.SUCCESS,
            data={"call_id": "123"},
            tool_name="create_call_record",
        )
        response = result.to_llm_response()
        assert "executed successfully" in response
        assert "create_call_record" in response
        assert "123" in response

    def test_failure_result_to_llm_response(self) -> None:
        """Test failure result formatting."""
        result = HandlerResult(
            status=HandlerStatus.FAILURE,
            data={},
            error="Call not found",
            tool_name="update_call_record",
        )
        response = result.to_llm_response()
        assert "failed" in response
        assert "Call not found" in response

    def test_partial_result_to_llm_response(self) -> None:
        """Test partial result formatting."""
        result = HandlerResult(
            status=HandlerStatus.PARTIAL,
            data={"task_id": "456"},
            error="Notification failed",
            tool_name="create_callback_task",
        )
        response = result.to_llm_response()
        assert "partially completed" in response
        assert "Warning" in response


class TestToolHandlerExecute:
    """Tests for ToolHandler.execute()."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock async session."""
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.rollback = AsyncMock()
        session.get = AsyncMock()
        return session

    @pytest.fixture
    def handler(self, mock_session: AsyncMock) -> ToolHandler:
        """Create tool handler with mock session."""
        return ToolHandler(db_session=mock_session)

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, handler: ToolHandler) -> None:
        """Test executing unknown tool returns failure."""
        result = await handler.execute("unknown_tool", {})

        assert result.status == HandlerStatus.FAILURE
        assert "Unknown tool" in result.error

    @pytest.mark.asyncio
    async def test_execute_handles_exception(
        self, handler: ToolHandler, mock_session: AsyncMock
    ) -> None:
        """Test that exceptions are caught and rolled back."""
        # Make validation fail
        result = await handler.execute("create_call_record", {"invalid": "args"})

        assert result.status == HandlerStatus.FAILURE
        mock_session.rollback.assert_called()


class TestCreateCallRecordHandler:
    """Tests for create_call_record handler."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock async session."""
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.rollback = AsyncMock()
        return session

    @pytest.fixture
    def handler(self, mock_session: AsyncMock) -> ToolHandler:
        """Create tool handler with mock session."""
        return ToolHandler(db_session=mock_session)

    @pytest.mark.asyncio
    async def test_create_call_record_success(
        self, handler: ToolHandler, mock_session: AsyncMock
    ) -> None:
        """Test successful call record creation."""
        args = {
            "from_number": "+15551234567",
            "language": "en",
            "customer_type": "new",
            "intent": "Schedule appointment",
        }

        # Mock the refresh to set the id
        async def mock_refresh(obj: Any) -> None:
            if hasattr(obj, "id") and not obj.id:
                obj.id = str(uuid4())

        mock_session.refresh = mock_refresh

        result = await handler.execute("create_call_record", args)

        assert result.status == HandlerStatus.SUCCESS
        assert "call_id" in result.data
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_call_record_validation_error(
        self, handler: ToolHandler
    ) -> None:
        """Test validation error on invalid phone number."""
        args = {
            "from_number": "invalid",
            "language": "en",
            "customer_type": "new",
            "intent": "Test",
        }

        result = await handler.execute("create_call_record", args)

        assert result.status == HandlerStatus.FAILURE

    @pytest.mark.asyncio
    async def test_create_call_record_blocks_sensitive_data(
        self, handler: ToolHandler
    ) -> None:
        """Test that sensitive data in intent is blocked."""
        args = {
            "from_number": "+15551234567",
            "language": "en",
            "customer_type": "new",
            "intent": "My SSN is 123-45-6789",
        }

        result = await handler.execute("create_call_record", args)

        assert result.status == HandlerStatus.FAILURE
        assert "sensitive" in result.error.lower()


class TestUpdateCallRecordHandler:
    """Tests for update_call_record handler."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock async session."""
        session = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.rollback = AsyncMock()
        return session

    @pytest.fixture
    def handler(self, mock_session: AsyncMock) -> ToolHandler:
        """Create tool handler with mock session."""
        return ToolHandler(db_session=mock_session)

    @pytest.mark.asyncio
    async def test_update_call_record_success(
        self, handler: ToolHandler, mock_session: AsyncMock
    ) -> None:
        """Test successful call record update."""
        # Create mock call
        mock_call = MagicMock(spec=Call)
        mock_call.id = "call-123"
        mock_call.status = CallStatus.INIT
        mock_session.get = AsyncMock(return_value=mock_call)

        args = {
            "call_id": "call-123",
            "status": "intent_discovery",
            "intent": "Dental appointment",
        }

        result = await handler.execute("update_call_record", args)

        assert result.status == HandlerStatus.SUCCESS
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_call_record_not_found(
        self, handler: ToolHandler, mock_session: AsyncMock
    ) -> None:
        """Test update fails when call not found."""
        mock_session.get = AsyncMock(return_value=None)

        args = {
            "call_id": "nonexistent",
            "status": "completed",
        }

        result = await handler.execute("update_call_record", args)

        assert result.status == HandlerStatus.FAILURE
        assert "not found" in result.error.lower()


class TestCreateCallbackTaskHandler:
    """Tests for create_callback_task handler."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock async session."""
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.rollback = AsyncMock()
        return session

    @pytest.fixture
    def handler(self, mock_session: AsyncMock) -> ToolHandler:
        """Create tool handler with mock session."""
        return ToolHandler(db_session=mock_session)

    @pytest.mark.asyncio
    async def test_create_callback_task_success(
        self, handler: ToolHandler, mock_session: AsyncMock
    ) -> None:
        """Test successful callback task creation."""
        # Mock call exists
        mock_call = MagicMock(spec=Call)
        mock_call.id = "call-123"
        mock_session.get = AsyncMock(return_value=mock_call)

        args = {
            "call_id": "call-123",
            "callback_number": "+15551234567",
            "priority": "high",
            "name": "John Doe",
            "best_time_window": "morning",
            "notes": "Needs dental checkup",
        }

        result = await handler.execute("create_callback_task", args)

        assert result.status == HandlerStatus.SUCCESS
        assert "task_id" in result.data
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_callback_task_call_not_found(
        self, handler: ToolHandler, mock_session: AsyncMock
    ) -> None:
        """Test task creation fails when call not found."""
        mock_session.get = AsyncMock(return_value=None)

        args = {
            "call_id": "nonexistent",
            "callback_number": "+15551234567",
        }

        result = await handler.execute("create_callback_task", args)

        assert result.status == HandlerStatus.FAILURE
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_create_callback_task_priority_mapping(
        self, handler: ToolHandler, mock_session: AsyncMock
    ) -> None:
        """Test that priority strings are correctly mapped."""
        mock_call = MagicMock(spec=Call)
        mock_session.get = AsyncMock(return_value=mock_call)

        for priority in ["low", "normal", "high", "urgent"]:
            mock_session.add.reset_mock()

            args = {
                "call_id": "call-123",
                "callback_number": "+15551234567",
                "priority": priority,
            }

            result = await handler.execute("create_callback_task", args)
            assert result.status == HandlerStatus.SUCCESS


class TestTransferCallHandler:
    """Tests for transfer_call handler."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock async session."""
        session = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        return session

    @pytest.fixture
    def mock_telephony(self) -> AsyncMock:
        """Create mock telephony adapter."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_transfer_call_success(
        self, mock_session: AsyncMock, mock_telephony: AsyncMock
    ) -> None:
        """Test successful call transfer."""
        handler = ToolHandler(db_session=mock_session, telephony_adapter=mock_telephony)

        mock_telephony.transfer_call = AsyncMock(return_value=True)
        mock_call = MagicMock(spec=Call)
        mock_session.get = AsyncMock(return_value=mock_call)

        args = {
            "call_id": "call-123",
            "target_number": "+15559876543",
            "reason": "Customer requested human agent",
        }

        result = await handler.execute("transfer_call", args)

        assert result.status == HandlerStatus.SUCCESS
        mock_telephony.transfer_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_transfer_call_no_telephony_adapter(
        self, mock_session: AsyncMock
    ) -> None:
        """Test transfer fails when no telephony adapter configured."""
        handler = ToolHandler(db_session=mock_session)

        args = {
            "call_id": "call-123",
            "target_number": "+15559876543",
            "reason": "Transfer needed",
        }

        result = await handler.execute("transfer_call", args)

        assert result.status == HandlerStatus.FAILURE
        assert "Telephony adapter not configured" in result.error

    @pytest.mark.asyncio
    async def test_transfer_call_no_target(
        self, mock_session: AsyncMock, mock_telephony: AsyncMock
    ) -> None:
        """Test transfer fails when no target provided."""
        handler = ToolHandler(db_session=mock_session, telephony_adapter=mock_telephony)

        args = {
            "call_id": "call-123",
            "reason": "Transfer needed",
        }

        result = await handler.execute("transfer_call", args)

        assert result.status == HandlerStatus.FAILURE
        assert "target_number or queue_name" in result.error

    @pytest.mark.asyncio
    async def test_transfer_call_failure(
        self, mock_session: AsyncMock, mock_telephony: AsyncMock
    ) -> None:
        """Test handling when transfer fails."""
        handler = ToolHandler(db_session=mock_session, telephony_adapter=mock_telephony)

        mock_telephony.transfer_call = AsyncMock(return_value=False)

        args = {
            "call_id": "call-123",
            "target_number": "+15559876543",
            "reason": "Transfer needed",
        }

        result = await handler.execute("transfer_call", args)

        assert result.status == HandlerStatus.FAILURE
        assert "Transfer failed" in result.error


class TestSendNotificationHandler:
    """Tests for send_notification handler."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock async session."""
        return AsyncMock()

    @pytest.fixture
    def handler(self, mock_session: AsyncMock) -> ToolHandler:
        """Create tool handler with mock session."""
        return ToolHandler(db_session=mock_session)

    @pytest.mark.asyncio
    async def test_send_notification_sms(self, handler: ToolHandler) -> None:
        """Test SMS notification."""
        args = {
            "call_id": "call-123",
            "notification_type": "sms",
            "recipient": "+15551234567",
            "message": "New callback request received",
        }

        result = await handler.execute("send_notification", args)

        assert result.status == HandlerStatus.SUCCESS
        assert result.data["notification_type"] == "sms"
        assert result.data["sent"] is True

    @pytest.mark.asyncio
    async def test_send_notification_email(self, handler: ToolHandler) -> None:
        """Test email notification."""
        args = {
            "call_id": "call-123",
            "notification_type": "email",
            "recipient": "office@example.com",
            "message": "New callback request received",
        }

        result = await handler.execute("send_notification", args)

        assert result.status == HandlerStatus.SUCCESS
        assert result.data["notification_type"] == "email"


class TestToolHandlerIntegration:
    """Integration-style tests for tool handlers."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock async session with realistic behavior."""
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()

        # Track added objects
        added_objects: list[Any] = []

        def track_add(obj: Any) -> None:
            added_objects.append(obj)

        session.add = track_add
        session._added = added_objects

        async def mock_refresh(obj: Any) -> None:
            pass

        session.refresh = mock_refresh

        return session

    @pytest.mark.asyncio
    async def test_full_call_flow(self, mock_session: AsyncMock) -> None:
        """Test a complete call flow: create record -> update -> create task."""
        handler = ToolHandler(db_session=mock_session)

        # Step 1: Create call record
        create_result = await handler.execute(
            "create_call_record",
            {
                "from_number": "+15551234567",
                "language": "en",
                "customer_type": "new",
                "intent": "Schedule appointment",
            },
        )

        assert create_result.status == HandlerStatus.SUCCESS

        # Verify a Call was added
        assert len(mock_session._added) == 1
        assert isinstance(mock_session._added[0], Call)
        call_id = mock_session._added[0].id

        # Step 2: Update call record (mock the get to return the call)
        mock_call = mock_session._added[0]
        mock_session.get = AsyncMock(return_value=mock_call)

        update_result = await handler.execute(
            "update_call_record",
            {
                "call_id": call_id,
                "status": "info_collection",
            },
        )

        assert update_result.status == HandlerStatus.SUCCESS

        # Step 3: Create callback task
        task_result = await handler.execute(
            "create_callback_task",
            {
                "call_id": call_id,
                "callback_number": "+15551234567",
                "priority": "normal",
                "name": "John Doe",
                "notes": "Dental appointment needed",
            },
        )

        assert task_result.status == HandlerStatus.SUCCESS

        # Verify CallbackTask was added
        assert len(mock_session._added) == 2
        assert isinstance(mock_session._added[1], CallbackTask)
