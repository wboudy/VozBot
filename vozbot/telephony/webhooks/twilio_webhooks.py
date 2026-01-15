"""Twilio webhook handlers for incoming calls.

Provides FastAPI route handlers for Twilio voice webhooks with
request signature validation and call metadata persistence.
"""

from __future__ import annotations

import logging
import os
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Query, Request, status
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import VoiceResponse

from vozbot.storage.db.models import CallStatus as DBCallStatus
from vozbot.storage.db.models import Language
from vozbot.telephony.adapters.twilio_adapter import TwilioAdapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/twilio", tags=["twilio"])

# Language detection constants
MAX_LANGUAGE_ATTEMPTS = 3
ENGLISH_SPEECH_PATTERNS = {"english", "inglés", "ingles", "one", "uno", "1"}
SPANISH_SPEECH_PATTERNS = {"spanish", "español", "espanol", "two", "dos", "2"}


def detect_language_from_input(
    digits: str | None = None,
    speech_result: str | None = None,
) -> Language | None:
    """Detect language selection from DTMF digits or speech input.

    Args:
        digits: DTMF digit pressed (1 for English, 2 for Spanish).
        speech_result: Speech recognition result.

    Returns:
        Language enum (EN or ES) if detected, None otherwise.
    """
    # Check DTMF input first
    if digits:
        if digits == "1":
            return Language.EN
        elif digits == "2":
            return Language.ES
        # Any other digit is invalid
        return None

    # Check speech input
    if speech_result:
        speech_lower = speech_result.lower().strip()
        # Check for English patterns
        for pattern in ENGLISH_SPEECH_PATTERNS:
            if pattern in speech_lower:
                return Language.EN
        # Check for Spanish patterns
        for pattern in SPANISH_SPEECH_PATTERNS:
            if pattern in speech_lower:
                return Language.ES

    return None


def get_twilio_adapter() -> TwilioAdapter:
    """Dependency to get TwilioAdapter instance."""
    return TwilioAdapter()


def get_request_validator() -> RequestValidator:
    """Dependency to get Twilio request validator."""
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    return RequestValidator(auth_token)


async def validate_twilio_signature(
    request: Request,
    x_twilio_signature: Annotated[str | None, Header()] = None,
) -> bool:
    """Validate incoming request is from Twilio.

    Args:
        request: FastAPI request object.
        x_twilio_signature: Twilio signature header.

    Returns:
        True if signature is valid.

    Raises:
        HTTPException: If signature validation fails.
    """
    # Skip validation in test/development mode
    if os.getenv("APP_ENV") in ("development", "test"):
        skip_validation = os.getenv("SKIP_TWILIO_VALIDATION", "false").lower() == "true"
        if skip_validation:
            return True

    if not x_twilio_signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Twilio signature header",
        )

    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Twilio auth token not configured",
        )

    validator = RequestValidator(auth_token)

    # Get the full URL
    url = str(request.url)

    # Get form data for validation
    form_data = await request.form()
    params = dict(form_data.items())

    # Validate the request
    is_valid = validator.validate(url, params, x_twilio_signature)

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Twilio signature",
        )

    return True


