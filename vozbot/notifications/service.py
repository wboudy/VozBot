"""Notification service for SMS and email alerts.

Sends SMS notifications via Twilio for urgent callbacks (P0/P1 priority)
and email notifications via SendGrid or SES for all callbacks.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vozbot.storage.db.models import Call, CallbackTask

logger = logging.getLogger(__name__)


class NotificationPriority(int, Enum):
    """Priority levels that trigger SMS notifications."""

    P0 = 4  # URGENT - always SMS
    P1 = 3  # HIGH - always SMS
    P2 = 2  # NORMAL - email only
    P3 = 1  # LOW - email only


@dataclass
class NotificationResult:
    """Result of a notification attempt."""

    success: bool
    provider: str
    message_id: str | None = None
    error: str | None = None


@dataclass
class StaffContact:
    """Staff member contact information."""

    name: str
    phone: str | None = None
    email: str | None = None


class EmailProvider(ABC):
    """Abstract base class for email providers."""

    @abstractmethod
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
    ) -> NotificationResult:
        """Send an email.

        Args:
            to_email: Recipient email address.
            subject: Email subject line.
            html_body: HTML content of the email.
            text_body: Plain text content (optional).

        Returns:
            NotificationResult with success status.
        """
        pass


class SendGridProvider(EmailProvider):
    """SendGrid email provider implementation."""

    def __init__(
        self,
        api_key: str | None = None,
        from_email: str | None = None,
    ) -> None:
        """Initialize SendGrid provider.

        Args:
            api_key: SendGrid API key. Defaults to SENDGRID_API_KEY env var.
            from_email: Sender email address. Defaults to SENDGRID_FROM_EMAIL env var.
        """
        self.api_key = api_key or os.getenv("SENDGRID_API_KEY", "")
        self.from_email = from_email or os.getenv(
            "SENDGRID_FROM_EMAIL", "noreply@vozbot.local"
        )

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
    ) -> NotificationResult:
        """Send an email via SendGrid.

        Args:
            to_email: Recipient email address.
            subject: Email subject line.
            html_body: HTML content of the email.
            text_body: Plain text content (optional).

        Returns:
            NotificationResult with success status.
        """
        if not self.api_key:
            logger.warning("SendGrid API key not configured, skipping email")
            return NotificationResult(
                success=False,
                provider="sendgrid",
                error="API key not configured",
            )

        try:
            # Import sendgrid here to make it an optional dependency
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "personalizations": [{"to": [{"email": to_email}]}],
                        "from": {"email": self.from_email},
                        "subject": subject,
                        "content": [
                            {"type": "text/plain", "value": text_body or html_body},
                            {"type": "text/html", "value": html_body},
                        ],
                    },
                    timeout=30.0,
                )

                if response.status_code in (200, 202):
                    message_id = response.headers.get("X-Message-Id", "")
                    logger.info(
                        "Email sent via SendGrid",
                        extra={
                            "to_email": to_email,
                            "subject": subject,
                            "message_id": message_id,
                        },
                    )
                    return NotificationResult(
                        success=True,
                        provider="sendgrid",
                        message_id=message_id,
                    )
                else:
                    error_msg = f"SendGrid API error: {response.status_code}"
                    logger.error(
                        error_msg,
                        extra={
                            "status_code": response.status_code,
                            "response": response.text,
                        },
                    )
                    return NotificationResult(
                        success=False,
                        provider="sendgrid",
                        error=error_msg,
                    )

        except Exception as e:
            error_msg = f"SendGrid error: {e}"
            logger.exception(error_msg)
            return NotificationResult(
                success=False,
                provider="sendgrid",
                error=error_msg,
            )


class SESProvider(EmailProvider):
    """AWS SES email provider implementation."""

    def __init__(
        self,
        region: str | None = None,
        from_email: str | None = None,
    ) -> None:
        """Initialize SES provider.

        Args:
            region: AWS region. Defaults to AWS_REGION env var.
            from_email: Sender email address. Defaults to SES_FROM_EMAIL env var.
        """
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self.from_email = from_email or os.getenv(
            "SES_FROM_EMAIL", "noreply@vozbot.local"
        )

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
    ) -> NotificationResult:
        """Send an email via AWS SES.

        Args:
            to_email: Recipient email address.
            subject: Email subject line.
            html_body: HTML content of the email.
            text_body: Plain text content (optional).

        Returns:
            NotificationResult with success status.
        """
        try:
            # Import boto3 here to make it an optional dependency
            import boto3

            client = boto3.client("ses", region_name=self.region)

            response = client.send_email(
                Source=self.from_email,
                Destination={"ToAddresses": [to_email]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {
                            "Data": text_body or html_body,
                            "Charset": "UTF-8",
                        },
                        "Html": {"Data": html_body, "Charset": "UTF-8"},
                    },
                },
            )

            message_id = response.get("MessageId", "")
            logger.info(
                "Email sent via SES",
                extra={
                    "to_email": to_email,
                    "subject": subject,
                    "message_id": message_id,
                },
            )
            return NotificationResult(
                success=True,
                provider="ses",
                message_id=message_id,
            )

        except Exception as e:
            error_msg = f"SES error: {e}"
            logger.exception(error_msg)
            return NotificationResult(
                success=False,
                provider="ses",
                error=error_msg,
            )


class SMSRateLimiter:
    """Rate limiter for SMS messages.

    Implements a sliding window rate limit of max_sms_per_hour.
    """

    def __init__(self, max_sms_per_hour: int = 10) -> None:
        """Initialize the rate limiter.

        Args:
            max_sms_per_hour: Maximum SMS messages allowed per hour.
        """
        self.max_sms_per_hour = max_sms_per_hour
        self._timestamps: deque[datetime] = deque()

    def _cleanup_old_timestamps(self) -> None:
        """Remove timestamps older than 1 hour."""
        cutoff = datetime.now() - timedelta(hours=1)
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

    def can_send(self) -> bool:
        """Check if an SMS can be sent within rate limits.

        Returns:
            True if sending is allowed, False if rate limited.
        """
        self._cleanup_old_timestamps()
        return len(self._timestamps) < self.max_sms_per_hour

    def record_send(self) -> None:
        """Record that an SMS was sent."""
        self._timestamps.append(datetime.now())

    def get_remaining(self) -> int:
        """Get the number of SMS sends remaining in the current window.

        Returns:
            Number of SMS messages that can still be sent.
        """
        self._cleanup_old_timestamps()
        return max(0, self.max_sms_per_hour - len(self._timestamps))


class NotificationService:
    """Service for sending SMS and email notifications for callback tasks.

    SMS is sent via Twilio for P0/P1 priority callbacks.
    Email is sent via configurable provider (SendGrid or SES) for all callbacks.

    Environment Variables:
        STAFF_PHONE: Phone number to receive SMS notifications.
        STAFF_EMAIL: Email address to receive notifications.
        TWILIO_ACCOUNT_SID: Twilio account SID (for SMS).
        TWILIO_AUTH_TOKEN: Twilio auth token (for SMS).
        TWILIO_PHONE_NUMBER: Twilio phone number for sending SMS.
        EMAIL_PROVIDER: 'sendgrid' or 'ses' (default: sendgrid).
        SENDGRID_API_KEY: SendGrid API key (if using SendGrid).
        SENDGRID_FROM_EMAIL: Sender email for SendGrid.
        AWS_REGION: AWS region for SES.
        SES_FROM_EMAIL: Sender email for SES.
        SMS_RATE_LIMIT: Max SMS per hour (default: 10).
        TRANSCRIPT_BASE_URL: Base URL for transcript links.

    Example:
        ```python
        service = NotificationService()
        result = await service.notify_callback_created(callback, call)
        ```
    """

    def __init__(
        self,
        staff_phone: str | None = None,
        staff_email: str | None = None,
        twilio_account_sid: str | None = None,
        twilio_auth_token: str | None = None,
        twilio_phone_number: str | None = None,
        email_provider: EmailProvider | None = None,
        sms_rate_limit: int | None = None,
        transcript_base_url: str | None = None,
    ) -> None:
        """Initialize the notification service.

        Args:
            staff_phone: Phone number to receive SMS. Defaults to STAFF_PHONE env.
            staff_email: Email to receive notifications. Defaults to STAFF_EMAIL env.
            twilio_account_sid: Twilio account SID. Defaults to TWILIO_ACCOUNT_SID env.
            twilio_auth_token: Twilio auth token. Defaults to TWILIO_AUTH_TOKEN env.
            twilio_phone_number: Twilio phone number. Defaults to TWILIO_PHONE_NUMBER env.
            email_provider: Email provider instance. Defaults based on EMAIL_PROVIDER env.
            sms_rate_limit: Max SMS per hour. Defaults to SMS_RATE_LIMIT env or 10.
            transcript_base_url: Base URL for transcripts. Defaults to TRANSCRIPT_BASE_URL env.
        """
        # Staff contact info
        self.staff_phone = staff_phone or os.getenv("STAFF_PHONE", "")
        self.staff_email = staff_email or os.getenv("STAFF_EMAIL", "")

        # Twilio config for SMS
        self.twilio_account_sid = twilio_account_sid or os.getenv(
            "TWILIO_ACCOUNT_SID", ""
        )
        self.twilio_auth_token = twilio_auth_token or os.getenv(
            "TWILIO_AUTH_TOKEN", ""
        )
        self.twilio_phone_number = twilio_phone_number or os.getenv(
            "TWILIO_PHONE_NUMBER", ""
        )

        # Lazy Twilio client
        self._twilio_client = None

        # Email provider
        if email_provider:
            self.email_provider = email_provider
        else:
            provider_type = os.getenv("EMAIL_PROVIDER", "sendgrid").lower()
            if provider_type == "ses":
                self.email_provider = SESProvider()
            else:
                self.email_provider = SendGridProvider()

        # Rate limiting
        rate_limit = sms_rate_limit or int(os.getenv("SMS_RATE_LIMIT", "10"))
        self.rate_limiter = SMSRateLimiter(max_sms_per_hour=rate_limit)

        # Transcript URL
        self.transcript_base_url = transcript_base_url or os.getenv(
            "TRANSCRIPT_BASE_URL", "https://vozbot.local/transcripts"
        )

    @property
    def twilio_client(self):
        """Get or create the Twilio client.

        Returns:
            Twilio REST client instance.

        Raises:
            ValueError: If Twilio credentials are not configured.
        """
        if self._twilio_client is None:
            if not self.twilio_account_sid or not self.twilio_auth_token:
                raise ValueError(
                    "Twilio credentials not configured. "
                    "Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN environment variables."
                )
            from twilio.rest import Client

            self._twilio_client = Client(
                self.twilio_account_sid, self.twilio_auth_token
            )
        return self._twilio_client

    def _is_urgent_priority(self, priority_value: int) -> bool:
        """Check if a priority value qualifies for SMS notification.

        P0 (4) and P1 (3) are considered urgent.

        Args:
            priority_value: Numeric priority value.

        Returns:
            True if SMS should be sent, False otherwise.
        """
        return priority_value >= NotificationPriority.P1.value

    def _format_sms_message(
        self, callback: CallbackTask, call: Call | None = None
    ) -> str:
        """Format an SMS message for a callback.

        Format: "New urgent callback: [name] [phone] - [intent]"

        Args:
            callback: The callback task.
            call: The associated call (optional, for intent).

        Returns:
            Formatted SMS message.
        """
        name = callback.name or "Unknown"
        phone = callback.callback_number
        intent = call.intent if call else None
        intent_str = intent or "Callback requested"

        return f"New urgent callback: {name} {phone} - {intent_str}"

    def _format_email_subject(
        self, callback: CallbackTask, call: Call | None = None
    ) -> str:
        """Format email subject for a callback.

        Args:
            callback: The callback task.
            call: The associated call (optional).

        Returns:
            Email subject line.
        """
        name = callback.name or "Unknown Caller"
        priority_label = {
            4: "[URGENT]",
            3: "[HIGH]",
            2: "[NORMAL]",
            1: "[LOW]",
        }.get(callback.priority.value, "")

        return f"{priority_label} New Callback: {name}".strip()

    def _format_email_body(
        self, callback: CallbackTask, call: Call | None = None
    ) -> tuple[str, str]:
        """Format email body (HTML and text) for a callback.

        Includes full summary and transcript link.

        Args:
            callback: The callback task.
            call: The associated call (optional).

        Returns:
            Tuple of (html_body, text_body).
        """
        name = callback.name or "Unknown"
        phone = callback.callback_number
        best_time = callback.best_time_window or "Any time"
        notes = callback.notes or "No additional notes"

        # Get call details if available
        summary = call.summary if call else None
        intent = call.intent if call else None
        language = call.language.value if call and call.language else "en"
        call_id = call.id if call else callback.call_id

        transcript_link = f"{self.transcript_base_url}/{call_id}"

        priority_label = {
            4: "URGENT (P0)",
            3: "HIGH (P1)",
            2: "NORMAL (P2)",
            1: "LOW (P3)",
        }.get(callback.priority.value, "UNKNOWN")

        # HTML body
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background-color: #2c3e50; color: white; padding: 20px; }}
        .content {{ padding: 20px; }}
        .field {{ margin-bottom: 15px; }}
        .label {{ font-weight: bold; color: #555; }}
        .value {{ margin-top: 5px; }}
        .priority-urgent {{ color: #e74c3c; font-weight: bold; }}
        .priority-high {{ color: #f39c12; font-weight: bold; }}
        .summary {{ background-color: #f9f9f9; padding: 15px; border-left: 4px solid #3498db; margin: 15px 0; }}
        .transcript-link {{ margin-top: 20px; }}
        .btn {{ display: inline-block; padding: 10px 20px; background-color: #3498db; color: white; text-decoration: none; border-radius: 5px; }}
    </style>
</head>
<body>
    <div class="header">
        <h2>New Callback Request</h2>
    </div>
    <div class="content">
        <div class="field">
            <div class="label">Priority:</div>
            <div class="value {'priority-urgent' if callback.priority.value >= 4 else 'priority-high' if callback.priority.value >= 3 else ''}">{priority_label}</div>
        </div>
        <div class="field">
            <div class="label">Caller Name:</div>
            <div class="value">{name}</div>
        </div>
        <div class="field">
            <div class="label">Callback Number:</div>
            <div class="value"><a href="tel:{phone}">{phone}</a></div>
        </div>
        <div class="field">
            <div class="label">Best Time to Call:</div>
            <div class="value">{best_time}</div>
        </div>
        <div class="field">
            <div class="label">Language:</div>
            <div class="value">{"English" if language == "en" else "Spanish" if language == "es" else language}</div>
        </div>
        {f'<div class="field"><div class="label">Intent:</div><div class="value">{intent}</div></div>' if intent else ''}
        {f'<div class="summary"><div class="label">Call Summary:</div><div class="value">{summary}</div></div>' if summary else ''}
        <div class="field">
            <div class="label">Notes:</div>
            <div class="value">{notes}</div>
        </div>
        <div class="transcript-link">
            <a href="{transcript_link}" class="btn">View Full Transcript</a>
        </div>
    </div>
</body>
</html>
"""

        # Plain text body
        intent_line = f"Intent: {intent}" if intent else ""
        summary_section = f"Call Summary:\n{summary}" if summary else ""

        text_body = f"""New Callback Request
====================

Priority: {priority_label}
Caller Name: {name}
Callback Number: {phone}
Best Time to Call: {best_time}
Language: {"English" if language == "en" else "Spanish" if language == "es" else language}
{intent_line}

{summary_section}

Notes:
{notes}

View Full Transcript: {transcript_link}
"""

        return html_body, text_body

    async def send_sms(
        self,
        to_phone: str,
        message: str,
        bypass_rate_limit: bool = False,
    ) -> NotificationResult:
        """Send an SMS message via Twilio.

        Args:
            to_phone: Recipient phone number.
            message: SMS message content.
            bypass_rate_limit: If True, skip rate limiting (for testing).

        Returns:
            NotificationResult with success status.
        """
        if not bypass_rate_limit and not self.rate_limiter.can_send():
            remaining = self.rate_limiter.get_remaining()
            logger.warning(
                "SMS rate limit exceeded",
                extra={
                    "to_phone": to_phone,
                    "remaining": remaining,
                },
            )
            return NotificationResult(
                success=False,
                provider="twilio",
                error=f"Rate limit exceeded. {remaining} SMS remaining this hour.",
            )

        if not self.twilio_phone_number:
            logger.warning("Twilio phone number not configured, skipping SMS")
            return NotificationResult(
                success=False,
                provider="twilio",
                error="Twilio phone number not configured",
            )

        try:
            sms = self.twilio_client.messages.create(
                body=message,
                from_=self.twilio_phone_number,
                to=to_phone,
            )

            if not bypass_rate_limit:
                self.rate_limiter.record_send()

            logger.info(
                "SMS sent via Twilio",
                extra={
                    "to_phone": to_phone,
                    "message_sid": sms.sid,
                },
            )

            return NotificationResult(
                success=True,
                provider="twilio",
                message_id=sms.sid,
            )

        except Exception as e:
            error_msg = f"Twilio SMS error: {e}"
            logger.exception(error_msg)
            return NotificationResult(
                success=False,
                provider="twilio",
                error=error_msg,
            )

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
    ) -> NotificationResult:
        """Send an email notification.

        Args:
            to_email: Recipient email address.
            subject: Email subject line.
            html_body: HTML content of the email.
            text_body: Plain text content (optional).

        Returns:
            NotificationResult with success status.
        """
        return await self.email_provider.send_email(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )

    async def notify_callback_created(
        self,
        callback: CallbackTask,
        call: Call | None = None,
    ) -> dict[str, NotificationResult]:
        """Send notifications for a newly created callback task.

        Sends SMS for P0/P1 priority callbacks.
        Sends email for all callbacks.

        Args:
            callback: The callback task that was created.
            call: The associated call (optional, for additional context).

        Returns:
            Dict with 'sms' and 'email' NotificationResult entries.
        """
        results: dict[str, NotificationResult] = {}

        # Check if SMS should be sent (P0/P1 priority)
        if self._is_urgent_priority(callback.priority.value):
            if self.staff_phone:
                sms_message = self._format_sms_message(callback, call)
                results["sms"] = await self.send_sms(self.staff_phone, sms_message)
            else:
                logger.warning(
                    "Staff phone not configured, skipping SMS",
                    extra={"callback_id": callback.id},
                )
                results["sms"] = NotificationResult(
                    success=False,
                    provider="twilio",
                    error="Staff phone not configured",
                )
        else:
            # Non-urgent, skip SMS
            results["sms"] = NotificationResult(
                success=True,
                provider="none",
                message_id=None,
                error="Skipped - not urgent priority",
            )

        # Always send email
        if self.staff_email:
            subject = self._format_email_subject(callback, call)
            html_body, text_body = self._format_email_body(callback, call)
            results["email"] = await self.send_email(
                to_email=self.staff_email,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
            )
        else:
            logger.warning(
                "Staff email not configured, skipping email",
                extra={"callback_id": callback.id},
            )
            results["email"] = NotificationResult(
                success=False,
                provider="none",
                error="Staff email not configured",
            )

        return results
