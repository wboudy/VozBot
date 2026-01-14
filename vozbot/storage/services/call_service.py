"""Call service - business logic for call data operations.

Provides methods for creating, updating, and querying call records.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from vozbot.storage.db.models import Call, CallStatus, Language

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class CallService:
    """Service for managing call records in the database."""

    def __init__(self, session: AsyncSession):
        """Initialize call service with database session.

        Args:
            session: Async SQLAlchemy session.
        """
        self.session = session

    async def create_call(
        self,
        from_number: str,
        call_sid: str | None = None,
        language: Language | None = None,
    ) -> Call:
        """Create a new call record.

        Args:
            from_number: Caller's phone number.
            call_sid: Twilio Call SID (used as ID if provided).
            language: Detected/selected language.

        Returns:
            Created Call object.
        """
        call = Call(
            id=call_sid or str(uuid4()),
            from_number=from_number,
            language=language,
            status=CallStatus.INIT,
        )

        self.session.add(call)
        await self.session.flush()

        logger.info(
            "Created call record",
            extra={
                "call_id": call.id,
                "from_number": from_number,
                "status": call.status.value,
            },
        )

        return call

    async def get_call(self, call_id: str) -> Call | None:
        """Get a call by ID.

        Args:
            call_id: Call ID (UUID or Twilio SID).

        Returns:
            Call object if found, None otherwise.
        """
        result = await self.session.execute(
            select(Call).where(Call.id == call_id)
        )
        return result.scalar_one_or_none()

    async def update_call_status(
        self,
        call_id: str,
        status: CallStatus,
    ) -> Call | None:
        """Update a call's status.

        Args:
            call_id: Call ID to update.
            status: New status.

        Returns:
            Updated Call object if found, None otherwise.
        """
        call = await self.get_call(call_id)
        if call is None:
            logger.warning(
                "Call not found for status update",
                extra={"call_id": call_id, "status": status.value},
            )
            return None

        call.status = status
        call.updated_at = datetime.now()
        await self.session.flush()

        logger.info(
            "Updated call status",
            extra={
                "call_id": call_id,
                "status": status.value,
            },
        )

        return call

    async def update_call_language(
        self,
        call_id: str,
        language: Language,
    ) -> Call | None:
        """Update a call's language.

        Args:
            call_id: Call ID to update.
            language: Selected/detected language.

        Returns:
            Updated Call object if found, None otherwise.
        """
        call = await self.get_call(call_id)
        if call is None:
            return None

        call.language = language
        call.updated_at = datetime.now()
        await self.session.flush()

        logger.info(
            "Updated call language",
            extra={
                "call_id": call_id,
                "language": language.value,
            },
        )

        return call

    async def complete_call(
        self,
        call_id: str,
        duration_sec: int | None = None,
        summary: str | None = None,
    ) -> Call | None:
        """Mark a call as completed.

        Args:
            call_id: Call ID to complete.
            duration_sec: Call duration in seconds.
            summary: Optional call summary.

        Returns:
            Updated Call object if found, None otherwise.
        """
        call = await self.get_call(call_id)
        if call is None:
            return None

        call.status = CallStatus.COMPLETED
        call.updated_at = datetime.now()

        if summary:
            call.summary = summary

        if duration_sec is not None and call.costs is None:
            call.costs = {"duration_sec": duration_sec}
        elif duration_sec is not None:
            call.costs["duration_sec"] = duration_sec

        await self.session.flush()

        logger.info(
            "Call completed",
            extra={
                "call_id": call_id,
                "duration_sec": duration_sec,
            },
        )

        return call


async def create_call_safe(
    session: AsyncSession,
    from_number: str,
    call_sid: str | None = None,
    language: Language | None = None,
) -> Call | None:
    """Create a call record with error handling.

    This function catches database errors to prevent call failures
    when the database is unavailable.

    Args:
        session: Database session.
        from_number: Caller's phone number.
        call_sid: Twilio Call SID.
        language: Detected/selected language.

    Returns:
        Created Call object, or None if creation failed.
    """
    try:
        service = CallService(session)
        return await service.create_call(from_number, call_sid, language)
    except SQLAlchemyError as e:
        logger.error(
            "Failed to create call record",
            extra={
                "from_number": from_number,
                "call_sid": call_sid,
                "error": str(e),
            },
        )
        return None


async def update_call_status_safe(
    session: AsyncSession,
    call_id: str,
    status: CallStatus,
) -> bool:
    """Update call status with error handling.

    Args:
        session: Database session.
        call_id: Call ID to update.
        status: New status.

    Returns:
        True if update succeeded, False otherwise.
    """
    try:
        service = CallService(session)
        call = await service.update_call_status(call_id, status)
        return call is not None
    except SQLAlchemyError as e:
        logger.error(
            "Failed to update call status",
            extra={
                "call_id": call_id,
                "status": status.value,
                "error": str(e),
            },
        )
        return False