@router.post("/voice")
async def handle_incoming_call(
    request: Request,
    CallSid: Annotated[str, Form()],
    From: Annotated[str, Form()],
    To: Annotated[str, Form()],
    CallStatus: Annotated[str, Form()],
    Direction: Annotated[str, Form()] = "inbound",
    _validated: bool = Depends(validate_twilio_signature),
) -> str:
    """Handle incoming voice calls from Twilio.

    This is the primary webhook that Twilio calls when a new call comes in.
    Returns TwiML to control the call flow.

    Args:
        request: FastAPI request object.
        CallSid: Unique identifier for the call.
        From: Caller's phone number.
        To: Called phone number (your Twilio number).
        CallStatus: Current status of the call.
        Direction: Call direction (inbound/outbound).

    Returns:
        TwiML response as XML string.
    """
    logger.info(
        "Incoming call received",
        extra={
            "call_sid": CallSid,
            "from_number": From,
            "to_number": To,
            "status": CallStatus,
            "direction": Direction,
        },
    )

    # Try to create call record in database (non-blocking)
    try:
        from vozbot.storage.db.session import get_db_session
        from vozbot.storage.services.call_service import CallService

        async with get_db_session() as session:
            service = CallService(session)
            await service.create_call(from_number=From, call_sid=CallSid)
            logger.info("Call record created", extra={"call_sid": CallSid})
    except Exception as e:
        # Log but don't fail the call
        logger.error(
            "Failed to create call record (continuing call)",
            extra={"call_sid": CallSid, "error": str(e)},
        )

    # Generate bilingual greeting with language selection menu
    response = TwilioAdapter.generate_bilingual_greeting_twiml(
        english_text=(
            "Hello, this is VozBot, the automated assistant for the insurance office. "
            "Press 1 for English. "
        ),
        spanish_text=(
            "Hola, soy VozBot, el asistente automatico de la oficina de seguros. "
            "Presione 2 para español. "
        ),
        gather_action_url=f"{request.base_url}webhooks/twilio/language-select?attempt=1",
        timeout=10,
    )

    logger.info("Call answered with bilingual greeting", extra={"call_sid": CallSid})

    return str(response)


@router.post("/language-select")
async def handle_language_selection(
    request: Request,
    CallSid: Annotated[str, Form()],
    Digits: Annotated[str | None, Form()] = None,
    SpeechResult: Annotated[str | None, Form()] = None,
    attempt: int = Query(default=1),
    timeout: bool = Query(default=False),
    _validated: bool = Depends(validate_twilio_signature),
) -> str:
    """Handle language selection DTMF or speech input.

    Implements retry logic for failed attempts and timeout handling.

    Args:
        request: FastAPI request object.
        CallSid: Unique identifier for the call.
        Digits: DTMF digits entered by caller.
        SpeechResult: Speech recognition result.
        attempt: Current attempt number (1-3).
        timeout: Whether this is a timeout redirect.

    Returns:
        TwiML response as XML string.
    """
    logger.info(
        "Language selection input received",
        extra={
            "call_sid": CallSid,
            "digits": Digits,
            "speech_result": SpeechResult,
            "attempt": attempt,
            "timeout": timeout,
        },
    )

    response = VoiceResponse()

    # Detect language from input
    detected_language = detect_language_from_input(
        digits=Digits,
        speech_result=SpeechResult,
    )

    # Handle timeout or failed detection
    if detected_language is None:
        # Check if we've exceeded max attempts
        if attempt >= MAX_LANGUAGE_ATTEMPTS:
            # Default to English after 3 failed attempts
            logger.info(
                "Max language selection attempts reached, defaulting to English",
                extra={"call_sid": CallSid, "attempts": attempt},
            )
            detected_language = Language.EN
            # Inform caller we're defaulting to English
            response.say(
                "We did not receive a valid selection. Defaulting to English.",
                language="en-US",
            )
        else:
            # Retry - play prompt again
            next_attempt = attempt + 1
            logger.info(
                "Language selection failed, retrying",
                extra={"call_sid": CallSid, "next_attempt": next_attempt},
            )

            # Play retry message based on what happened
            if timeout:
                # Timeout message
                response.say(
                    "We did not receive your selection.",
                    language="en-US",
                )
                response.say(
                    "No recibimos su selección.",
                    language="es-MX",
                )
            else:
                # Invalid input message
                response.say(
                    "Sorry, we did not understand your selection.",
                    language="en-US",
                )
                response.say(
                    "Lo siento, no entendimos su selección.",
                    language="es-MX",
                )

            # Gather again with incremented attempt
            gather = response.gather(
                num_digits=1,
                action=f"{request.base_url}webhooks/twilio/language-select?attempt={next_attempt}",
                method="POST",
                timeout=10,
                input="dtmf speech",
                hints="English, inglés, Spanish, español, one, two, uno, dos",
                speech_timeout="auto",
                language="en-US",
            )

            gather.say(
                "Press 1 for English.",
                language="en-US",
            )
            gather.say(
                "Presione 2 para español.",
                language="es-MX",
            )

            # Redirect on timeout
            response.redirect(
                f"{request.base_url}webhooks/twilio/language-select?attempt={next_attempt}&timeout=true"
            )

            return str(response)

    # Language was detected successfully - store in database
    await _store_language_selection(CallSid, detected_language)

    # Play confirmation message in selected language
    if detected_language == Language.ES:
        response.say(
            "Gracias. Ha seleccionado español.",
            language="es-MX",
        )
        # For now, acknowledge and end call (Phase 0)
        response.say(
            "Su llamada ha sido recibida. Un representante le devolverá la llamada pronto. Adiós.",
            language="es-MX",
        )
    else:
        response.say(
            "Thank you. You have selected English.",
            language="en-US",
        )
        # For now, acknowledge and end call (Phase 0)
        response.say(
            "Your call has been received. A representative will call you back shortly. Goodbye.",
            language="en-US",
        )

    response.hangup()

    logger.info(
        "Language selection completed",
        extra={
            "call_sid": CallSid,
            "language": detected_language.value,
        },
    )

    return str(response)


