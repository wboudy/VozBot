"""Tool handlers for executing LLM tool calls.

This module provides handlers for each tool that the LLM can call.
Handlers validate inputs using Pydantic schemas, execute operations
against the database and telephony adapters, and return structured results.

Security: All handlers use Pydantic validation which includes
blocklist checks for sensitive data (SSN, DOB, payment info).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from vozbot.storage.db.models import (
    Call,
    CallbackTask,
    CallStatus,
    CustomerType,
    Language,
    TaskPriority,
    TaskStatus,
)
from vozbot.telephony.adapters.base import TelephonyAdapter

from .schemas import (
    CreateCallbackTask as CreateCallbackTaskSchema,
    CreateCallRecord,
    SendNotification,
    TransferCall,
    UpdateCallRecord,
)

logger = logging.getLogger(__name__)


class HandlerStatus(str, Enum):
    """Status of a tool handler execution."""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


@dataclass
class HandlerResult:
    """Result of a tool handler execution.

    Attributes:
        status: Whether the handler succeeded or failed.
        data: Result data (varies by handler).
        error: Error message if status is FAILURE.
        tool_name: Name of the tool that was executed.
    """

    status: HandlerStatus
    data: dict[str, Any]
    error: str | None = None
    tool_name: str = ""

    def to_llm_response(self) -> str:
        """Format result for LLM consumption.

        Returns:
            Human-readable string describing the result.
        """
        if self.status == HandlerStatus.SUCCESS:
            return f"Tool '{self.tool_name}' executed successfully. Result: {self.data}"
        elif self.status == HandlerStatus.PARTIAL:
            return (
                f"Tool '{self.tool_name}' partially completed. "
                f"Result: {self.data}. Warning: {self.error}"
            )
        else:
            return f"Tool '{self.tool_name}' failed. Error: {self.error}"


class ToolHandler:
    """Handles execution of LLM tool calls.

    Provides methods to execute each tool type with proper validation,
    database transactions, and error handling.

    Example:
        ```python
        handler = ToolHandler(db_session, telephony_adapter)
        result = await handler.execute("create_call_record", {
            "from_number": "+15551234567",
            "language": "en",
            "customer_type": "new",
            "intent": "Schedule appointment",
        })
        if result.status == HandlerStatus.SUCCESS:
            call_id = result.data["call_id"]
        ```
    """

    def __init__(
        self,
        db_session: AsyncSession,
        telephony_adapter: TelephonyAdapter | None = None,
    ) -> None:
        """Initialize tool handler.

        Args:
            db_session: Async SQLAlchemy session for DB operations.
            telephony_adapter: Optional telephony adapter for call transfer.
        """
        self._db = db_session
        self._telephony = telephony_adapter

        # Registry of tool handlers
        self._handlers: dict[str, Any] = {
            "create_call_record": self.handle_create_call_record,
            "update_call_record": self.handle_update_call_record,
            "create_callback_task": self.handle_create_callback_task,
            "transfer_call": self.handle_transfer_call,
            "send_notification": self.handle_send_notification,
        }

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> HandlerResult:
        """Execute a tool by name with given arguments.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Arguments to pass to the tool.

        Returns:
            HandlerResult with execution outcome.
        """
        handler = self._handlers.get(tool_name)
        if not handler:
            logger.error(f"Unknown tool: {tool_name}")
            return HandlerResult(
                status=HandlerStatus.FAILURE,
                data={},
                error=f"Unknown tool: {tool_name}",
                tool_name=tool_name,
            )

        try:
            logger.info(f"Executing tool: {tool_name} with args: {arguments}")
            result = await handler(arguments)
            logger.info(f"Tool {tool_name} completed with status: {result.status}")
            return result
        except Exception as e:
            logger.exception(f"Tool {tool_name} failed with exception")
            await self._db.rollback()
            return HandlerResult(
                status=HandlerStatus.FAILURE,
                data={},
                error=str(e),
                tool_name=tool_name,
            )

    async def handle_create_call_record(self, args: dict[str, Any]) -> HandlerResult:
        """Handle create_call_record tool call.

        Creates a new Call record in the database with the provided information.

        Args:
            args: Tool arguments matching CreateCallRecord schema.

        Returns:
            HandlerResult with call_id on success.
        """
        try:
            # Validate with Pydantic
            validated = CreateCallRecord(**args)

            # Create Call model
            call = Call(
                id=str(uuid4()),
                from_number=validated.from_number,
                language=Language(validated.language.value) if validated.language else None,
                customer_type=(
                    CustomerType(validated.customer_type.value)
                    if validated.customer_type
                    else None
                ),
                intent=validated.intent,
                status=(
                    CallStatus(validated.status.value)
                    if validated.status
                    else CallStatus.INIT
                ),
            )

            self._db.add(call)
            await self._db.commit()
            await self._db.refresh(call)

            logger.info(f"Created call record: {call.id}")

            return HandlerResult(
                status=HandlerStatus.SUCCESS,
                data={"call_id": call.id, "status": call.status.value},
                tool_name="create_call_record",
            )
        except Exception as e:
            await self._db.rollback()
            raise

    async def handle_update_call_record(self, args: dict[str, Any]) -> HandlerResult:
        """Handle update_call_record tool call.

        Updates an existing Call record with new information.

        Args:
            args: Tool arguments matching UpdateCallRecord schema.

        Returns:
            HandlerResult with updated call info on success.
        """
        try:
            validated = UpdateCallRecord(**args)

            # Fetch existing call
            call = await self._db.get(Call, validated.call_id)
            if not call:
                return HandlerResult(
                    status=HandlerStatus.FAILURE,
                    data={},
                    error=f"Call not found: {validated.call_id}",
                    tool_name="update_call_record",
                )

            # Update fields
            if validated.language is not None:
                call.language = Language(validated.language.value)
            if validated.customer_type is not None:
                call.customer_type = CustomerType(validated.customer_type.value)
            if validated.intent is not None:
                call.intent = validated.intent
            if validated.status is not None:
                call.status = CallStatus(validated.status.value)
            if validated.summary is not None:
                call.summary = validated.summary
            if validated.transcript is not None:
                call.transcript = validated.transcript

            await self._db.commit()
            await self._db.refresh(call)

            logger.info(f"Updated call record: {call.id}")

            return HandlerResult(
                status=HandlerStatus.SUCCESS,
                data={"call_id": call.id, "status": call.status.value},
                tool_name="update_call_record",
            )
        except Exception as e:
            await self._db.rollback()
            raise

    async def handle_create_callback_task(self, args: dict[str, Any]) -> HandlerResult:
        """Handle create_callback_task tool call.

        Creates a CallbackTask for office staff to follow up on a call.

        Args:
            args: Tool arguments matching CreateCallbackTask schema.

        Returns:
            HandlerResult with task_id on success.
        """
        try:
            validated = CreateCallbackTaskSchema(**args)

            # Verify call exists
            call = await self._db.get(Call, validated.call_id)
            if not call:
                return HandlerResult(
                    status=HandlerStatus.FAILURE,
                    data={},
                    error=f"Call not found: {validated.call_id}",
                    tool_name="create_callback_task",
                )

            # Map priority
            priority_map = {
                "low": TaskPriority.LOW,
                "normal": TaskPriority.NORMAL,
                "high": TaskPriority.HIGH,
                "urgent": TaskPriority.URGENT,
            }

            task = CallbackTask(
                id=str(uuid4()),
                call_id=validated.call_id,
                priority=priority_map.get(validated.priority.value, TaskPriority.NORMAL),
                name=validated.name,
                callback_number=validated.callback_number,
                best_time_window=validated.best_time_window,
                notes=validated.notes,
                status=TaskStatus.PENDING,
            )

            self._db.add(task)
            await self._db.commit()
            await self._db.refresh(task)

            logger.info(f"Created callback task: {task.id} for call: {validated.call_id}")

            return HandlerResult(
                status=HandlerStatus.SUCCESS,
                data={"task_id": task.id, "call_id": validated.call_id},
                tool_name="create_callback_task",
            )
        except Exception as e:
            await self._db.rollback()
            raise

    async def handle_transfer_call(self, args: dict[str, Any]) -> HandlerResult:
        """Handle transfer_call tool call.

        Transfers an active call to another number using the telephony adapter.

        Args:
            args: Tool arguments matching TransferCall schema.

        Returns:
            HandlerResult with transfer status.
        """
        try:
            validated = TransferCall(**args)

            if not self._telephony:
                return HandlerResult(
                    status=HandlerStatus.FAILURE,
                    data={},
                    error="Telephony adapter not configured",
                    tool_name="transfer_call",
                )

            # Determine target
            target = validated.target_number or validated.queue_name
            if not target:
                return HandlerResult(
                    status=HandlerStatus.FAILURE,
                    data={},
                    error="Either target_number or queue_name must be provided",
                    tool_name="transfer_call",
                )

            # Execute transfer
            success = await self._telephony.transfer_call(
                call_id=validated.call_id,
                target_number=validated.target_number or "",
            )

            if success:
                # Update call status
                call = await self._db.get(Call, validated.call_id)
                if call:
                    call.status = CallStatus.TRANSFERRED
                    await self._db.commit()

                logger.info(f"Transferred call {validated.call_id} to {target}")

                return HandlerResult(
                    status=HandlerStatus.SUCCESS,
                    data={"call_id": validated.call_id, "transferred_to": target},
                    tool_name="transfer_call",
                )
            else:
                return HandlerResult(
                    status=HandlerStatus.FAILURE,
                    data={},
                    error="Transfer failed",
                    tool_name="transfer_call",
                )
        except Exception as e:
            await self._db.rollback()
            raise

    async def handle_send_notification(self, args: dict[str, Any]) -> HandlerResult:
        """Handle send_notification tool call.

        Sends a notification (SMS or email) to office staff.
        Currently logs the notification; production would integrate with providers.

        Args:
            args: Tool arguments matching SendNotification schema.

        Returns:
            HandlerResult indicating notification was sent.
        """
        try:
            validated = SendNotification(**args)

            # For now, just log the notification
            # In production, this would integrate with SMS/email providers
            logger.info(
                f"Notification [{validated.notification_type}] to {validated.recipient}: "
                f"{validated.message}"
            )

            return HandlerResult(
                status=HandlerStatus.SUCCESS,
                data={
                    "notification_type": validated.notification_type,
                    "recipient": validated.recipient,
                    "sent": True,
                },
                tool_name="send_notification",
            )
        except Exception:
            raise
