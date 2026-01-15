"""Orchestrator core - manages the STT -> LLM -> TTS conversation loop.

This module provides the main Orchestrator class that connects speech-to-text,
LLM processing, and text-to-speech components into a coherent conversation flow.
It handles state transitions, tool execution, error recovery, and session management.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine
from uuid import uuid4

from vozbot.agent.orchestrator.llm_base import (
    FinishReason,
    LLMError,
    LLMProvider,
    LLMResponse,
    Message,
    MessageRole,
    Tool,
    ToolCall,
)
from vozbot.agent.prompts.templates import get_system_prompt
from vozbot.agent.state_machine.states import CallState, StateMachine
from vozbot.agent.tools.handlers import HandlerResult, HandlerStatus, ToolHandler
from vozbot.agent.tools.schemas import get_all_tool_schemas
from vozbot.speech.stt.base import STTProvider, TranscriptResult
from vozbot.speech.tts.base import AudioFormat, AudioResult, Language, TTSProvider


logger = logging.getLogger(__name__)


class OrchestratorState(str, Enum):
    """High-level orchestrator state."""

    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"
    ENDED = "ended"


@dataclass
class LatencyMetrics:
    """Tracks latency for various operations.

    Attributes:
        stt_latency_ms: Time for speech-to-text transcription.
        llm_latency_ms: Time for LLM response generation.
        tts_latency_ms: Time for text-to-speech synthesis.
        tool_latency_ms: Time for tool execution.
        total_turn_latency_ms: Total time for a full conversation turn.
    """

    stt_latency_ms: float = 0.0
    llm_latency_ms: float = 0.0
    tts_latency_ms: float = 0.0
    tool_latency_ms: float = 0.0
    total_turn_latency_ms: float = 0.0

    def reset(self) -> None:
        """Reset all latency metrics."""
        self.stt_latency_ms = 0.0
        self.llm_latency_ms = 0.0
        self.tts_latency_ms = 0.0
        self.tool_latency_ms = 0.0
        self.total_turn_latency_ms = 0.0


@dataclass
class SessionConfig:
    """Configuration for an orchestrator session.

    Attributes:
        max_duration_seconds: Maximum session duration (default 5 minutes).
        target_latency_ms: Target latency for response (default 2000ms).
        max_retry_attempts: Maximum retries for transient failures.
        retry_delay_seconds: Delay between retry attempts.
        default_voice_en: Default English voice ID for TTS.
        default_voice_es: Default Spanish voice ID for TTS.
        audio_format: Audio format for TTS output.
        business_name: Name of the business for greetings.
    """

    max_duration_seconds: float = 300.0  # 5 minutes
    target_latency_ms: float = 2000.0
    max_retry_attempts: int = 3
    retry_delay_seconds: float = 0.5
    default_voice_en: str = "aura-2-thalia-en"
    default_voice_es: str = "aura-2-estrella-es"
    audio_format: AudioFormat = AudioFormat.MP3
    business_name: str = "our office"


@dataclass
class ConversationTurn:
    """Represents a single conversation turn.

    Attributes:
        user_text: Transcribed user speech.
        assistant_text: LLM response text.
        tool_calls: Any tool calls made during the turn.
        tool_results: Results from executed tool calls.
        timestamp: When the turn occurred.
        latency: Latency metrics for this turn.
    """

    user_text: str = ""
    assistant_text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[HandlerResult] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    latency: LatencyMetrics = field(default_factory=LatencyMetrics)


# Type alias for audio callback
AudioCallback = Callable[[bytes], Coroutine[Any, Any, None]]


class OrchestratorError(Exception):
    """Base exception for orchestrator errors."""

    pass


class SessionTimeoutError(OrchestratorError):
    """Raised when session exceeds maximum duration."""

    pass


class STTFailureError(OrchestratorError):
    """Raised when STT fails after retries."""

    pass


class LLMFailureError(OrchestratorError):
    """Raised when LLM fails after retries."""

    pass


class TTSFailureError(OrchestratorError):
    """Raised when TTS fails after retries."""

    pass


class Orchestrator:
    """Main orchestrator for VozBot conversation loop.

    Connects STT, LLM, and TTS providers to handle a complete conversation.
    Manages state transitions, tool execution, error recovery, and session timing.

    Attributes:
        session_id: Unique identifier for this session.
        state: Current orchestrator state.
        call_state: Current call flow state from state machine.
        language: Current language for the session.
        config: Session configuration.
        metrics: Current turn latency metrics.

    Example:
        ```python
        orchestrator = Orchestrator(
            stt_provider=DeepgramSTT(),
            llm_provider=OpenAIProvider(),
            tts_provider=DeepgramTTS(),
        )

        await orchestrator.start_session(call_id="call-123")

        async def handle_audio(audio: bytes):
            # Send audio to telephony
            pass

        response_audio = await orchestrator.process_audio(
            audio_bytes=incoming_audio,
            audio_callback=handle_audio,
        )
        ```
    """

    def __init__(
        self,
        stt_provider: STTProvider,
        llm_provider: LLMProvider,
        tts_provider: TTSProvider,
        tool_handler: ToolHandler | None = None,
        config: SessionConfig | None = None,
    ) -> None:
        """Initialize the orchestrator.

        Args:
            stt_provider: Speech-to-text provider instance.
            llm_provider: LLM provider instance.
            tts_provider: Text-to-speech provider instance.
            tool_handler: Optional tool handler for executing tool calls.
            config: Session configuration. Defaults to SessionConfig().
        """
        self._stt = stt_provider
        self._llm = llm_provider
        self._tts = tts_provider
        self._tool_handler = tool_handler
        self._config = config or SessionConfig()

        # Session state
        self._session_id: str = ""
        self._call_id: str = ""
        self._state: OrchestratorState = OrchestratorState.IDLE
        self._state_machine: StateMachine | None = None
        self._session_start_time: float = 0.0

        # Conversation history
        self._messages: list[Message] = []
        self._turns: list[ConversationTurn] = []
        self._metrics = LatencyMetrics()

        # Tools
        self._tools = self._build_tools()

    @property
    def session_id(self) -> str:
        """Get the current session ID."""
        return self._session_id

    @property
    def state(self) -> OrchestratorState:
        """Get the current orchestrator state."""
        return self._state

    @property
    def call_state(self) -> CallState | None:
        """Get the current call flow state."""
        return self._state_machine.current_state if self._state_machine else None

    @property
    def language(self) -> str:
        """Get the current session language."""
        return self._state_machine.language if self._state_machine else "en"

    @property
    def config(self) -> SessionConfig:
        """Get the session configuration."""
        return self._config

    @property
    def metrics(self) -> LatencyMetrics:
        """Get the current turn latency metrics."""
        return self._metrics

    @property
    def conversation_history(self) -> list[Message]:
        """Get the full conversation history."""
        return self._messages.copy()

    @property
    def turns(self) -> list[ConversationTurn]:
        """Get all conversation turns."""
        return self._turns.copy()

    def _build_tools(self) -> list[Tool]:
        """Build Tool objects from schemas."""
        tools = []
        for schema in get_all_tool_schemas():
            tools.append(
                Tool(
                    name=schema["function"]["name"],
                    description=schema["function"]["description"],
                    parameters=schema["function"]["parameters"],
                )
            )
        return tools

    async def start_session(
        self,
        call_id: str,
        from_number: str = "",
        initial_language: str = "en",
    ) -> None:
        """Start a new conversation session.

        Initializes the session state, state machine, and conversation history.
        Sets up the system prompt for the LLM.

        Args:
            call_id: Unique identifier for the call.
            from_number: Caller's phone number (optional).
            initial_language: Initial language (en or es). Defaults to "en".

        Raises:
            OrchestratorError: If a session is already active.
        """
        if self._state != OrchestratorState.IDLE:
            raise OrchestratorError("Session already active")

        self._session_id = str(uuid4())
        self._call_id = call_id
        self._session_start_time = time.time()
        self._state = OrchestratorState.LISTENING

        # Initialize state machine
        self._state_machine = StateMachine(call_id=call_id)
        self._state_machine.language = initial_language

        # Store caller info in context
        if from_number:
            self._state_machine.context["from_number"] = from_number

        # Initialize conversation with system prompt
        system_prompt = get_system_prompt(
            language=initial_language,
            call_id=call_id,
            current_state=self._state_machine.current_state.value,
            additional_context=f"Caller phone: {from_number}" if from_number else "",
        )
        self._messages = [Message(role=MessageRole.SYSTEM, content=system_prompt)]
        self._turns = []

        logger.info(
            f"Started session {self._session_id} for call {call_id}, "
            f"language={initial_language}"
        )

    async def end_session(self) -> dict[str, Any]:
        """End the current session.

        Cleans up resources and returns session summary.

        Returns:
            Dict containing session summary with call_id, duration,
            turns count, and final state.
        """
        if self._state == OrchestratorState.IDLE:
            return {"status": "no_active_session"}

        duration = time.time() - self._session_start_time
        summary = {
            "session_id": self._session_id,
            "call_id": self._call_id,
            "duration_seconds": duration,
            "turns_count": len(self._turns),
            "final_state": self._state_machine.current_state.value if self._state_machine else None,
            "language": self.language,
        }

        # Transition to END if not already there
        if self._state_machine and not self._state_machine.is_terminal():
            if self._state_machine.can_transition_to(CallState.END):
                self._state_machine.transition_to(CallState.END)

        self._state = OrchestratorState.ENDED
        logger.info(f"Ended session {self._session_id}: duration={duration:.1f}s, turns={len(self._turns)}")

        return summary

    def _check_session_timeout(self) -> bool:
        """Check if session has exceeded maximum duration.

        Returns:
            True if session has timed out, False otherwise.
        """
        if self._session_start_time == 0:
            return False
        elapsed = time.time() - self._session_start_time
        return elapsed > self._config.max_duration_seconds

    async def process_audio(
        self,
        audio_bytes: bytes,
        audio_callback: AudioCallback | None = None,
    ) -> AudioResult | None:
        """Process incoming audio through the full STT -> LLM -> TTS pipeline.

        This is the main entry point for handling a conversation turn.
        Takes audio input, transcribes it, generates a response, and
        synthesizes speech output.

        Args:
            audio_bytes: Raw audio data from the caller.
            audio_callback: Optional async callback to receive audio chunks
                for streaming output.

        Returns:
            AudioResult containing the synthesized speech response,
            or None if the session has ended.

        Raises:
            SessionTimeoutError: If session exceeds maximum duration.
            STTFailureError: If speech-to-text fails after retries.
            LLMFailureError: If LLM fails after retries.
            TTSFailureError: If text-to-speech fails after retries.
        """
        # Check session timeout
        if self._check_session_timeout():
            logger.warning(f"Session {self._session_id} timed out")
            await self._handle_timeout()
            raise SessionTimeoutError("Session exceeded maximum duration")

        if self._state == OrchestratorState.ENDED:
            return None

        turn_start = time.time()
        self._metrics.reset()
        current_turn = ConversationTurn()

        try:
            # Step 1: STT - Transcribe audio
            self._state = OrchestratorState.LISTENING
            transcript = await self._transcribe_with_retry(audio_bytes)
            current_turn.user_text = transcript.text
            logger.debug(f"Transcribed: '{transcript.text}' (confidence={transcript.confidence:.2f})")

            # Add user message to history
            self._messages.append(
                Message(role=MessageRole.USER, content=transcript.text)
            )

            # Step 2: LLM - Generate response
            self._state = OrchestratorState.PROCESSING
            response = await self._generate_response_with_retry()

            # Step 3: Handle tool calls if present
            if response.has_tool_calls:
                response = await self._handle_tool_calls(response, current_turn)

            # Extract assistant text
            assistant_text = response.content or ""
            current_turn.assistant_text = assistant_text

            # Add assistant message to history
            self._messages.append(
                Message(
                    role=MessageRole.ASSISTANT,
                    content=assistant_text,
                    tool_calls=response.tool_calls if response.has_tool_calls else None,
                )
            )

            # Step 4: Update state machine based on response
            self._update_state_machine(response)

            # Step 5: TTS - Synthesize response
            if assistant_text and self._state != OrchestratorState.ENDED:
                self._state = OrchestratorState.SPEAKING
                audio_result = await self._synthesize_with_retry(assistant_text)

                # Call audio callback if provided
                if audio_callback:
                    await audio_callback(audio_result.audio_bytes)

                # Record turn
                current_turn.latency = LatencyMetrics(
                    stt_latency_ms=self._metrics.stt_latency_ms,
                    llm_latency_ms=self._metrics.llm_latency_ms,
                    tts_latency_ms=self._metrics.tts_latency_ms,
                    tool_latency_ms=self._metrics.tool_latency_ms,
                    total_turn_latency_ms=(time.time() - turn_start) * 1000,
                )
                self._turns.append(current_turn)
                self._metrics.total_turn_latency_ms = current_turn.latency.total_turn_latency_ms

                # Check if we're at end state
                if self._state_machine and self._state_machine.is_terminal():
                    self._state = OrchestratorState.ENDED

                return audio_result
            else:
                # No speech needed (e.g., session ended)
                current_turn.latency.total_turn_latency_ms = (time.time() - turn_start) * 1000
                self._turns.append(current_turn)
                return None

        except (STTFailureError, LLMFailureError, TTSFailureError):
            # Re-raise specific failures
            raise
        except Exception as e:
            logger.exception(f"Unexpected error in process_audio: {e}")
            self._state = OrchestratorState.ERROR
            raise OrchestratorError(f"Unexpected error: {e}") from e

    async def _transcribe_with_retry(self, audio_bytes: bytes) -> TranscriptResult:
        """Transcribe audio with retry on failure.

        Args:
            audio_bytes: Raw audio data.

        Returns:
            TranscriptResult with transcribed text.

        Raises:
            STTFailureError: If all retry attempts fail.
        """
        last_error: Exception | None = None
        start_time = time.time()

        for attempt in range(self._config.max_retry_attempts):
            try:
                result = await self._stt.transcribe(audio_bytes, language=self.language)
                self._metrics.stt_latency_ms = (time.time() - start_time) * 1000
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"STT attempt {attempt + 1} failed: {e}")
                if attempt < self._config.max_retry_attempts - 1:
                    await asyncio.sleep(self._config.retry_delay_seconds)

        logger.error(f"STT failed after {self._config.max_retry_attempts} attempts")
        raise STTFailureError(f"STT failed: {last_error}")

    async def _generate_response_with_retry(self) -> LLMResponse:
        """Generate LLM response with retry on failure.

        Returns:
            LLMResponse from the LLM provider.

        Raises:
            LLMFailureError: If all retry attempts fail.
        """
        last_error: Exception | None = None
        start_time = time.time()

        for attempt in range(self._config.max_retry_attempts):
            try:
                # Update system prompt with current state
                self._update_system_prompt()

                response = await self._llm.complete(
                    messages=self._messages,
                    tools=self._tools if self._tool_handler else None,
                )
                self._metrics.llm_latency_ms = (time.time() - start_time) * 1000
                return response
            except LLMError as e:
                last_error = e
                logger.warning(f"LLM attempt {attempt + 1} failed: {e}")
                if attempt < self._config.max_retry_attempts - 1:
                    await asyncio.sleep(self._config.retry_delay_seconds)

        logger.error(f"LLM failed after {self._config.max_retry_attempts} attempts")
        raise LLMFailureError(f"LLM failed: {last_error}")

    async def _synthesize_with_retry(self, text: str) -> AudioResult:
        """Synthesize speech with retry on failure.

        Args:
            text: Text to synthesize.

        Returns:
            AudioResult with synthesized audio.

        Raises:
            TTSFailureError: If all retry attempts fail.
        """
        last_error: Exception | None = None
        start_time = time.time()

        # Select voice based on language
        voice = (
            self._config.default_voice_es
            if self.language == "es"
            else self._config.default_voice_en
        )
        tts_language = Language.SPANISH if self.language == "es" else Language.ENGLISH

        for attempt in range(self._config.max_retry_attempts):
            try:
                result = await self._tts.synthesize(
                    text=text,
                    language=tts_language,
                    voice=voice,
                    audio_format=self._config.audio_format,
                )
                self._metrics.tts_latency_ms = (time.time() - start_time) * 1000
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"TTS attempt {attempt + 1} failed: {e}")
                if attempt < self._config.max_retry_attempts - 1:
                    await asyncio.sleep(self._config.retry_delay_seconds)

        logger.error(f"TTS failed after {self._config.max_retry_attempts} attempts")
        raise TTSFailureError(f"TTS failed: {last_error}")

    async def _handle_tool_calls(
        self,
        response: LLMResponse,
        turn: ConversationTurn,
    ) -> LLMResponse:
        """Execute tool calls and get follow-up response.

        Args:
            response: LLM response containing tool calls.
            turn: Current conversation turn to record results.

        Returns:
            Updated LLMResponse after tool execution.
        """
        if not self._tool_handler:
            logger.warning("Tool calls received but no tool handler configured")
            return response

        start_time = time.time()
        turn.tool_calls = response.tool_calls

        # Execute each tool call
        for tool_call in response.tool_calls:
            logger.info(f"Executing tool: {tool_call.name}")
            result = await self._tool_handler.execute(
                tool_name=tool_call.name,
                arguments=tool_call.arguments,
            )
            turn.tool_results.append(result)

            # Add tool result to conversation
            self._messages.append(
                Message(
                    role=MessageRole.TOOL,
                    content=result.to_llm_response(),
                    tool_call_id=tool_call.id,
                    name=tool_call.name,
                )
            )

        self._metrics.tool_latency_ms = (time.time() - start_time) * 1000

        # Get follow-up response after tool execution
        try:
            follow_up = await self._llm.complete(
                messages=self._messages,
                tools=self._tools,
            )
            return follow_up
        except LLMError as e:
            logger.error(f"Failed to get follow-up response after tool calls: {e}")
            # Return a synthesized error response
            return LLMResponse(
                content=self._get_error_message(),
                finish_reason=FinishReason.ERROR,
            )

    def _update_system_prompt(self) -> None:
        """Update the system prompt with current state."""
        if not self._state_machine or not self._messages:
            return

        # Build additional context
        context_parts = []
        if "from_number" in self._state_machine.context:
            context_parts.append(f"Caller phone: {self._state_machine.context['from_number']}")
        if "customer_name" in self._state_machine.context:
            context_parts.append(f"Customer name: {self._state_machine.context['customer_name']}")
        if "intent" in self._state_machine.context:
            context_parts.append(f"Intent: {self._state_machine.context['intent']}")

        new_system_prompt = get_system_prompt(
            language=self.language,
            call_id=self._call_id,
            current_state=self._state_machine.current_state.value,
            additional_context="\n".join(context_parts),
        )

        # Update first message if it's the system prompt
        if self._messages and self._messages[0].role == MessageRole.SYSTEM:
            self._messages[0] = Message(role=MessageRole.SYSTEM, content=new_system_prompt)

    def _update_state_machine(self, response: LLMResponse) -> None:
        """Update state machine based on LLM response and tool results.

        Analyzes the response content and tool calls to determine
        appropriate state transitions.

        Args:
            response: The LLM response to analyze.
        """
        if not self._state_machine:
            return

        # Check for specific tool calls that trigger state changes
        if response.has_tool_calls:
            for tool_call in response.tool_calls:
                if tool_call.name == "create_callback_task":
                    self._try_transition(CallState.CREATE_CALLBACK_TASK)
                elif tool_call.name == "transfer_call":
                    self._try_transition(CallState.TRANSFER_OR_WRAPUP)
                elif tool_call.name == "update_call_record":
                    # Extract language/customer type updates
                    args = tool_call.arguments
                    if "language" in args:
                        self._state_machine.language = args["language"]
                    if "customer_type" in args:
                        self._state_machine.context["customer_type"] = args["customer_type"]
                    if "intent" in args:
                        self._state_machine.context["intent"] = args["intent"]

        # Auto-progress through initial states
        current = self._state_machine.current_state
        if current == CallState.INIT:
            self._try_transition(CallState.GREET)
        elif current == CallState.GREET:
            self._try_transition(CallState.LANGUAGE_SELECT)

        # Check for end conditions in response content
        content_lower = (response.content or "").lower()
        if any(phrase in content_lower for phrase in ["goodbye", "have a great day", "que tenga"]):
            if self._state_machine.can_transition_to(CallState.END):
                self._try_transition(CallState.END)

    def _try_transition(self, target_state: CallState) -> bool:
        """Attempt a state transition if valid.

        Args:
            target_state: The state to transition to.

        Returns:
            True if transition succeeded, False otherwise.
        """
        if not self._state_machine:
            return False

        if self._state_machine.can_transition_to(target_state):
            self._state_machine.transition_to(target_state)
            logger.debug(f"Transitioned to state: {target_state.value}")
            return True
        return False

    def _get_error_message(self) -> str:
        """Get an error message in the current language.

        Returns:
            Localized error message string.
        """
        if self.language == "es":
            return (
                "Disculpe, encontre un problema tecnico. "
                "Permitame intentar de nuevo o transferirle a alguien que pueda ayudarle."
            )
        return (
            "I apologize, I encountered a technical issue. "
            "Let me try again or transfer you to someone who can help."
        )

    async def _handle_timeout(self) -> None:
        """Handle session timeout.

        Transitions to error/end state and logs the timeout.
        """
        if self._state_machine:
            if self._state_machine.can_transition_to(CallState.TIMEOUT):
                self._state_machine.transition_to(CallState.TIMEOUT)
            elif self._state_machine.can_transition_to(CallState.END):
                self._state_machine.transition_to(CallState.END)

        self._state = OrchestratorState.ENDED
        logger.warning(f"Session {self._session_id} timed out after {self._config.max_duration_seconds}s")

    async def generate_greeting(self) -> AudioResult:
        """Generate an initial greeting for the call.

        Creates the greeting audio to play when a call is first answered.

        Returns:
            AudioResult with the greeting audio.

        Raises:
            OrchestratorError: If session not started or TTS fails.
        """
        if not self._state_machine:
            raise OrchestratorError("Session not started")

        # Transition to greet state
        self._try_transition(CallState.GREET)

        # Get greeting text
        greeting = self._state_machine.get_current_prompt()
        if not greeting:
            # Fallback greeting
            if self.language == "es":
                greeting = (
                    f"Hola! Gracias por llamar a {self._config.business_name}. "
                    "Soy un asistente de inteligencia artificial. Como puedo ayudarle?"
                )
            else:
                greeting = (
                    f"Hello! Thank you for calling {self._config.business_name}. "
                    "I'm an AI assistant. How may I help you?"
                )

        # Add greeting to conversation history
        self._messages.append(
            Message(role=MessageRole.ASSISTANT, content=greeting)
        )

        # Synthesize greeting
        try:
            return await self._synthesize_with_retry(greeting)
        except TTSFailureError:
            raise OrchestratorError("Failed to generate greeting audio")

    def set_language(self, language: str) -> None:
        """Set the session language.

        Args:
            language: Language code ("en" or "es").

        Raises:
            ValueError: If language is not "en" or "es".
        """
        if language not in ("en", "es"):
            raise ValueError(f"Unsupported language: {language}")

        if self._state_machine:
            self._state_machine.language = language
        logger.info(f"Session language set to: {language}")

    def get_transcript(self) -> str:
        """Get the full conversation transcript.

        Returns:
            Formatted transcript string with speaker labels.
        """
        lines = []
        for turn in self._turns:
            if turn.user_text:
                lines.append(f"User: {turn.user_text}")
            if turn.assistant_text:
                lines.append(f"Assistant: {turn.assistant_text}")
        return "\n".join(lines)

    def get_session_stats(self) -> dict[str, Any]:
        """Get session statistics.

        Returns:
            Dict with session statistics including timing and usage data.
        """
        if not self._session_start_time:
            return {}

        duration = time.time() - self._session_start_time
        avg_latency = 0.0
        if self._turns:
            avg_latency = sum(t.latency.total_turn_latency_ms for t in self._turns) / len(self._turns)

        return {
            "session_id": self._session_id,
            "call_id": self._call_id,
            "duration_seconds": duration,
            "turns_count": len(self._turns),
            "average_turn_latency_ms": avg_latency,
            "current_state": self._state.value,
            "call_state": self.call_state.value if self.call_state else None,
            "language": self.language,
            "llm_tokens_used": getattr(self._llm, "total_tokens_used", 0),
        }