async def _store_language_selection(call_sid: str, language: Language) -> None:
    """Store the selected language in the call record.

    Args:
        call_sid: Call SID to update.
        language: Selected language.
    """
    try:
        from vozbot.storage.db.session import get_db_session
        from vozbot.storage.services.call_service import CallService

        async with get_db_session() as session:
            service = CallService(session)
            await service.update_call_language(call_sid, language)
            # Also update status to LANGUAGE_SELECT to indicate we're past that stage
            await service.update_call_status(call_sid, DBCallStatus.LANGUAGE_SELECT)
            await session.commit()
            logger.info(
                "Language stored in database",
                extra={"call_sid": call_sid, "language": language.value},
            )
    except Exception as e:
        # Log but don't fail the call
        logger.error(
            "Failed to store language selection (continuing call)",
            extra={"call_sid": call_sid, "language": language.value, "error": str(e)},
        )


@router.post("/status")
async def handle_call_status(
    request: Request,
    CallSid: Annotated[str, Form()],
    CallStatus: Annotated[str, Form()],
    CallDuration: Annotated[str | None, Form()] = None,
    RecordingUrl: Annotated[str | None, Form()] = None,
    _validated: bool = Depends(validate_twilio_signature),
) -> str:
    """Handle call status callbacks.

    Twilio sends these when call status changes (e.g., completed, failed).

    Args:
        request: FastAPI request object.
        CallSid: Unique identifier for the call.
        CallStatus: New status of the call.
        CallDuration: Duration of the call in seconds.
        RecordingUrl: URL to the call recording (if recorded).

    Returns:
        Empty TwiML response.
    """
    logger.info(
        "Call status update received",
        extra={
            "call_sid": CallSid,
            "status": CallStatus,
            "duration": CallDuration,
            "recording_url": RecordingUrl,
        },
    )

    # Update call record in database if call completed
    if CallStatus in ("completed", "failed", "busy", "no-answer", "canceled"):
        try:
            from vozbot.storage.db.session import get_db_session
            from vozbot.storage.services.call_service import CallService

            async with get_db_session() as session:
                service = CallService(session)
                duration_sec = int(CallDuration) if CallDuration else None

                if CallStatus == "completed":
                    await service.complete_call(
                        call_id=CallSid,
                        duration_sec=duration_sec,
                    )
                    logger.info(
                        "Call completed",
                        extra={
                            "call_sid": CallSid,
                            "duration_sec": duration_sec,
                        },
                    )
                else:
                    # Map Twilio status to our CallStatus enum
                    status_map = {
                        "failed": DBCallStatus.FAILED,
                        "busy": DBCallStatus.FAILED,
                        "no-answer": DBCallStatus.FAILED,
                        "canceled": DBCallStatus.FAILED,
                    }
                    db_status = status_map.get(CallStatus, DBCallStatus.FAILED)
                    await service.update_call_status(CallSid, db_status)
                    logger.info(
                        "Call ended with status",
                        extra={
                            "call_sid": CallSid,
                            "status": CallStatus,
                        },
                    )
        except Exception as e:
            # Log but don't fail the callback
            logger.error(
                "Failed to update call status in database (continuing)",
                extra={"call_sid": CallSid, "error": str(e)},
            )

    response = VoiceResponse()
    return str(response)


