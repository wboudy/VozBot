"""Integration tests for the notification system.

Tests the full flow from callback creation to SMS/email notification.
Uses mocked external services (Twilio, SendGrid) but tests real
internal logic including rate limiting and priority routing.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from vozbot.notifications.service import (
    EmailProvider,
    NotificationResult,
    NotificationService,
)
from vozbot.storage.db.models import (
    Call,
    CallbackTask,
    CallStatus,
    CustomerType,
    Language,
    TaskPriority,
    TaskStatus,
)


class TestCallbackToNotificationFlow:
    """Integration tests for callback creation -> notification flow."""

    @pytest.fixture
    def mock_email_provider(self) -> AsyncMock:
        """Create a mock email provider that tracks calls."""
        provider = AsyncMock(spec=EmailProvider)
        provider.send_email.return_value = NotificationResult(
            success=True,
            provider="sendgrid",
            message_id="email-integration-test",
        )
        return provider

    @pytest.fixture
    def mock_twilio_client(self) -> MagicMock:
        """Create a mock Twilio client that tracks calls."""
        client = MagicMock()
        mock_message = MagicMock()
        mock_message.sid = "SM-integration-test"
        client.messages.create.return_value = mock_message
        return client

    @pytest.fixture
    def notification_service(
        self,
        mock_email_provider: AsyncMock,
        mock_twilio_client: MagicMock,
    ) -> NotificationService:
        """Create a fully configured notification service with mocked providers."""
        service = NotificationService(
            staff_phone="+15559999999",
            staff_email="staff@insurance-office.com",
            twilio_account_sid="test_sid",
            twilio_auth_token="test_token",
            twilio_phone_number="+15550001111",
            email_provider=mock_email_provider,
            sms_rate_limit=10,
            transcript_base_url="https://app.insurance-office.com/transcripts",
        )
        service._twilio_client = mock_twilio_client
        return service

    async def test_urgent_callback_full_flow(
        self,
        notification_service: NotificationService,
        mock_twilio_client: MagicMock,
        mock_email_provider: AsyncMock,
    ) -> None:
        """Test full notification flow for an urgent callback.

        Scenario: Customer calls about an urgent insurance claim.
        Expected: Both SMS and email are sent to staff.
        """
        # Create a realistic call record
        call = Call(
            id="call-urgent-001",
            from_number="+15551234567",
            language=Language.EN,
            customer_type=CustomerType.EXISTING,
            intent="Urgent auto insurance claim after accident",
            status=CallStatus.COMPLETED,
            summary=(
                "Existing customer John Smith called regarding an auto accident "
                "that occurred this morning. Vehicle is totaled. He needs to "
                "file a claim immediately and arrange for a rental car. "
                "Customer was distressed but understood the process."
            ),
            transcript="[Full transcript would be here]",
        )

        # Create the callback task
        callback = CallbackTask(
            id="task-urgent-001",
            call_id=call.id,
            priority=TaskPriority.URGENT,
            name="John Smith",
            callback_number="+15551234567",
            best_time_window="ASAP - Available all day",
            notes="Customer is very anxious. Car accident this morning, needs rental.",
            status=TaskStatus.PENDING,
        )

        # Trigger notifications
        results = await notification_service.notify_callback_created(callback, call)

        # Verify SMS was sent with correct format
        assert results["sms"].success is True
        assert results["sms"].message_id == "SM-integration-test"

        sms_call = mock_twilio_client.messages.create.call_args
        sms_body = sms_call.kwargs["body"]
        assert "New urgent callback:" in sms_body
        assert "John Smith" in sms_body
        assert "+15551234567" in sms_body
        assert "auto insurance claim" in sms_body.lower()

        # Verify email was sent with full details
        assert results["email"].success is True

        email_call = mock_email_provider.send_email.call_args
        assert email_call.kwargs["to_email"] == "staff@insurance-office.com"
        assert "[URGENT]" in email_call.kwargs["subject"]
        assert "John Smith" in email_call.kwargs["subject"]

        html_body = email_call.kwargs["html_body"]
        assert "John Smith" in html_body
        assert "+15551234567" in html_body
        assert "ASAP" in html_body
        assert "auto accident" in html_body
        assert "https://app.insurance-office.com/transcripts/call-urgent-001" in html_body

    async def test_spanish_caller_flow(
        self,
        notification_service: NotificationService,
        mock_email_provider: AsyncMock,
    ) -> None:
        """Test notification flow for a Spanish-speaking caller.

        Scenario: Customer calls in Spanish about policy questions.
        Expected: Email shows Spanish as the language preference.
        """
        call = Call(
            id="call-spanish-001",
            from_number="+15551234567",
            language=Language.ES,
            customer_type=CustomerType.NEW,
            intent="Pregunta sobre cobertura de seguro de hogar",
            status=CallStatus.COMPLETED,
            summary=(
                "Nueva cliente Maria Garcia llamó preguntando sobre "
                "seguro de hogar. Interesada en cotización para casa nueva."
            ),
        )

        callback = CallbackTask(
            id="task-spanish-001",
            call_id=call.id,
            priority=TaskPriority.NORMAL,
            name="Maria Garcia",
            callback_number="+15557654321",
            best_time_window="Afternoon (2-5 PM)",
            notes="Prefers Spanish. Interested in home insurance quote.",
            status=TaskStatus.PENDING,
        )

        results = await notification_service.notify_callback_created(callback, call)

        # No SMS for normal priority
        assert results["sms"].provider == "none"

        # Email should indicate Spanish
        assert results["email"].success is True

        email_call = mock_email_provider.send_email.call_args
        html_body = email_call.kwargs["html_body"]
        text_body = email_call.kwargs["text_body"]

        assert "Spanish" in html_body
        assert "Spanish" in text_body
        assert "Maria Garcia" in html_body

    async def test_rate_limiting_across_multiple_callbacks(
        self,
        mock_email_provider: AsyncMock,
        mock_twilio_client: MagicMock,
    ) -> None:
        """Test that SMS rate limiting works across multiple callback notifications.

        Scenario: Multiple urgent callbacks in quick succession.
        Expected: Only first N callbacks get SMS, rest are rate limited.
        """
        service = NotificationService(
            staff_phone="+15559999999",
            staff_email="staff@example.com",
            twilio_account_sid="test_sid",
            twilio_auth_token="test_token",
            twilio_phone_number="+15550001111",
            email_provider=mock_email_provider,
            sms_rate_limit=3,  # Only allow 3 SMS per hour
        )
        service._twilio_client = mock_twilio_client

        sms_successes = 0
        sms_rate_limited = 0

        # Create 5 urgent callbacks
        for i in range(5):
            callback = CallbackTask(
                id=f"task-{i}",
                call_id=f"call-{i}",
                priority=TaskPriority.URGENT,
                name=f"Customer {i}",
                callback_number=f"+1555000{i:04d}",
                status=TaskStatus.PENDING,
            )

            results = await service.notify_callback_created(callback)

            if results["sms"].success:
                sms_successes += 1
            elif "Rate limit" in (results["sms"].error or ""):
                sms_rate_limited += 1

            # Email should always work
            assert results["email"].success is True

        # First 3 should succeed, last 2 should be rate limited
        assert sms_successes == 3
        assert sms_rate_limited == 2

    async def test_priority_based_routing(
        self,
        notification_service: NotificationService,
        mock_twilio_client: MagicMock,
        mock_email_provider: AsyncMock,
    ) -> None:
        """Test that notifications are routed correctly based on priority.

        Tests all priority levels to verify correct SMS/email routing.
        """
        priorities = [
            (TaskPriority.URGENT, True, True),   # P0: SMS + Email
            (TaskPriority.HIGH, True, True),     # P1: SMS + Email
            (TaskPriority.NORMAL, False, True),  # P2: Email only
            (TaskPriority.LOW, False, True),     # P3: Email only
        ]

        for priority, expect_sms, expect_email in priorities:
            # Reset mocks
            mock_twilio_client.messages.create.reset_mock()
            mock_email_provider.send_email.reset_mock()

            callback = CallbackTask(
                id=f"task-{priority.name}",
                call_id=f"call-{priority.name}",
                priority=priority,
                name=f"Test {priority.name}",
                callback_number="+15551234567",
                status=TaskStatus.PENDING,
            )

            results = await notification_service.notify_callback_created(callback)

            if expect_sms:
                assert results["sms"].success is True, f"SMS should succeed for {priority.name}"
                mock_twilio_client.messages.create.assert_called_once()
            else:
                assert results["sms"].provider == "none", f"SMS should be skipped for {priority.name}"
                mock_twilio_client.messages.create.assert_not_called()

            if expect_email:
                assert results["email"].success is True, f"Email should succeed for {priority.name}"
                mock_email_provider.send_email.assert_called_once()

    async def test_callback_without_call_context(
        self,
        notification_service: NotificationService,
        mock_email_provider: AsyncMock,
    ) -> None:
        """Test notification when call context is not provided.

        Scenario: Callback created but call record not passed.
        Expected: Notification still works with available information.
        """
        callback = CallbackTask(
            id="task-no-context",
            call_id="call-unknown",
            priority=TaskPriority.NORMAL,
            name="Anonymous Caller",
            callback_number="+15551111111",
            best_time_window="Morning",
            notes="Called about general inquiry",
            status=TaskStatus.PENDING,
        )

        # Call without the call object
        results = await notification_service.notify_callback_created(callback)

        assert results["email"].success is True

        email_call = mock_email_provider.send_email.call_args
        html_body = email_call.kwargs["html_body"]

        # Should use defaults for missing call info
        assert "Anonymous Caller" in html_body
        assert "+15551111111" in html_body
        assert "Morning" in html_body

    async def test_notification_with_minimal_callback(
        self,
        notification_service: NotificationService,
        mock_twilio_client: MagicMock,
    ) -> None:
        """Test notification with minimal callback information.

        Scenario: Callback has only required fields.
        Expected: Notification uses appropriate defaults.
        """
        callback = CallbackTask(
            id="task-minimal",
            call_id="call-minimal",
            priority=TaskPriority.URGENT,
            name=None,  # No name
            callback_number="+15552222222",
            best_time_window=None,  # No time preference
            notes=None,  # No notes
            status=TaskStatus.PENDING,
        )

        results = await notification_service.notify_callback_created(callback)

        # SMS should still work
        assert results["sms"].success is True

        sms_call = mock_twilio_client.messages.create.call_args
        sms_body = sms_call.kwargs["body"]

        # Should use "Unknown" for missing name
        assert "Unknown" in sms_body
        assert "+15552222222" in sms_body
        assert "Callback requested" in sms_body


class TestNotificationErrorHandling:
    """Integration tests for error handling in the notification flow."""

    async def test_sms_failure_does_not_block_email(self) -> None:
        """Test that SMS failure doesn't prevent email from being sent."""
        mock_email = AsyncMock(spec=EmailProvider)
        mock_email.send_email.return_value = NotificationResult(
            success=True,
            provider="sendgrid",
            message_id="email-123",
        )

        # Create a service where SMS will fail
        service = NotificationService(
            staff_phone="+15559999999",
            staff_email="staff@example.com",
            twilio_account_sid="",  # Missing credentials
            twilio_auth_token="",
            twilio_phone_number="+15550001111",
            email_provider=mock_email,
        )

        callback = CallbackTask(
            id="task-1",
            call_id="call-1",
            priority=TaskPriority.URGENT,
            name="Test User",
            callback_number="+15551234567",
            status=TaskStatus.PENDING,
        )

        results = await service.notify_callback_created(callback)

        # SMS should fail gracefully
        assert results["sms"].success is False

        # Email should still succeed
        assert results["email"].success is True
        mock_email.send_email.assert_called_once()

    async def test_email_failure_does_not_block_sms(self) -> None:
        """Test that email failure doesn't prevent SMS from being sent."""
        mock_email = AsyncMock(spec=EmailProvider)
        mock_email.send_email.return_value = NotificationResult(
            success=False,
            provider="sendgrid",
            error="API Error",
        )

        mock_twilio = MagicMock()
        mock_message = MagicMock()
        mock_message.sid = "SM123"
        mock_twilio.messages.create.return_value = mock_message

        service = NotificationService(
            staff_phone="+15559999999",
            staff_email="staff@example.com",
            twilio_account_sid="test_sid",
            twilio_auth_token="test_token",
            twilio_phone_number="+15550001111",
            email_provider=mock_email,
        )
        service._twilio_client = mock_twilio

        callback = CallbackTask(
            id="task-1",
            call_id="call-1",
            priority=TaskPriority.URGENT,
            name="Test User",
            callback_number="+15551234567",
            status=TaskStatus.PENDING,
        )

        results = await service.notify_callback_created(callback)

        # SMS should succeed
        assert results["sms"].success is True
        mock_twilio.messages.create.assert_called_once()

        # Email failure is recorded
        assert results["email"].success is False
