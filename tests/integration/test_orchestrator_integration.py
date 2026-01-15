"""Integration tests for orchestrator with callback task creation.

Tests a complete conversation flow that:
1. Starts a session
2. Processes multiple audio turns
3. Collects caller information
4. Creates a callback task
5. Ends the session
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from vozbot.agent.orchestrator.core import (
    Orchestrator,
    OrchestratorState,
    SessionConfig,
)
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
from vozbot.agent.state_machine.states import CallState
from vozbot.agent.tools.handlers import HandlerResult, HandlerStatus, ToolHandler
from vozbot.speech.stt.base import STTProvider, TranscriptResult
from vozbot.speech.tts.base import AudioFormat, AudioResult, Language, TTSProvider


class ConversationSimulator:
    """Simulates a multi-turn conversation for testing.

    Provides scripted responses for STT and LLM to test a complete
    conversation flow including callback task creation.
    """

    def __init__(self) -> None:
        self.stt_index = 0  # Separate index for STT
        self.llm_index = 0  # Separate index for LLM
        self.call_id = str(uuid4())

        # Script of user utterances (what STT returns)
        self.user_utterances = [
            "Hello, I need to schedule an appointment",
            "Yes, I'm a new customer",
            "My name is Maria Garcia",
            "My number is 555-123-4567",
            "Mornings work best for me",
            "Yes, that's correct",
        ]

        # Script of LLM responses - note: after tool call, there's a follow-up response
        # LLM is called twice for turn 5 (tool call + follow-up)
        self.llm_responses = [
            # Turn 1 response
            LLMResponse(
                content="Hello! Thank you for calling. I'd be happy to help you schedule an appointment. Are you an existing customer or is this your first time with us?",
                finish_reason=FinishReason.STOP,
            ),
            # Turn 2 response
            LLMResponse(
                content="Welcome! May I have your name please?",
                finish_reason=FinishReason.STOP,
            ),
            # Turn 3 response
            LLMResponse(
                content="Nice to meet you, Maria. What's the best phone number to reach you for a callback?",
                finish_reason=FinishReason.STOP,
            ),
            # Turn 4 response
            LLMResponse(
                content="Got it, 555-123-4567. And what's the best time for someone to call you back?",
                finish_reason=FinishReason.STOP,
            ),
            # Turn 5 response (tool call)
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCall(
                        id=f"call_{uuid4().hex[:8]}",
                        name="create_callback_task",
                        arguments={
                            "call_id": "",  # Will be filled in
                            "priority": "normal",
                            "name": "Maria Garcia",
                            "callback_number": "+15551234567",
                            "best_time_window": "morning",
                            "notes": "New customer wants to schedule an appointment",
                        },
                    )
                ],
                finish_reason=FinishReason.TOOL_CALLS,
            ),
            # Turn 5 follow-up response (after tool execution)
            LLMResponse(
                content="I've created a callback request. Someone from our office will call you back in the morning. Thank you for calling, Maria. Have a great day!",
                finish_reason=FinishReason.STOP,
            ),
            # Turn 6 response
            LLMResponse(
                content="You're welcome! Goodbye!",
                finish_reason=FinishReason.STOP,
            ),
        ]

    def get_next_utterance(self) -> str:
        """Get the next user utterance and advance STT index."""
        if self.stt_index < len(self.user_utterances):
            utterance = self.user_utterances[self.stt_index]
            self.stt_index += 1
            return utterance
        return "goodbye"

    def get_next_response(self, call_id: str) -> LLMResponse:
        """Get the next LLM response and advance LLM index."""
        if self.llm_index < len(self.llm_responses):
            response = self.llm_responses[self.llm_index]
            self.llm_index += 1
            # Fill in call_id for tool calls
            if response.has_tool_calls:
                for tc in response.tool_calls:
                    if "call_id" in tc.arguments:
                        tc.arguments["call_id"] = call_id
            return response
        return LLMResponse(
            content="Goodbye! Thank you for calling.",
            finish_reason=FinishReason.STOP,
        )


class SimulatedSTT(STTProvider):
    """STT provider that returns scripted utterances."""

    def __init__(self, simulator: ConversationSimulator) -> None:
        self.simulator = simulator

    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str = "en",
    ) -> TranscriptResult:
        return TranscriptResult(
            text=self.simulator.get_next_utterance(),
            confidence=0.95,
            language=language,
            duration=2.0,
        )

    def transcribe_stream(self, audio_stream, language: str = "en"):
        raise NotImplementedError


class SimulatedLLM(LLMProvider):
    """LLM provider that returns scripted responses."""

    def __init__(self, simulator: ConversationSimulator) -> None:
        self.simulator = simulator
        self.call_id = ""
        self.total_tokens_used = 0

    async def complete(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        **kwargs,
    ) -> LLMResponse:
        self.total_tokens_used += 100
        return self.simulator.get_next_response(self.call_id)

    async def stream_complete(self, messages, tools=None, **kwargs):
        raise NotImplementedError
        yield


class SimulatedTTS(TTSProvider):
    """TTS provider that returns mock audio."""

    def __init__(self) -> None:
        self.synthesized_texts: list[str] = []

    async def synthesize(
        self,
        text: str,
        language: Language,
        voice: str,
        audio_format: AudioFormat = AudioFormat.MP3,
    ) -> AudioResult:
        self.synthesized_texts.append(text)
        return AudioResult(
            audio_bytes=f"audio:{text[:20]}".encode(),
            format=audio_format,
            duration=len(text) * 0.05,  # Rough estimate
            sample_rate=24000,
        )

    async def get_available_voices(self, language: Language):
        return []


class SimulatedToolHandler(ToolHandler):
    """Tool handler that tracks calls without database."""

    def __init__(self) -> None:
        self.executed_tools: list[tuple[str, dict]] = []
        self._handlers = {
            "create_callback_task": self._handle_callback_task,
            "create_call_record": self._handle_call_record,
            "update_call_record": self._handle_update_record,
            "transfer_call": self._handle_transfer,
            "send_notification": self._handle_notification,
        }

    async def execute(self, tool_name: str, arguments: dict) -> HandlerResult:
        self.executed_tools.append((tool_name, arguments))
        handler = self._handlers.get(tool_name)
        if handler:
            return await handler(arguments)
        return HandlerResult(
            status=HandlerStatus.FAILURE,
            data={},
            error=f"Unknown tool: {tool_name}",
            tool_name=tool_name,
        )

    async def _handle_callback_task(self, args: dict) -> HandlerResult:
        return HandlerResult(
            status=HandlerStatus.SUCCESS,
            data={
                "task_id": str(uuid4()),
                "call_id": args.get("call_id", ""),
                "name": args.get("name", ""),
                "callback_number": args.get("callback_number", ""),
            },
            tool_name="create_callback_task",
        )

    async def _handle_call_record(self, args: dict) -> HandlerResult:
        return HandlerResult(
            status=HandlerStatus.SUCCESS,
            data={"call_id": str(uuid4())},
            tool_name="create_call_record",
        )

    async def _handle_update_record(self, args: dict) -> HandlerResult:
        return HandlerResult(
            status=HandlerStatus.SUCCESS,
            data={"call_id": args.get("call_id", "")},
            tool_name="update_call_record",
        )

    async def _handle_transfer(self, args: dict) -> HandlerResult:
        return HandlerResult(
            status=HandlerStatus.SUCCESS,
            data={"transferred_to": args.get("target_number", "")},
            tool_name="transfer_call",
        )

    async def _handle_notification(self, args: dict) -> HandlerResult:
        return HandlerResult(
            status=HandlerStatus.SUCCESS,
            data={"sent": True},
            tool_name="send_notification",
        )


class TestRecordedConversationIntegration:
    """Integration tests for complete conversation flows."""

    @pytest.mark.asyncio
    async def test_complete_callback_conversation(self) -> None:
        """Test a complete conversation that results in a callback task.

        Simulates a caller who:
        1. Wants to schedule an appointment
        2. Is a new customer
        3. Provides their name
        4. Provides their phone number
        5. Specifies preferred callback time
        6. Confirms information

        The LLM should create a callback task with all the gathered info.
        """
        # Setup
        simulator = ConversationSimulator()
        stt = SimulatedSTT(simulator)
        llm = SimulatedLLM(simulator)
        tts = SimulatedTTS()
        tool_handler = SimulatedToolHandler()

        config = SessionConfig(
            max_duration_seconds=300.0,
            max_retry_attempts=1,
        )

        orchestrator = Orchestrator(
            stt_provider=stt,
            llm_provider=llm,
            tts_provider=tts,
            tool_handler=tool_handler,
            config=config,
        )

        # Start session
        call_id = "integration-test-call"
        await orchestrator.start_session(
            call_id=call_id,
            from_number="+15559876543",
            initial_language="en",
        )
        llm.call_id = call_id

        assert orchestrator.state == OrchestratorState.LISTENING
        assert orchestrator.session_id != ""

        # Process conversation turns
        collected_audio: list[bytes] = []

        async def audio_callback(audio: bytes) -> None:
            collected_audio.append(audio)

        # Turn 1: Initial request
        result = await orchestrator.process_audio(b"audio_turn_1", audio_callback)
        assert result is not None
        assert len(collected_audio) == 1

        # Turn 2: Customer type
        result = await orchestrator.process_audio(b"audio_turn_2", audio_callback)
        assert result is not None

        # Turn 3: Name
        result = await orchestrator.process_audio(b"audio_turn_3", audio_callback)
        assert result is not None

        # Turn 4: Phone number
        result = await orchestrator.process_audio(b"audio_turn_4", audio_callback)
        assert result is not None

        # Turn 5: Preferred time (triggers callback task creation)
        result = await orchestrator.process_audio(b"audio_turn_5", audio_callback)
        assert result is not None

        # Turn 6: Confirmation
        result = await orchestrator.process_audio(b"audio_turn_6", audio_callback)
        assert result is not None

        # Verify callback task was created
        assert len(tool_handler.executed_tools) > 0

        callback_calls = [
            (name, args)
            for name, args in tool_handler.executed_tools
            if name == "create_callback_task"
        ]
        assert len(callback_calls) == 1

        tool_name, tool_args = callback_calls[0]
        assert tool_args["name"] == "Maria Garcia"
        assert "+1555" in tool_args["callback_number"]
        assert tool_args["best_time_window"] == "morning"
        assert "appointment" in tool_args["notes"].lower()

        # Verify conversation history
        assert len(orchestrator.turns) == 6
        assert orchestrator.turns[0].user_text == "Hello, I need to schedule an appointment"
        assert orchestrator.turns[2].user_text == "My name is Maria Garcia"

        # Verify transcript
        transcript = orchestrator.get_transcript()
        assert "Maria Garcia" in transcript
        assert "555-123-4567" in transcript

        # End session and check summary
        summary = await orchestrator.end_session()
        assert summary["call_id"] == call_id
        assert summary["turns_count"] == 6
        assert summary["duration_seconds"] > 0

    @pytest.mark.asyncio
    async def test_spanish_conversation(self) -> None:
        """Test conversation in Spanish."""
        stt = MagicMock(spec=STTProvider)
        stt.transcribe = AsyncMock(
            return_value=TranscriptResult(
                text="Hola, necesito una cita",
                confidence=0.9,
                language="es",
                duration=2.0,
            )
        )

        llm = MagicMock(spec=LLMProvider)
        llm.complete = AsyncMock(
            return_value=LLMResponse(
                content="Hola! Gracias por llamar. Como puedo ayudarle?",
                finish_reason=FinishReason.STOP,
            )
        )
        llm.total_tokens_used = 0

        tts = MagicMock(spec=TTSProvider)
        tts.synthesize = AsyncMock(
            return_value=AudioResult(
                audio_bytes=b"spanish_audio",
                format=AudioFormat.MP3,
                duration=2.0,
                sample_rate=24000,
            )
        )

        orchestrator = Orchestrator(stt, llm, tts)

        await orchestrator.start_session(
            call_id="spanish-call",
            initial_language="es",
        )

        assert orchestrator.language == "es"

        result = await orchestrator.process_audio(b"audio")
        assert result is not None

        # Verify TTS was called with Spanish
        tts.synthesize.assert_called()
        call_args = tts.synthesize.call_args
        assert call_args[1]["language"] == Language.SPANISH

    @pytest.mark.asyncio
    async def test_latency_under_target(self) -> None:
        """Test that latency is tracked and reasonable."""
        stt = MagicMock(spec=STTProvider)
        stt.transcribe = AsyncMock(
            return_value=TranscriptResult(
                text="Test",
                confidence=0.9,
                language="en",
                duration=1.0,
            )
        )

        llm = MagicMock(spec=LLMProvider)
        llm.complete = AsyncMock(
            return_value=LLMResponse(
                content="Response",
                finish_reason=FinishReason.STOP,
            )
        )
        llm.total_tokens_used = 0

        tts = MagicMock(spec=TTSProvider)
        tts.synthesize = AsyncMock(
            return_value=AudioResult(
                audio_bytes=b"audio",
                format=AudioFormat.MP3,
                duration=1.0,
                sample_rate=24000,
            )
        )

        config = SessionConfig(target_latency_ms=2000.0)
        orchestrator = Orchestrator(stt, llm, tts, config=config)

        await orchestrator.start_session(call_id="latency-test")
        await orchestrator.process_audio(b"audio")

        stats = orchestrator.get_session_stats()
        # With mocked providers, latency should be very low
        assert stats["average_turn_latency_ms"] < config.target_latency_ms

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_in_conversation(self) -> None:
        """Test conversation with multiple tool calls."""
        tool_handler = SimulatedToolHandler()

        # LLM responses with multiple tool calls
        responses = [
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="create_call_record",
                        arguments={
                            "from_number": "+15551234567",
                            "language": "en",
                            "customer_type": "new",
                            "intent": "Schedule appointment",
                        },
                    )
                ],
                finish_reason=FinishReason.TOOL_CALLS,
            ),
            LLMResponse(
                content="I've recorded your information. May I have your name?",
                finish_reason=FinishReason.STOP,
            ),
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="call_2",
                        name="create_callback_task",
                        arguments={
                            "call_id": "test-call",
                            "callback_number": "+15551234567",
                            "name": "John Doe",
                            "priority": "high",
                        },
                    )
                ],
                finish_reason=FinishReason.TOOL_CALLS,
            ),
            LLMResponse(
                content="I've created a callback request. Have a great day!",
                finish_reason=FinishReason.STOP,
            ),
        ]

        response_index = 0

        async def mock_complete(messages, tools=None, **kwargs):
            nonlocal response_index
            if response_index < len(responses):
                resp = responses[response_index]
                response_index += 1
                return resp
            return LLMResponse(content="Goodbye!", finish_reason=FinishReason.STOP)

        stt = MagicMock(spec=STTProvider)
        stt.transcribe = AsyncMock(
            return_value=TranscriptResult(
                text="Test input",
                confidence=0.9,
                language="en",
                duration=1.0,
            )
        )

        llm = MagicMock(spec=LLMProvider)
        llm.complete = mock_complete
        llm.total_tokens_used = 0

        tts = MagicMock(spec=TTSProvider)
        tts.synthesize = AsyncMock(
            return_value=AudioResult(
                audio_bytes=b"audio",
                format=AudioFormat.MP3,
                duration=1.0,
                sample_rate=24000,
            )
        )

        orchestrator = Orchestrator(stt, llm, tts, tool_handler=tool_handler)
        await orchestrator.start_session(call_id="multi-tool-test")

        # First turn - creates call record
        await orchestrator.process_audio(b"audio1")

        # Second turn - creates callback task
        await orchestrator.process_audio(b"audio2")

        # Verify both tools were executed
        tool_names = [name for name, _ in tool_handler.executed_tools]
        assert "create_call_record" in tool_names
        assert "create_callback_task" in tool_names


class TestConversationRecovery:
    """Tests for conversation recovery scenarios."""

    @pytest.mark.asyncio
    async def test_recovery_from_stt_failure_mid_conversation(self) -> None:
        """Test recovery when STT fails during conversation."""
        fail_on_turn = 2
        current_turn = 0

        async def mock_transcribe(audio, language="en"):
            nonlocal current_turn
            current_turn += 1
            if current_turn == fail_on_turn:
                raise Exception("Network error")
            return TranscriptResult(
                text=f"Turn {current_turn}",
                confidence=0.9,
                language=language,
                duration=1.0,
            )

        stt = MagicMock(spec=STTProvider)
        stt.transcribe = mock_transcribe

        llm = MagicMock(spec=LLMProvider)
        llm.complete = AsyncMock(
            return_value=LLMResponse(
                content="Response",
                finish_reason=FinishReason.STOP,
            )
        )
        llm.total_tokens_used = 0

        tts = MagicMock(spec=TTSProvider)
        tts.synthesize = AsyncMock(
            return_value=AudioResult(
                audio_bytes=b"audio",
                format=AudioFormat.MP3,
                duration=1.0,
                sample_rate=24000,
            )
        )

        config = SessionConfig(max_retry_attempts=3, retry_delay_seconds=0.01)
        orchestrator = Orchestrator(stt, llm, tts, config=config)

        await orchestrator.start_session(call_id="recovery-test")

        # First turn succeeds
        result1 = await orchestrator.process_audio(b"audio1")
        assert result1 is not None

        # Second turn fails but retries succeed
        result2 = await orchestrator.process_audio(b"audio2")
        assert result2 is not None

        # Both turns should be recorded
        assert len(orchestrator.turns) == 2
