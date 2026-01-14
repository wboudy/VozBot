"""Twilio webhook handlers for incoming calls.

Provides FastAPI route handlers for Twilio voice webhooks with
request signature validation and call metadata persistence.
"""

from __future__ import annotations

import logging
import os
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Request, status
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import VoiceResponse

from vozbot.storage.db.models import CallStatus as DBCallStatus
from vozbot.telephony.adapters.twilio_adapter import TwilioAdapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/twilio", tags=["twilio"])


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

    # Generate bilingual greeting
    response = TwilioAdapter.generate_bilingual_greeting_twiml(
        english_text=(
            "Hello, this is VozBot, the automated assistant for the insurance office. "
            "For English, press 1 or stay on the line. "
        ),
        spanish_text=(
            "Hola, soy VozBot, el asistente automatico de la oficina de seguros. "
            "Para espanol, presione 2. "
        ),
        gather_action_url=f"{request.base_url}webhooks/twilio/language-select",
    )

    logger.info("Call answered with bilingual greeting", extra={"call_sid": CallSid})

    return str(response)


@router.post("/language-select")
async def handle_language_selection(
    request: Request,
    CallSid: Annotated[str, Form()],
    Digits: Annotated[str | None, Form()] = None,
    _validated: bool = Depends(validate_twilio_signature),
) -> str:
    """Handle language selection DTMF input.

    Args:
        request: FastAPI request object.
        CallSid: Unique identifier for the call.
        Digits: DTMF digits entered by caller.

    Returns:
        TwiML response as XML string.
    """
    response = VoiceResponse()

    # Determine language from input
    if Digits == "2":
        # Spanish selected
        response.say(
            "Gracias. Un momento, por favor, mientras procesamos su llamada.",
            language="es-MX",
        )
        # TODO: Continue to Spanish call flow
    else:
        # Default to English (1 or no input)
        response.say(
            "Thank you. Please hold while we process your call.",
            language="en-US",
        )
        # TODO: Continue to English call flow

    # For now, just acknowledge and hang up (Phase 0)
    response.say(
        "Your call has been received. A representative will call you back shortly. Goodbye.",
        language="en-US" if Digits != "2" else "es-MX",
    )
    response.hangup()

    return str(response)


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
