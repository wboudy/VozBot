"""Integration tests for transfer fallback to callback functionality.

These tests verify the complete flow when a transfer fails:
1. Twilio sends transfer-status webhook with failure status
2. System creates a critical priority callback task
3. Caller hears bilingual fallback message

Note: These tests do NOT require Twilio credentials as they mock the
database layer and only test the webhook handler logic.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from vozbot.telephony.webhooks.twilio_webhooks import router


@pytest.fixture
def app():
    """Create a FastAPI app with Twilio router for testing."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_env_dev():
    """Mock development environment with validation skipped."""
    with patch.dict(os.environ, {
        "APP_ENV": "development",
        "SKIP_TWILIO_VALIDATION": "true",
        "TWILIO_AUTH_TOKEN": "test_token",
        "TWILIO_ACCOUNT_SID": "test_sid",
    }):
        yield


class TestTransferTimeoutCreatesCallbackTask:
    """Integration test: transfer timeout triggers callback task creation."""

    def test_transfer_timeout_creates_callback_task_integration(
        self, client, mock_env_dev
    ) -> None:
        """Integration test: transfer timeout triggers callback task creation.

        Simulates the complete flow:
        1. Call comes in, transfer is initiated
        2. Transfer times out (no-answer)
        3. Callback task is created with critical priority
        4. Caller hears fallback message
        """
        from vozbot.storage.db.models import (
            Call,
            CallbackTask,
            TaskPriority,
            TaskStatus,
        )

        # Create a mock call that exists in the database
        mock_call = MagicMock(spec=Call)
        mock_call.id = "CA_TIMEOUT_TEST"
        mock_call.from_number = "+15551234567"

        # Track created callback task
        created_tasks = []

        def capture_task(task):
            if isinstance(task, CallbackTask):
                created_tasks.append(task)

        # Create mock session
        mock_session = AsyncMock()
        mock_session.add = MagicMock(side_effect=capture_task)
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()

        # Create mock service
        mock_service = MagicMock()
        mock_service.get_call = AsyncMock(return_value=mock_call)
        mock_service.update_call_status = AsyncMock(return_value=mock_call)

        with patch(
            "vozbot.storage.db.session.get_db_session"
        ) as mock_get_session:
            # Setup async context manager
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_get_session.return_value = mock_context

            with patch(
                "vozbot.storage.services.call_service.CallService"
            ) as mock_service_class:
                mock_service_class.return_value = mock_service

                # Simulate Twilio sending transfer-status callback with no-answer
                response = client.post(
                    "/webhooks/twilio/transfer-status",
                    data={
                        "CallSid": "CA_TIMEOUT_TEST",
                        "DialCallSid": "CA_OUTBOUND_LEG",
                        "DialCallStatus": "no-answer",  # Transfer timed out
                        "Called": "+15559999999",
                    },
                )

                # Verify webhook returns success
                assert response.status_code == 200

                # Verify callback task was created
                assert len(created_tasks) == 1
                task = created_tasks[0]

                # Verify task properties match requirements
                assert task.priority == TaskPriority.CRITICAL
                assert task.callback_number == "+15551234567"
                assert task.notes == "Transfer failed - urgent callback"
                assert task.status == TaskStatus.PENDING
                assert task.call_id == "CA_TIMEOUT_TEST"

                # Verify response contains fallback messages
                content = response.json()

                # English message
                assert "no one is available" in content
                assert "call you back within 1 hour" in content

                # Spanish message
                assert "no hay nadie disponible" in content
                assert "dentro de 1 hora" in content

                # Should end call
                assert "<Hangup" in content