@router.post("/recording")
async def handle_recording_callback(
    request: Request,
    CallSid: Annotated[str, Form()],
    RecordingSid: Annotated[str, Form()],
    RecordingUrl: Annotated[str, Form()],
    RecordingStatus: Annotated[str, Form()],
    RecordingDuration: Annotated[str | None, Form()] = None,
    _validated: bool = Depends(validate_twilio_signature),
) -> str:
    """Handle recording completion callbacks.

    Twilio sends these when a recording is completed and available.

    Args:
        request: FastAPI request object.
        CallSid: Unique identifier for the call.
        RecordingSid: Unique identifier for the recording.
        RecordingUrl: URL to access the recording.
        RecordingStatus: Status of the recording.
        RecordingDuration: Duration of recording in seconds.

    Returns:
        Empty TwiML response.
    """
    # TODO: Save recording URL to call record
    # TODO: Trigger transcription if enabled

    response = VoiceResponse()
    return str(response)


# Transfer failure fallback messages
TRANSFER_FALLBACK_MESSAGE_EN = (
    "I'm sorry, no one is available. We will call you back within 1 hour."
)
TRANSFER_FALLBACK_MESSAGE_ES = (
    "Lo siento, no hay nadie disponible. Le devolveremos la llamada dentro de 1 hora."
)
TRANSFER_FAILED_NOTES = "Transfer failed - urgent callback"


@router.post("/transfer-status")
async def handle_transfer_status(
    request: Request,
    CallSid: Annotated[str, Form()],
    DialCallSid: Annotated[str | None, Form()] = None,
    DialCallStatus: Annotated[str | None, Form()] = None,
    DialCallDuration: Annotated[str | None, Form()] = None,
    Called: Annotated[str | None, Form()] = None,
    CallStatus: Annotated[str | None, Form()] = None,
    _validated: bool = Depends(validate_twilio_signature),
) -> str:
    """Handle call transfer status callbacks.

    Twilio sends these to report the status of a transfer/dial operation.
    Status events include: initiated, ringing, answered, completed.

    On transfer failure (busy, no-answer, failed, canceled):
    - Creates a critical priority callback task
    - Plays fallback message in English and Spanish
    - Task notes include "Transfer failed - urgent callback"

    Args:
        request: FastAPI request object.
        CallSid: Original call SID (the call being transferred).
        DialCallSid: SID of the outbound call leg to the transfer target.
        DialCallStatus: Status of the dial attempt (e.g., 'answered', 'busy', 'no-answer').
        DialCallDuration: Duration of the connected call in seconds.
        Called: The number that was dialed (transfer target).
        CallStatus: Status of the callback event.

    Returns:
        TwiML response. If transfer failed, returns fallback TwiML with callback promise.
    """
    logger.info(
        "Transfer status callback received",
        extra={
            "call_sid": CallSid,
            "dial_call_sid": DialCallSid,
            "dial_call_status": DialCallStatus,
            "dial_call_duration": DialCallDuration,
            "called": Called,
            "call_status": CallStatus,
        },
    )

    response = VoiceResponse()

    # Handle different dial outcomes
    if DialCallStatus:
        if DialCallStatus == "completed":
            # Transfer completed successfully
            logger.info(
                "Transfer completed successfully",
                extra={
                    "call_sid": CallSid,
                    "dial_call_sid": DialCallSid,
                    "duration": DialCallDuration,
                },
            )
            # Update call record if needed
            await _update_transfer_status(CallSid, "completed", DialCallDuration)

        elif DialCallStatus == "answered":
            # Transfer target answered - call is connected
            logger.info(
                "Transfer connected",
                extra={
                    "call_sid": CallSid,
                    "dial_call_sid": DialCallSid,
                },
            )
            await _update_transfer_status(CallSid, "connected", None)

        elif DialCallStatus in ("busy", "no-answer", "failed", "canceled"):
            # Transfer failed - create callback task and provide fallback
            logger.warning(
                "Transfer failed - triggering fallback to callback",
                extra={
                    "call_sid": CallSid,
                    "dial_call_status": DialCallStatus,
                    "target": Called,
                },
            )

            # Update call status and create critical callback task
            # This is wrapped in try/except so caller still gets fallback message
            try:
                await _handle_transfer_failure(CallSid, DialCallStatus, Called)
            except Exception as e:
                logger.error(
                    "Error in transfer failure handler (continuing with fallback message)",
                    extra={"call_sid": CallSid, "error": str(e)},
                )

            # Provide fallback message to caller (bilingual)
            response.say(
                TRANSFER_FALLBACK_MESSAGE_EN,
                language="en-US",
            )
            response.say(
                TRANSFER_FALLBACK_MESSAGE_ES,
                language="es-MX",
            )
            response.hangup()

    return str(response)


