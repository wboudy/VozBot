"""Unit tests for the NotificationService.

Tests cover:
- SMS sending with rate limiting
- Email sending via mocked providers
- Priority-based notification routing (P0/P1 = SMS, all = email)
- Message formatting (SMS and email)
- Rate limiting behavior
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vozbot.notifications.service import (
    EmailProvider,
    NotificationResult,
    NotificationService,
    SendGridProvider,
    SESProvider,
    SMSRateLimiter,
)
from vozbot.storage.db.models import (
    Call,
    CallbackTask,
    CallStatus,
    Language,
    TaskPriority,
    TaskStatus,
)


class TestSMSRateLimiter:
    """Tests for the SMS rate limiter."""

    def test_can_send_when_under_limit(self) -> None:
        """Test that sending is allowed when under the rate limit."""
        limiter = SMSRateLimiter(max_sms_per_hour=10)
        assert limiter.can_send() is True

    def test_cannot_send_when_at_limit(self) -> None:
        """Test that sending is blocked when at the rate limit."""
        limiter = SMSRateLimiter(max_sms_per_hour=3)

        # Record 3 sends
        for _ in range(3):
            assert limiter.can_send() is True
            limiter.record_send()

        # 4th should be blocked
        assert limiter.can_send() is False

    def test_get_remaining_accurate(self) -> None:
        """Test that remaining count is accurate."""
        limiter = SMSRateLimiter(max_sms_per_hour=5)

        assert limiter.get_remaining() == 5

        limiter.record_send()
        assert limiter.get_remaining() == 4

        limiter.record_send()
        limiter.record_send()
        assert limiter.get_remaining() == 2

    def test_old_timestamps_cleaned_up(self) -> None:
        """Test that timestamps older than 1 hour are cleaned up."""
        limiter = SMSRateLimiter(max_sms_per_hour=2)

        # Manually add an old timestamp
        old_time = datetime.now() - timedelta(hours=2)
        limiter._timestamps.append(old_time)
        limiter.record_send()

        # Should clean up old timestamp
        assert limiter.can_send() is True
        assert limiter.get_remaining() == 1  # Only recent one counts


class TestNotificationPriority:
    """Tests for priority classification."""

    def test_p0_is_urgent(self) -> None:
        """P0 should be classified as urgent."""
        service = NotificationService()
        assert service._is_urgent_priority(4) is True

    def test_p1_is_urgent(self) -> None:
        """P1 should be classified as urgent."""
        service = NotificationService()
        assert service._is_urgent_priority(3) is True

    def test_p2_is_not_urgent(self) -> None:
        """P2 should NOT be classified as urgent."""
        service = NotificationService()
        assert service._is_urgent_priority(2) is False

    def test_p3_is_not_urgent(self) -> None:
        """P3 should NOT be classified as urgent."""
        service = NotificationService()
        assert service._is_urgent_priority(1) is False


class TestSMSFormatting:
    """Tests for SMS message formatting."""

    def test_format_sms_with_all_fields(self) -> None:
        """Test SMS formatting with all fields present."""
        service = NotificationService()

        callback = CallbackTask(
            id="task-123",
            call_id="call-456",
            name="John Doe",
            callback_number="+15551234567",
            priority=TaskPriority.URGENT,
            status=TaskStatus.PENDING,
        )

        call = Call(
            id="call-456",
            from_number="+15551234567",
            intent="Insurance quote inquiry",
            status=CallStatus.COMPLETED,
        )

        message = service._format_sms_message(callback, call)

        assert "New urgent callback:" in message
        assert "John Doe" in message
        assert "+15551234567" in message
        assert "Insurance quote inquiry" in message

    def test_format_sms_without_name(self) -> None:
        """Test SMS formatting without caller name."""
        service = NotificationService()

        callback = CallbackTask(
            id="task-123",
            call_id="call-456",
            name=None,
            callback_number="+15551234567",
            priority=TaskPriority.HIGH,
            status=TaskStatus.PENDING,
        )

        message = service._format_sms_message(callback, None)

        assert "Unknown" in message
        assert "+15551234567" in message
        assert "Callback requested" in message

    def test_format_sms_without_intent(self) -> None:
        """Test SMS formatting without intent."""
        service = NotificationService()

        callback = CallbackTask(
            id="task-123",
            call_id="call-456",
            name="Jane Smith",
            callback_number="+15559876543",
            priority=TaskPriority.URGENT,
            status=TaskStatus.PENDING,
        )

        call = Call(
            id="call-456",
            from_number="+15559876543",
            intent=None,
            status=CallStatus.COMPLETED,
        )

        message = service._format_sms_message(callback, call)

        assert "Jane Smith" in message
        assert "Callback requested" in message


class TestEmailFormatting:
    """Tests for email formatting."""

    def test_format_email_subject_urgent(self) -> None:
        """Test email subject for urgent priority."""
        service = NotificationService()

        callback = CallbackTask(
            id="task-123",
            call_id="call-456",
            name="John Doe",
            callback_number="+15551234567",
            priority=TaskPriority.URGENT,
            status=TaskStatus.PENDING,
        )

        subject = service._format_email_subject(callback)

        assert "[URGENT]" in subject
        assert "John Doe" in subject

    def test_format_email_subject_high(self) -> None:
        """Test email subject for high priority."""
        service = NotificationService()

        callback = CallbackTask(
            id="task-123",
            call_id="call-456",
            name="Jane Smith",
            callback_number="+15551234567",
            priority=TaskPriority.HIGH,
            status=TaskStatus.PENDING,
        )

        subject = service._format_email_subject(callback)

        assert "[HIGH]" in subject
        assert "Jane Smith" in subject

    def test_format_email_subject_normal(self) -> None:
        """Test email subject for normal priority."""
        service = NotificationService()

        callback = CallbackTask(
            id="task-123",
            call_id="call-456",
            name="Bob Jones",
            callback_number="+15551234567",
            priority=TaskPriority.NORMAL,
            status=TaskStatus.PENDING,
        )

        subject = service._format_email_subject(callback)

        assert "[NORMAL]" in subject
        assert "Bob Jones" in subject

    def test_format_email_body_contains_required_fields(self) -> None:
        """Test email body contains all required information."""
        service = NotificationService(transcript_base_url="https://test.com/transcripts")

        callback = CallbackTask(
            id="task-123",
            call_id="call-456",
            name="John Doe",
            callback_number="+15551234567",
            priority=TaskPriority.URGENT,
            best_time_window="Morning",
            notes="Please call ASAP",
            status=TaskStatus.PENDING,
        )

        call = Call(
            id="call-456",
            from_number="+15551234567",
            intent="Insurance claim",
            summary="Customer needs help with auto insurance claim after accident.",
            language=Language.EN,
            status=CallStatus.COMPLETED,
        )

        html_body, text_body = service._format_email_body(callback, call)

        # Check HTML body
        assert "John Doe" in html_body
        assert "+15551234567" in html_body
        assert "Morning" in html_body
        assert "Insurance claim" in html_body
        assert "auto insurance claim" in html_body
        assert "Please call ASAP" in html_body
        assert "https://test.com/transcripts/call-456" in html_body

        # Check text body
        assert "John Doe" in text_body
        assert "+15551234567" in text_body
        assert "Morning" in text_body
        assert "Insurance claim" in text_body

    def test_format_email_body_spanish_language(self) -> None:
        """Test email body shows Spanish language correctly."""
        service = NotificationService()

        callback = CallbackTask(
            id="task-123",
            call_id="call-456",
            name="Maria Garcia",
            callback_number="+15551234567",
            priority=TaskPriority.NORMAL,
            status=TaskStatus.PENDING,
        )

        call = Call(
            id="call-456",
            from_number="+15551234567",
            language=Language.ES,
            status=CallStatus.COMPLETED,
        )

        html_body, text_body = service._format_email_body(callback, call)

        assert "Spanish" in html_body
        assert "Spanish" in text_body


class TestSendSMS:
    """Tests for SMS sending functionality."""

    @pytest.fixture
    def mock_twilio_client(self) -> MagicMock:
        """Create a mock Twilio client."""
        client = MagicMock()
        mock_message = MagicMock()
        mock_message.sid = "SM123456789"
        client.messages.create.return_value = mock_message
        return client

    async def test_send_sms_success(self, mock_twilio_client: MagicMock) -> None:
        """Test successful SMS sending."""
        service = NotificationService(
            twilio_account_sid="test_sid",
            twilio_auth_token="test_token",
            twilio_phone_number="+15550001111",
        )
        service._twilio_client = mock_twilio_client

        result = await service.send_sms(
            to_phone="+15551234567",
            message="Test message",
        )

        assert result.success is True
        assert result.provider == "twilio"
        assert result.message_id == "SM123456789"

        mock_twilio_client.messages.create.assert_called_once_with(
            body="Test message",
            from_="+15550001111",
            to="+15551234567",
        )

    async def test_send_sms_rate_limited(self) -> None:
        """Test SMS is blocked when rate limited."""
        service = NotificationService(
            twilio_account_sid="test_sid",
            twilio_auth_token="test_token",
            twilio_phone_number="+15550001111",
            sms_rate_limit=2,
        )

        # Exhaust the rate limit
        service.rate_limiter.record_send()
        service.rate_limiter.record_send()

        result = await service.send_sms(
            to_phone="+15551234567",
            message="Test message",
        )

        assert result.success is False
        assert "Rate limit exceeded" in result.error

    async def test_send_sms_bypass_rate_limit(self, mock_twilio_client: MagicMock) -> None:
        """Test SMS can bypass rate limit when specified."""
        service = NotificationService(
            twilio_account_sid="test_sid",
            twilio_auth_token="test_token",
            twilio_phone_number="+15550001111",
            sms_rate_limit=1,
        )
        service._twilio_client = mock_twilio_client

        # Exhaust rate limit
        service.rate_limiter.record_send()

        # Should still work with bypass
        result = await service.send_sms(
            to_phone="+15551234567",
            message="Test message",
            bypass_rate_limit=True,
        )

        assert result.success is True

    async def test_send_sms_no_phone_configured(self) -> None:
        """Test SMS fails gracefully when Twilio phone not configured."""
        service = NotificationService(
            twilio_account_sid="test_sid",
            twilio_auth_token="test_token",
            twilio_phone_number="",  # Not configured
        )

        result = await service.send_sms(
            to_phone="+15551234567",
            message="Test message",
        )

        assert result.success is False
        assert "phone number not configured" in result.error


class TestSendEmail:
    """Tests for email sending functionality."""

    async def test_send_email_via_sendgrid(self) -> None:
        """Test email sending via SendGrid."""
        mock_provider = AsyncMock(spec=EmailProvider)
        mock_provider.send_email.return_value = NotificationResult(
            success=True,
            provider="sendgrid",
            message_id="msg-123",
        )

        service = NotificationService(email_provider=mock_provider)

        result = await service.send_email(
            to_email="test@example.com",
            subject="Test Subject",
            html_body="<p>Test</p>",
            text_body="Test",
        )

        assert result.success is True
        assert result.provider == "sendgrid"
        mock_provider.send_email.assert_called_once()

    async def test_send_email_failure(self) -> None:
        """Test email failure handling."""
        mock_provider = AsyncMock(spec=EmailProvider)
        mock_provider.send_email.return_value = NotificationResult(
            success=False,
            provider="sendgrid",
            error="API error",
        )

        service = NotificationService(email_provider=mock_provider)

        result = await service.send_email(
            to_email="test@example.com",
            subject="Test Subject",
            html_body="<p>Test</p>",
        )

        assert result.success is False
        assert "API error" in result.error


class TestNotifyCallbackCreated:
    """Tests for the notify_callback_created method."""

    @pytest.fixture
    def mock_email_provider(self) -> AsyncMock:
        """Create a mock email provider."""
        provider = AsyncMock(spec=EmailProvider)
        provider.send_email.return_value = NotificationResult(
            success=True,
            provider="sendgrid",
            message_id="email-123",
        )
        return provider

    @pytest.fixture
    def mock_twilio_client(self) -> MagicMock:
        """Create a mock Twilio client."""
        client = MagicMock()
        mock_message = MagicMock()
        mock_message.sid = "SM123456789"
        client.messages.create.return_value = mock_message
        return client

    async def test_urgent_callback_sends_sms_and_email(
        self,
        mock_email_provider: AsyncMock,
        mock_twilio_client: MagicMock,
    ) -> None:
        """Test that P0/P1 callbacks send both SMS and email."""
        service = NotificationService(
            staff_phone="+15559999999",
            staff_email="staff@example.com",
            twilio_account_sid="test_sid",
            twilio_auth_token="test_token",
            twilio_phone_number="+15550001111",
            email_provider=mock_email_provider,
        )
        service._twilio_client = mock_twilio_client

        callback = CallbackTask(
            id="task-123",
            call_id="call-456",
            name="John Doe",
            callback_number="+15551234567",
            priority=TaskPriority.URGENT,  # P0
            status=TaskStatus.PENDING,
        )

        call = Call(
            id="call-456",
            from_number="+15551234567",
            intent="Urgent insurance matter",
            status=CallStatus.COMPLETED,
        )

        results = await service.notify_callback_created(callback, call)

        # Both SMS and email should be sent
        assert results["sms"].success is True
        assert results["email"].success is True

        mock_twilio_client.messages.create.assert_called_once()
        mock_email_provider.send_email.assert_called_once()

    async def test_high_priority_callback_sends_sms_and_email(
        self,
        mock_email_provider: AsyncMock,
        mock_twilio_client: MagicMock,
    ) -> None:
        """Test that HIGH priority callbacks send both SMS and email."""
        service = NotificationService(
            staff_phone="+15559999999",
            staff_email="staff@example.com",
            twilio_account_sid="test_sid",
            twilio_auth_token="test_token",
            twilio_phone_number="+15550001111",
            email_provider=mock_email_provider,
        )
        service._twilio_client = mock_twilio_client

        callback = CallbackTask(
            id="task-123",
            call_id="call-456",
            name="Jane Smith",
            callback_number="+15551234567",
            priority=TaskPriority.HIGH,  # P1
            status=TaskStatus.PENDING,
        )

        results = await service.notify_callback_created(callback)

        assert results["sms"].success is True
        assert results["email"].success is True

    async def test_normal_priority_sends_email_only(
        self,
        mock_email_provider: AsyncMock,
    ) -> None:
        """Test that NORMAL priority callbacks only send email, not SMS."""
        service = NotificationService(
            staff_phone="+15559999999",
            staff_email="staff@example.com",
            email_provider=mock_email_provider,
        )

        callback = CallbackTask(
            id="task-123",
            call_id="call-456",
            name="Bob Jones",
            callback_number="+15551234567",
            priority=TaskPriority.NORMAL,  # P2
            status=TaskStatus.PENDING,
        )

        results = await service.notify_callback_created(callback)

        # SMS should be skipped
        assert results["sms"].success is True
        assert results["sms"].provider == "none"
        assert "not urgent" in results["sms"].error.lower()

        # Email should still be sent
        assert results["email"].success is True

    async def test_low_priority_sends_email_only(
        self,
        mock_email_provider: AsyncMock,
    ) -> None:
        """Test that LOW priority callbacks only send email, not SMS."""
        service = NotificationService(
            staff_phone="+15559999999",
            staff_email="staff@example.com",
            email_provider=mock_email_provider,
        )

        callback = CallbackTask(
            id="task-123",
            call_id="call-456",
            name="Alice Brown",
            callback_number="+15551234567",
            priority=TaskPriority.LOW,  # P3
            status=TaskStatus.PENDING,
        )

        results = await service.notify_callback_created(callback)

        assert results["sms"].provider == "none"
        assert results["email"].success is True

    async def test_no_staff_phone_skips_sms(
        self,
        mock_email_provider: AsyncMock,
    ) -> None:
        """Test that missing staff phone skips SMS gracefully."""
        service = NotificationService(
            staff_phone="",  # Not configured
            staff_email="staff@example.com",
            email_provider=mock_email_provider,
        )

        callback = CallbackTask(
            id="task-123",
            call_id="call-456",
            name="John Doe",
            callback_number="+15551234567",
            priority=TaskPriority.URGENT,
            status=TaskStatus.PENDING,
        )

        results = await service.notify_callback_created(callback)

        assert results["sms"].success is False
        assert "not configured" in results["sms"].error.lower()
        assert results["email"].success is True

    async def test_no_staff_email_skips_email(
        self,
        mock_twilio_client: MagicMock,
    ) -> None:
        """Test that missing staff email skips email gracefully."""
        service = NotificationService(
            staff_phone="+15559999999",
            staff_email="",  # Not configured
            twilio_account_sid="test_sid",
            twilio_auth_token="test_token",
            twilio_phone_number="+15550001111",
        )
        service._twilio_client = mock_twilio_client

        callback = CallbackTask(
            id="task-123",
            call_id="call-456",
            name="John Doe",
            callback_number="+15551234567",
            priority=TaskPriority.URGENT,
            status=TaskStatus.PENDING,
        )

        results = await service.notify_callback_created(callback)

        assert results["sms"].success is True
        assert results["email"].success is False
        assert "not configured" in results["email"].error.lower()


class TestSendGridProvider:
    """Tests for the SendGrid email provider."""

    async def test_sendgrid_no_api_key(self) -> None:
        """Test SendGrid fails gracefully without API key."""
        provider = SendGridProvider(api_key="")

        result = await provider.send_email(
            to_email="test@example.com",
            subject="Test",
            html_body="<p>Test</p>",
        )

        assert result.success is False
        assert "not configured" in result.error.lower()

    async def test_sendgrid_success(self) -> None:
        """Test successful SendGrid email sending."""
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.headers = {"X-Message-Id": "msg-123"}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        provider = SendGridProvider(
            api_key="test-api-key",
            from_email="from@test.com",
        )

        with patch.object(httpx, "AsyncClient", return_value=mock_client):
            result = await provider.send_email(
                to_email="test@example.com",
                subject="Test Subject",
                html_body="<p>Test</p>",
                text_body="Test",
            )

        assert result.success is True
        assert result.provider == "sendgrid"
        assert result.message_id == "msg-123"

    async def test_sendgrid_api_error(self) -> None:
        """Test SendGrid API error handling."""
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        provider = SendGridProvider(api_key="test-api-key")

        with patch.object(httpx, "AsyncClient", return_value=mock_client):
            result = await provider.send_email(
                to_email="test@example.com",
                subject="Test",
                html_body="<p>Test</p>",
            )

        assert result.success is False
        assert "400" in result.error


class TestSESProvider:
    """Tests for the AWS SES email provider."""

    async def test_ses_success(self) -> None:
        """Test successful SES email sending."""
        mock_client = MagicMock()
        mock_client.send_email.return_value = {"MessageId": "ses-msg-123"}

        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_client

        provider = SESProvider(
            region="us-east-1",
            from_email="from@test.com",
        )

        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            # Need to reimport since boto3 is imported inside the method
            result = await provider.send_email(
                to_email="test@example.com",
                subject="Test Subject",
                html_body="<p>Test</p>",
                text_body="Test",
            )

        assert result.success is True
        assert result.provider == "ses"
        assert result.message_id == "ses-msg-123"

    async def test_ses_error(self) -> None:
        """Test SES error handling."""
        mock_client = MagicMock()
        mock_client.send_email.side_effect = Exception("SES Error")

        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_client

        provider = SESProvider()

        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            result = await provider.send_email(
                to_email="test@example.com",
                subject="Test",
                html_body="<p>Test</p>",
            )

        assert result.success is False
        assert "SES Error" in result.error
