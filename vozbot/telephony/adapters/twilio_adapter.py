"""Twilio implementation of the TelephonyAdapter interface.

Provides call control operations through the Twilio API and TwiML generation.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING

from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse

from vozbot.telephony.adapters.base import CallInfo, CallStatus, TelephonyAdapter

if TYPE_CHECKING:
    from twilio.rest.api.v2010.account.call import CallInstance

logger = logging.getLogger(__name__)

# Default hold music URL (Twilio's default classical hold music)
DEFAULT_HOLD_MUSIC_URL = "http://com.twilio.sounds.music.s3.amazonaws.com/ClockworkWaltz.mp3"


class TwilioAdapter(TelephonyAdapter):
    """Twilio implementation of the TelephonyAdapter interface.

    Uses the Twilio REST API for call control operations and generates
    TwiML for in-call actions like playing audio and transfers.

    Environment Variables:
        TWILIO_ACCOUNT_SID: Twilio account SID
        TWILIO_AUTH_TOKEN: Twilio auth token
        TWILIO_PHONE_NUMBER: Twilio phone number for outbound calls
        TRANSFER_NUMBER: Default target number for call transfers
        TRANSFER_TIMEOUT: Transfer ring timeout in seconds (default: 30)
        HOLD_MUSIC_URL: URL for hold music during transfer (optional)

    Example:
        ```python
        adapter = TwilioAdapter()
        await adapter.answer_call("CA123456")
        ```
    """

    def __init__(
        self,
        account_sid: str | None = None,
        auth_token: str | None = None,
        phone_number: str | None = None,
        transfer_number: str | None = None,
        transfer_timeout: int | None = None,
        hold_music_url: str | None = None,
    ) -> None:
        """Initialize the Twilio adapter.

        Args:
            account_sid: Twilio account SID. Defaults to TWILIO_ACCOUNT_SID env var.
            auth_token: Twilio auth token. Defaults to TWILIO_AUTH_TOKEN env var.
            phone_number: Twilio phone number. Defaults to TWILIO_PHONE_NUMBER env var.
            transfer_number: Default transfer target. Defaults to TRANSFER_NUMBER env var.
            transfer_timeout: Transfer ring timeout in seconds. Defaults to TRANSFER_TIMEOUT env var or 30.
            hold_music_url: URL for hold music. Defaults to HOLD_MUSIC_URL env var.
        """
        self.account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID", "")
        self.auth_token = auth_token or os.getenv("TWILIO_AUTH_TOKEN", "")
        self.phone_number = phone_number or os.getenv("TWILIO_PHONE_NUMBER", "")
        self.transfer_number = transfer_number or os.getenv("TRANSFER_NUMBER", "")
        self.transfer_timeout = transfer_timeout or int(os.getenv("TRANSFER_TIMEOUT", "30"))
        self.hold_music_url = hold_music_url or os.getenv("HOLD_MUSIC_URL", DEFAULT_HOLD_MUSIC_URL)

        # Lazy initialization of client
        self._client: Client | None = None

    @property
    def client(self) -> Client:
        """Get or create the Twilio client.

        Returns:
            Twilio REST client instance.

        Raises:
            ValueError: If credentials are not configured.
        """
        if self._client is None:
            if not self.account_sid or not self.auth_token:
                raise ValueError(
                    "Twilio credentials not configured. "
                    "Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN environment variables."
                )
            self._client = Client(self.account_sid, self.auth_token)
        return self._client

    async def answer_call(self, call_id: str) -> None:
        """Answer an incoming call by generating TwiML response.

        For Twilio, answering is handled via webhook response, not API call.
        This method is used to update the call state and can modify the call
        if needed.

        Args:
            call_id: The Twilio Call SID.
        """
        # For Twilio, the initial answer is handled by the webhook returning TwiML.
        # This method can be used for call state management or modifications.
        # In most cases, the answer is implicit when the webhook returns a VoiceResponse.
        pass

    async def hangup_call(self, call_id: str) -> None:
        """Terminate an active call.

        Args:
            call_id: The Twilio Call SID to hang up.

        Raises:
            TwilioException: If the call cannot be terminated.
        """
        self.client.calls(call_id).update(status="completed")

    async def transfer_call(
        self,
        call_id: str,
        target_number: str | None = None,
        timeout: int | None = None,
        status_callback_url: str | None = None,
        hold_music_url: str | None = None,
    ) -> bool:
        """Transfer an active call to another phone number.

        Updates the call's TwiML to dial the target number. Plays hold music
        while connecting and supports status callbacks for transfer events.

        Args:
            call_id: The Twilio Call SID to transfer.
            target_number: The destination phone number (E.164 format).
                          Defaults to TRANSFER_NUMBER environment variable.
            timeout: Ring timeout in seconds. Defaults to TRANSFER_TIMEOUT env var or 30.
            status_callback_url: URL to receive transfer status callbacks.
            hold_music_url: URL for hold music while connecting.
                           Defaults to HOLD_MUSIC_URL env var or default music.

        Returns:
            True if the transfer was initiated successfully.

        Raises:
            ValueError: If no target number is provided and TRANSFER_NUMBER is not set.
            TwilioException: If the transfer fails.
        """
        # Use default target number if not provided
        effective_target = target_number or self.transfer_number
        if not effective_target:
            logger.error(
                "Transfer failed: no target number provided",
                extra={"call_id": call_id},
            )
            raise ValueError(
                "No transfer target number provided. "
                "Pass target_number or set TRANSFER_NUMBER environment variable."
            )

        effective_timeout = timeout or self.transfer_timeout
        effective_hold_music = hold_music_url or self.hold_music_url

        logger.info(
            "Initiating call transfer",
            extra={
                "call_id": call_id,
                "target_number": effective_target,
                "timeout": effective_timeout,
            },
        )

        # Generate TwiML for transfer with hold music
        twiml = self.generate_transfer_twiml_with_hold(
            target_number=effective_target,
            caller_id=self.phone_number or None,
            timeout=effective_timeout,
            hold_music_url=effective_hold_music,
            status_callback_url=status_callback_url,
        )

        # Update the call with new TwiML
        self.client.calls(call_id).update(twiml=str(twiml))

        logger.info(
            "Transfer initiated successfully",
            extra={
                "call_id": call_id,
                "target_number": effective_target,
            },
        )

        return True

    async def play_audio(self, call_id: str, audio_url: str) -> None:
        """Play an audio file to the caller.

        Updates the call's TwiML to play the specified audio URL.

        Args:
            call_id: The Twilio Call SID.
            audio_url: URL of the audio file to play (must be publicly accessible).

        Raises:
            TwilioException: If the audio cannot be played.
        """
        twiml = self.generate_play_twiml(audio_url)
        self.client.calls(call_id).update(twiml=str(twiml))

    async def get_call_info(self, call_id: str) -> CallInfo:
        """Retrieve information about a call from Twilio.

        Args:
            call_id: The Twilio Call SID.

        Returns:
            CallInfo object containing details about the call.

        Raises:
            TwilioException: If call information cannot be retrieved.
        """
        call: CallInstance = self.client.calls(call_id).fetch()

        return CallInfo(
            call_id=call.sid,
            from_number=call.from_formatted or call.from_,
            to_number=call.to_formatted or call.to,
            status=self._map_twilio_status(call.status),
            started_at=call.start_time or datetime.now(),
        )

    def _map_twilio_status(self, twilio_status: str) -> CallStatus:
        """Map Twilio call status to internal CallStatus enum.

        Args:
            twilio_status: Twilio's call status string.

        Returns:
            Corresponding CallStatus enum value.
        """
        status_map = {
            "queued": CallStatus.QUEUED,
            "ringing": CallStatus.RINGING,
            "in-progress": CallStatus.IN_PROGRESS,
            "completed": CallStatus.COMPLETED,
            "busy": CallStatus.BUSY,
            "failed": CallStatus.FAILED,
            "no-answer": CallStatus.NO_ANSWER,
            "canceled": CallStatus.CANCELED,
        }
        return status_map.get(twilio_status, CallStatus.IN_PROGRESS)

    # -------------------------------------------------------------------------
    # TwiML Generation Methods
    # -------------------------------------------------------------------------

    @staticmethod
    def generate_answer_twiml(
        greeting_url: str | None = None,
        greeting_text: str | None = None,
        language: str = "en-US",
    ) -> VoiceResponse:
        """Generate TwiML for answering and greeting a caller.

        Args:
            greeting_url: URL of audio file to play as greeting.
            greeting_text: Text to speak as greeting (uses TTS if no URL).
            language: Language code for TTS (default: en-US).

        Returns:
            VoiceResponse with greeting TwiML.
        """
        response = VoiceResponse()

        if greeting_url:
            response.play(greeting_url)
        elif greeting_text:
            response.say(greeting_text, language=language)
        else:
            # Default greeting
            response.say(
                "Hello, thank you for calling. Please hold while we connect you.",
                language=language,
            )

        return response

    @staticmethod
    def generate_play_twiml(audio_url: str, loop: int = 1) -> VoiceResponse:
        """Generate TwiML to play an audio file.

        Args:
            audio_url: URL of the audio file to play.
            loop: Number of times to loop the audio (default: 1).

        Returns:
            VoiceResponse with Play TwiML.
        """
        response = VoiceResponse()
        response.play(audio_url, loop=loop)
        return response

    @staticmethod
    def generate_transfer_twiml(
        target_number: str,
        caller_id: str | None = None,
        timeout: int = 30,
        record: bool = False,
    ) -> VoiceResponse:
        """Generate TwiML to transfer/dial to another number.

        Args:
            target_number: Phone number to dial (E.164 format).
            caller_id: Caller ID to display (must be verified Twilio number).
            timeout: Ring timeout in seconds (default: 30).
            record: Whether to record the call (default: False).

        Returns:
            VoiceResponse with Dial TwiML.
        """
        response = VoiceResponse()

        dial_kwargs = {
            "timeout": timeout,
        }

        if caller_id:
            dial_kwargs["caller_id"] = caller_id

        if record:
            dial_kwargs["record"] = "record-from-answer-dual"

        response.dial(target_number, **dial_kwargs)

        return response

    @staticmethod
    def generate_transfer_twiml_with_hold(
        target_number: str,
        caller_id: str | None = None,
        timeout: int = 30,
        hold_music_url: str | None = None,
        status_callback_url: str | None = None,
        record: bool = False,
        announce_transfer: bool = True,
        language: str = "en-US",
    ) -> VoiceResponse:
        """Generate TwiML to transfer/dial with hold music while connecting.

        The TwiML will:
        1. Optionally announce the transfer to the caller
        2. Play hold music while the transfer is connecting
        3. Dial the target number with optional status callbacks

        Args:
            target_number: Phone number to dial (E.164 format).
            caller_id: Caller ID to display (must be verified Twilio number).
            timeout: Ring timeout in seconds (default: 30).
            hold_music_url: URL for hold music played while connecting.
                           If None, uses Twilio's default ring tone.
            status_callback_url: URL to receive dial status events
                                (initiated, ringing, answered, completed).
            record: Whether to record the call (default: False).
            announce_transfer: Whether to announce "Please hold" (default: True).
            language: Language for announcement (default: en-US).

        Returns:
            VoiceResponse with Dial TwiML including hold music.
        """
        response = VoiceResponse()

        # Announce transfer to caller
        if announce_transfer:
            if language.startswith("es"):
                response.say(
                    "Por favor espere mientras lo transferimos.",
                    language="es-MX",
                )
            else:
                response.say(
                    "Please hold while we transfer your call.",
                    language="en-US",
                )

        # Build dial kwargs
        dial_kwargs: dict[str, str | int | bool] = {
            "timeout": timeout,
        }

        if caller_id:
            dial_kwargs["caller_id"] = caller_id

        if record:
            dial_kwargs["record"] = "record-from-answer-dual"

        if status_callback_url:
            dial_kwargs["action"] = status_callback_url
            dial_kwargs["method"] = "POST"

        # Add ring tone / hold music using ringTone attribute
        # The ringTone plays to the caller while waiting for the transfer target to answer
        # Options: at, au, bg, br, be, ch, cl, cn, cz, de, dk, ee, es, fi, fr, gr, hu, il, in, it, lt, jp, mx, my, nl, no, nz, ph, pl, pt, ru, se, sg, th, uk, us, us-old, tw, ve, za
        dial_kwargs["ring_tone"] = "us"

        dial = response.dial(**dial_kwargs)

        # Use <Number> verb to allow playing hold music to caller
        # The hold_music_url is played to the caller while ringing
        number_kwargs: dict[str, str] = {}
        if hold_music_url:
            number_kwargs["url"] = hold_music_url
            number_kwargs["method"] = "GET"

        if status_callback_url:
            number_kwargs["status_callback"] = status_callback_url
            number_kwargs["status_callback_event"] = "initiated ringing answered completed"
            number_kwargs["status_callback_method"] = "POST"

        if number_kwargs:
            dial.number(target_number, **number_kwargs)
        else:
            dial.number(target_number)

        return response

    @staticmethod
    def generate_record_twiml(
        action_url: str,
        max_length: int = 300,
        transcribe: bool = False,
        play_beep: bool = True,
    ) -> VoiceResponse:
        """Generate TwiML to record the caller.

        Args:
            action_url: Webhook URL to receive recording details.
            max_length: Maximum recording length in seconds (default: 300).
            transcribe: Whether to transcribe the recording (default: False).
            play_beep: Whether to play beep before recording (default: True).

        Returns:
            VoiceResponse with Record TwiML.
        """
        response = VoiceResponse()
        response.record(
            action=action_url,
            max_length=max_length,
            transcribe=transcribe,
            play_beep=play_beep,
        )
        return response

    @staticmethod
    def generate_hangup_twiml() -> VoiceResponse:
        """Generate TwiML to hang up the call.

        Returns:
            VoiceResponse with Hangup TwiML.
        """
        response = VoiceResponse()
        response.hangup()
        return response

    @staticmethod
    def generate_bilingual_greeting_twiml(
        english_text: str,
        spanish_text: str,
        gather_action_url: str,
        timeout: int = 10,
        speech_timeout: str = "auto",
    ) -> VoiceResponse:
        """Generate TwiML for bilingual greeting with language selection.

        Plays greeting in both languages and gathers DTMF or speech input.

        Args:
            english_text: Greeting text in English.
            spanish_text: Greeting text in Spanish.
            gather_action_url: URL to receive DTMF or speech input.
            timeout: Seconds to wait for input (default: 10).
            speech_timeout: Speech timeout setting (default: "auto").

        Returns:
            VoiceResponse with bilingual greeting and Gather TwiML.
        """
        response = VoiceResponse()

        gather = response.gather(
            num_digits=1,
            action=gather_action_url,
            method="POST",
            timeout=timeout,
            input="dtmf speech",
            hints="English, inglés, Spanish, español, one, two, uno, dos",
            speech_timeout=speech_timeout,
            language="en-US",
        )

        # English greeting first
        gather.say(english_text, language="en-US")

        # Then Spanish
        gather.say(spanish_text, language="es-MX")

        # Default to English if no input (redirect triggers timeout handling)
        response.redirect(f"{gather_action_url}?timeout=true")

        return response