class TestTransferBusyCreatesCallbackTask:
    """Integration test: busy transfer target triggers callback task."""

    def test_transfer_busy_creates_callback_task_integration(
        self, client, mock_env_dev
    ) -> None:
        """Test that busy transfer target creates a critical callback task."""
        from vozbot.storage.db.models import Call, CallbackTask, TaskPriority

        mock_call = MagicMock(spec=Call)
        mock_call.id = "CA_BUSY_TEST"
        mock_call.from_number = "+15559876543"

        created_tasks = []

        def capture_task(task):
            if isinstance(task, CallbackTask):
                created_tasks.append(task)

        mock_session = AsyncMock()
        mock_session.add = MagicMock(side_effect=capture_task)
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()

        mock_service = MagicMock()
        mock_service.get_call = AsyncMock(return_value=mock_call)
        mock_service.update_call_status = AsyncMock(return_value=mock_call)

        with patch(
            "vozbot.storage.db.session.get_db_session"
        ) as mock_get_session:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_get_session.return_value = mock_context

            with patch(
                "vozbot.storage.services.call_service.CallService"
            ) as mock_service_class:
                mock_service_class.return_value = mock_service

                response = client.post(
                    "/webhooks/twilio/transfer-status",
                    data={
                        "CallSid": "CA_BUSY_TEST",
                        "DialCallStatus": "busy",
                        "Called": "+15551111111",
                    },
                )

                assert response.status_code == 200
                assert len(created_tasks) == 1
                assert created_tasks[0].priority == TaskPriority.CRITICAL
                assert created_tasks[0].callback_number == "+15559876543"


class TestTransferSuccessNoCallbackTask:
    """Integration test: successful transfer does NOT create callback task."""

    def test_transfer_success_no_callback_task_integration(
        self, client, mock_env_dev
    ) -> None:
        """Test that successful transfer does not create a callback task."""
        from vozbot.storage.db.models import CallbackTask

        created_tasks = []

        def capture_task(task):
            if isinstance(task, CallbackTask):
                created_tasks.append(task)

        mock_session = AsyncMock()
        mock_session.add = MagicMock(side_effect=capture_task)
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()

        mock_service = MagicMock()
        mock_service.complete_call = AsyncMock()

        with patch(
            "vozbot.storage.db.session.get_db_session"
        ) as mock_get_session:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_get_session.return_value = mock_context

            with patch(
                "vozbot.storage.services.call_service.CallService"
            ) as mock_service_class:
                mock_service_class.return_value = mock_service

                response = client.post(
                    "/webhooks/twilio/transfer-status",
                    data={
                        "CallSid": "CA_SUCCESS_TEST",
                        "DialCallStatus": "completed",
                        "DialCallDuration": "120",
                    },
                )

                assert response.status_code == 200
                # No callback task should be created for successful transfer
                assert len(created_tasks) == 0

                # Response should NOT contain fallback messages
                content = response.json()
                assert "no one is available" not in content
                assert "<Hangup" not in content


class TestAllFailureStatusesCreateCallback:
    """Integration test: all failure statuses create callback tasks."""

    def test_all_failure_statuses_create_callback_integration(
        self, client, mock_env_dev
    ) -> None:
        """Test that all failure statuses (busy, no-answer, failed, canceled) create callback tasks."""
        from vozbot.storage.db.models import Call, CallbackTask, TaskPriority

        failure_statuses = ["busy", "no-answer", "failed", "canceled"]

        for status in failure_statuses:
            mock_call = MagicMock(spec=Call)
            mock_call.id = f"CA_{status.upper()}_TEST"
            mock_call.from_number = "+15551234567"

            created_tasks = []

            def capture_task(task):
                if isinstance(task, CallbackTask):
                    created_tasks.append(task)

            mock_session = AsyncMock()
            mock_session.add = MagicMock(side_effect=capture_task)
            mock_session.commit = AsyncMock()
            mock_session.flush = AsyncMock()

            mock_service = MagicMock()
            mock_service.get_call = AsyncMock(return_value=mock_call)
            mock_service.update_call_status = AsyncMock(return_value=mock_call)

            with patch(
                "vozbot.storage.db.session.get_db_session"
            ) as mock_get_session:
                mock_context = AsyncMock()
                mock_context.__aenter__.return_value = mock_session
                mock_context.__aexit__.return_value = None
                mock_get_session.return_value = mock_context

                with patch(
                    "vozbot.storage.services.call_service.CallService"
                ) as mock_service_class:
                    mock_service_class.return_value = mock_service

                    response = client.post(
                        "/webhooks/twilio/transfer-status",
                        data={
                            "CallSid": f"CA_{status.upper()}_TEST",
                            "DialCallStatus": status,
                        },
                    )

                    assert response.status_code == 200, f"Failed for status: {status}"
                    assert len(created_tasks) == 1, f"No task created for status: {status}"
                    assert created_tasks[0].priority == TaskPriority.CRITICAL, (
                        f"Wrong priority for status: {status}"
                    )