async def _handle_transfer_failure(
    call_sid: str,
    dial_status: str,
    target_number: str | None,
) -> None:
    """Handle transfer failure by updating status and creating callback task.

    Creates a critical priority callback task when transfer fails.
    The callback task has notes indicating "Transfer failed - urgent callback".

    Args:
        call_sid: The call SID that failed to transfer.
        dial_status: The dial status (busy, no-answer, failed, canceled).
        target_number: The target number that was being dialed.
    """
    try:
        from uuid import uuid4

        from vozbot.storage.db.models import CallbackTask, TaskPriority, TaskStatus
        from vozbot.storage.db.session import get_db_session
        from vozbot.storage.services.call_service import CallService

        async with get_db_session() as session:
            service = CallService(session)

            # Get the call to extract caller info for callback task
            call = await service.get_call(call_sid)
            if call is None:
                logger.warning(
                    "Call not found for transfer failure callback task",
                    extra={"call_sid": call_sid},
                )
                return

            # Update call status to FAILED
            await service.update_call_status(call_sid, DBCallStatus.FAILED)

            # Create critical priority callback task
            callback_task = CallbackTask(
                id=str(uuid4()),
                call_id=call_sid,
                priority=TaskPriority.CRITICAL,  # priority=0 (critical)
                callback_number=call.from_number,
                notes=TRANSFER_FAILED_NOTES,  # "Transfer failed - urgent callback"
                status=TaskStatus.PENDING,
            )

            session.add(callback_task)
            await session.commit()

            logger.info(
                "Created critical callback task for failed transfer",
                extra={
                    "call_sid": call_sid,
                    "task_id": callback_task.id,
                    "priority": TaskPriority.CRITICAL.value,
                    "dial_status": dial_status,
                    "target_number": target_number,
                },
            )
    except Exception as e:
        # Log but don't fail the callback - caller still gets fallback message
        logger.error(
            "Failed to create callback task for transfer failure",
            extra={
                "call_sid": call_sid,
                "dial_status": dial_status,
                "error": str(e),
            },
        )


async def _update_transfer_status(
    call_sid: str,
    status: str,
    duration: str | None,
) -> None:
    """Update call record with transfer status.

    Args:
        call_sid: The call SID to update.
        status: Transfer status (connected, completed, failed).
        duration: Duration of the transfer in seconds.
    """
    try:
        from vozbot.storage.db.session import get_db_session
        from vozbot.storage.services.call_service import CallService

        async with get_db_session() as session:
            service = CallService(session)

            if status == "completed" and duration:
                # Mark call as completed with duration
                await service.complete_call(
                    call_id=call_sid,
                    duration_sec=int(duration),
                )
            elif status == "connected":
                # Update status to show transfer is active
                await service.update_call_status(call_sid, DBCallStatus.IN_PROGRESS)
            elif status == "failed":
                # Mark transfer as failed
                await service.update_call_status(call_sid, DBCallStatus.FAILED)

            await session.commit()
            logger.info(
                "Transfer status updated in database",
                extra={"call_sid": call_sid, "status": status},
            )
    except Exception as e:
        # Log but don't fail the callback
        logger.error(
            "Failed to update transfer status in database",
            extra={"call_sid": call_sid, "status": status, "error": str(e)},
        )
