"""Tests for orchestrator core.

Verifies:
- Session lifecycle (start, process, end)
- STT -> LLM -> TTS pipeline
- Tool call execution
- State transitions
- Error recovery and retries
- Session timeout handling
- Latency tracking
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vozbot.agent.orchestrator.core import (
    ConversationTurn,
    LatencyMetrics,
    LLMFailureError,
    Orchestrator,
    OrchestratorError,
    OrchestratorState,
    SessionConfig,
    SessionTimeoutError,
    STTFailureError,
    TTSFailureError,
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
from vozbot.agent.tools.handlers import HandlerResult, HandlerStatus
from vozbot.speech.stt.base import STTProvider, TranscriptResult
from vozbot.speech.tts.base import AudioFormat, AudioResult, Language, TTSProvider


class MockSTTProvider(STTProvider):
    """Mock STT provider for testing."""

    def __init__(self) -> None:
        self.transcribe_calls: list[tuple[bytes, str]] = []
        self.result = TranscriptResult(
            text="Hello, I need help",
            confidence=0.95,
            language="en",
            duration=2.5,
        )
        self.should_fail = False
        self.fail_count = 0

    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str = "en",
    ) -> TranscriptResult:
        self.transcribe_calls.append((audio_bytes, language))
        if self.should_fail:
            self.fail_count += 1
            raise Exception("STT failed")
        return self.result

    def transcribe_stream(self, audio_stream, language: str = "en"):
        """Streaming transcription - not used in tests."""
        raise NotImplementedError


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""

    def __init__(self) -> None:
        self.complete_calls: list[tuple[list[Message], list[Tool] | None]] = []
        self.response = LLMResponse(
            content="Hello! How can I help you today?",
            finish_reason=FinishReason.STOP,
        )
        self.should_fail = False
        self.fail_count = 0
        self.total_tokens_used = 0

    async def complete(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        **kwargs,
    ) -> LLMResponse:
        self.complete_calls.append((messages, tools))
        if self.should_fail:
            self.fail_count += 1
            raise LLMError("LLM failed")
        self.total_tokens_used += 100
        return self.response

    async def stream_complete(self, messages, tools=None, **kwargs):
        """Streaming completion - not used in tests."""
        raise NotImplementedError
        yield  # Make it a generator


class MockTTSProvider(TTSProvider):
    """Mock TTS provider for testing."""

    def __init__(self) -> None:
        self.synthesize_calls: list[tuple[str, Language, str]] = []
        self.result = AudioResult(
            audio_bytes=b"mock_audio_data",
            format=AudioFormat.MP3,
            duration=1.5,
            sample_rate=24000,
        )
        self.should_fail = False
        self.fail_count = 0

    async def synthesize(
        self,
        text: str,
        language: Language,
        voice: str,
        audio_format: AudioFormat = AudioFormat.MP3,
    ) -> AudioResult:
        self.synthesize_calls.append((text, language, voice))
        if self.should_fail:
            self.fail_count += 1
            raise Exception("TTS failed")
        return self.result

    async def get_available_voices(self, language: Language):
        return []


class TestOrchestratorInit:
    """Tests for Orchestrator initialization."""

    def test_init_default_config(self) -> None:
        """Test initialization with default config."""
        stt = MockSTTProvider()
        llm = MockLLMProvider()
        tts = MockTTSProvider()

        orchestrator = Orchestrator(stt, llm, tts)

        assert orchestrator.state == OrchestratorState.IDLE
        assert orchestrator.session_id == ""
        assert orchestrator.call_state is None
        assert orchestrator.config.max_duration_seconds == 300.0

    def test_init_custom_config(self) -> None:
        """Test initialization with custom config."""
        config = SessionConfig(
            max_duration_seconds=600.0,
            target_latency_ms=1500.0,
            max_retry_attempts=5,
        )
        orchestrator = Orchestrator(
            MockSTTProvider(),
            MockLLMProvider(),
            MockTTSProvider(),
            config=config,
        )

        assert orchestrator.config.max_duration_seconds == 600.0
        assert orchestrator.config.target_latency_ms == 1500.0
        assert orchestrator.config.max_retry_attempts == 5


class TestSessionLifecycle:
    """Tests for session start/end lifecycle."""

    @pytest.fixture
    def orchestrator(self) -> Orchestrator:
        """Create orchestrator with mocked providers."""
        return Orchestrator(
            MockSTTProvider(),
            MockLLMProvider(),
            MockTTSProvider(),
        )

    @pytest.mark.asyncio
    async def test_start_session(self, orchestrator: Orchestrator) -> None:
        """Test starting a new session."""
        await orchestrator.start_session(
            call_id="call-123",
            from_number="+15551234567",
            initial_language="en",
        )

        assert orchestrator.session_id != ""
        assert orchestrator.state == OrchestratorState.LISTENING
        assert orchestrator.call_state == CallState.INIT
        assert orchestrator.language == "en"

    @pytest.mark.asyncio
    async def test_start_session_spanish(self, orchestrator: Orchestrator) -> None:
        """Test starting a session in Spanish."""
        await orchestrator.start_session(
            call_id="call-456",
            initial_language="es",
        )

        assert orchestrator.language == "es"

    @pytest.mark.asyncio
    async def test_start_session_already_active(self, orchestrator: Orchestrator) -> None:
        """Test starting a session when one is already active."""
        await orchestrator.start_session(call_id="call-1")

        with pytest.raises(OrchestratorError, match="Session already active"):
            await orchestrator.start_session(call_id="call-2")

    @pytest.mark.asyncio
    async def test_end_session(self, orchestrator: Orchestrator) -> None:
        """Test ending a session."""
        await orchestrator.start_session(call_id="call-123")
        summary = await orchestrator.end_session()

        assert summary["call_id"] == "call-123"
        assert "duration_seconds" in summary
        assert summary["turns_count"] == 0
        assert orchestrator.state == OrchestratorState.ENDED

    @pytest.mark.asyncio
    async def test_end_session_no_active(self, orchestrator: Orchestrator) -> None:
        """Test ending when no session is active."""
        summary = await orchestrator.end_session()
        assert summary["status"] == "no_active_session"


class TestProcessAudio:
    """Tests for the main process_audio pipeline."""

    @pytest.fixture
    def orchestrator(self) -> Orchestrator:
        """Create orchestrator with mocked providers."""
        return Orchestrator(
            MockSTTProvider(),
            MockLLMProvider(),
            MockTTSProvider(),
        )

    @pytest.mark.asyncio
    async def test_process_audio_basic(self, orchestrator: Orchestrator) -> None:
        """Test basic audio processing pipeline."""
        await orchestrator.start_session(call_id="call-123")

        result = await orchestrator.process_audio(b"audio_data")

        assert result is not None
        assert result.audio_bytes == b"mock_audio_data"
        assert len(orchestrator.turns) == 1
        assert orchestrator.turns[0].user_text == "Hello, I need help"
        assert "How can I help" in orchestrator.turns[0].assistant_text

    @pytest.mark.asyncio
    async def test_process_audio_updates_history(self, orchestrator: Orchestrator) -> None:
        """Test that conversation history is updated."""
        await orchestrator.start_session(call_id="call-123")
        await orchestrator.process_audio(b"audio_data")

        history = orchestrator.conversation_history
        # Should have: system, user, assistant
        assert len(history) >= 3
        assert history[0].role == MessageRole.SYSTEM
        assert history[-2].role == MessageRole.USER
        assert history[-1].role == MessageRole.ASSISTANT

    @pytest.mark.asyncio
    async def test_process_audio_with_callback(self, orchestrator: Orchestrator) -> None:
        """Test audio processing with callback."""
        await orchestrator.start_session(call_id="call-123")

        received_audio = []

        async def callback(audio: bytes) -> None:
            received_audio.append(audio)

        await orchestrator.process_audio(b"audio_data", audio_callback=callback)

        assert len(received_audio) == 1
        assert received_audio[0] == b"mock_audio_data"

    @pytest.mark.asyncio
    async def test_process_audio_latency_tracking(self, orchestrator: Orchestrator) -> None:
        """Test that latency metrics are tracked."""
        await orchestrator.start_session(call_id="call-123")
        await orchestrator.process_audio(b"audio_data")

        metrics = orchestrator.metrics
        assert metrics.stt_latency_ms >= 0
        assert metrics.llm_latency_ms >= 0
        assert metrics.tts_latency_ms >= 0
        assert metrics.total_turn_latency_ms > 0

    @pytest.mark.asyncio
    async def test_process_audio_session_ended(self, orchestrator: Orchestrator) -> None:
        """Test processing after session ended returns None."""
        await orchestrator.start_session(call_id="call-123")
        await orchestrator.end_session()

        result = await orchestrator.process_audio(b"audio_data")
        assert result is None


class TestToolCalls:
    """Tests for tool call handling."""

    @pytest.fixture
    def mock_tool_handler(self) -> MagicMock:
        """Create mock tool handler."""
        handler = MagicMock()
        handler.execute = AsyncMock(
            return_value=HandlerResult(
                status=HandlerStatus.SUCCESS,
                data={"task_id": "task-123", "call_id": "call-123"},
                tool_name="create_callback_task",
            )
        )
        return handler

    @pytest.mark.asyncio
    async def test_tool_call_execution(self, mock_tool_handler: MagicMock) -> None:
        """Test that tool calls are executed."""
        llm = MockLLMProvider()
        # First response triggers tool call, second is follow-up
        tool_call_response = LLMResponse(
            content=None,
            tool_calls=[
                ToolCall(
                    id="call_123",
                    name="create_callback_task",
                    arguments={
                        "call_id": "call-123",
                        "callback_number": "+15551234567",
                    },
                )
            ],
            finish_reason=FinishReason.TOOL_CALLS,
        )
        follow_up_response = LLMResponse(
            content="I've created a callback request for you.",
            finish_reason=FinishReason.STOP,
        )

        call_count = 0

        async def mock_complete(messages, tools=None, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return tool_call_response
            return follow_up_response

        llm.complete = mock_complete

        orchestrator = Orchestrator(
            MockSTTProvider(),
            llm,
            MockTTSProvider(),
            tool_handler=mock_tool_handler,
        )

        await orchestrator.start_session(call_id="call-123")
        await orchestrator.process_audio(b"audio_data")

        # Verify tool was executed
        mock_tool_handler.execute.assert_called_once()
        call_args = mock_tool_handler.execute.call_args
        assert call_args[1]["tool_name"] == "create_callback_task"

        # Verify turn recorded tool call
        assert len(orchestrator.turns) == 1
        assert len(orchestrator.turns[0].tool_calls) == 1
        assert orchestrator.turns[0].tool_calls[0].name == "create_callback_task"

    @pytest.mark.asyncio
    async def test_tool_call_without_handler(self) -> None:
        """Test tool calls are ignored without handler."""
        llm = MockLLMProvider()
        llm.response = LLMResponse(
            content="Let me help you with that.",
            tool_calls=[
                ToolCall(id="call_1", name="some_tool", arguments={})
            ],
            finish_reason=FinishReason.TOOL_CALLS,
        )

        orchestrator = Orchestrator(
            MockSTTProvider(),
            llm,
            MockTTSProvider(),
            # No tool handler
        )

        await orchestrator.start_session(call_id="call-123")
        result = await orchestrator.process_audio(b"audio_data")

        # Should still return audio
        assert result is not None


class TestErrorRecovery:
    """Tests for error handling and retry logic."""

    @pytest.mark.asyncio
    async def test_stt_retry_success(self) -> None:
        """Test STT succeeds after retry."""
        stt = MockSTTProvider()
        fail_count = 0

        async def failing_transcribe(audio, language="en"):
            nonlocal fail_count
            if fail_count < 2:
                fail_count += 1
                raise Exception("Temporary failure")
            return TranscriptResult(
                text="Hello",
                confidence=0.9,
                language=language,
                duration=1.0,
            )

        stt.transcribe = failing_transcribe

        config = SessionConfig(max_retry_attempts=3, retry_delay_seconds=0.01)
        orchestrator = Orchestrator(
            stt,
            MockLLMProvider(),
            MockTTSProvider(),
            config=config,
        )

        await orchestrator.start_session(call_id="call-123")
        result = await orchestrator.process_audio(b"audio")

        assert result is not None
        assert fail_count == 2  # Failed twice, succeeded on third

    @pytest.mark.asyncio
    async def test_stt_all_retries_fail(self) -> None:
        """Test STTFailureError after all retries exhausted."""
        stt = MockSTTProvider()
        stt.should_fail = True

        config = SessionConfig(max_retry_attempts=2, retry_delay_seconds=0.01)
        orchestrator = Orchestrator(
            stt,
            MockLLMProvider(),
            MockTTSProvider(),
            config=config,
        )

        await orchestrator.start_session(call_id="call-123")

        with pytest.raises(STTFailureError):
            await orchestrator.process_audio(b"audio")

        assert stt.fail_count == 2

    @pytest.mark.asyncio
    async def test_llm_retry_success(self) -> None:
        """Test LLM succeeds after retry."""
        llm = MockLLMProvider()
        fail_count = 0

        async def failing_complete(messages, tools=None, **kwargs):
            nonlocal fail_count
            if fail_count < 1:
                fail_count += 1
                raise LLMError("Rate limited")
            return LLMResponse(content="Hello!", finish_reason=FinishReason.STOP)

        llm.complete = failing_complete

        config = SessionConfig(max_retry_attempts=3, retry_delay_seconds=0.01)
        orchestrator = Orchestrator(
            MockSTTProvider(),
            llm,
            MockTTSProvider(),
            config=config,
        )

        await orchestrator.start_session(call_id="call-123")
        result = await orchestrator.process_audio(b"audio")

        assert result is not None

    @pytest.mark.asyncio
    async def test_llm_all_retries_fail(self) -> None:
        """Test LLMFailureError after all retries exhausted."""
        llm = MockLLMProvider()
        llm.should_fail = True

        config = SessionConfig(max_retry_attempts=2, retry_delay_seconds=0.01)
        orchestrator = Orchestrator(
            MockSTTProvider(),
            llm,
            MockTTSProvider(),
            config=config,
        )

        await orchestrator.start_session(call_id="call-123")

        with pytest.raises(LLMFailureError):
            await orchestrator.process_audio(b"audio")

    @pytest.mark.asyncio
    async def test_tts_all_retries_fail(self) -> None:
        """Test TTSFailureError after all retries exhausted."""
        tts = MockTTSProvider()
        tts.should_fail = True

        config = SessionConfig(max_retry_attempts=2, retry_delay_seconds=0.01)
        orchestrator = Orchestrator(
            MockSTTProvider(),
            MockLLMProvider(),
            tts,
            config=config,
        )

        await orchestrator.start_session(call_id="call-123")

        with pytest.raises(TTSFailureError):
            await orchestrator.process_audio(b"audio")


class TestSessionTimeout:
    """Tests for session timeout handling."""

    @pytest.mark.asyncio
    async def test_session_timeout(self) -> None:
        """Test session timeout is detected."""
        config = SessionConfig(max_duration_seconds=0.1)  # 100ms timeout
        orchestrator = Orchestrator(
            MockSTTProvider(),
            MockLLMProvider(),
            MockTTSProvider(),
            config=config,
        )

        await orchestrator.start_session(call_id="call-123")
        await asyncio.sleep(0.15)  # Wait for timeout

        with pytest.raises(SessionTimeoutError):
            await orchestrator.process_audio(b"audio")


class TestStateTransitions:
    """Tests for state machine transitions."""

    @pytest.fixture
    def orchestrator(self) -> Orchestrator:
        """Create orchestrator with mocked providers."""
        return Orchestrator(
            MockSTTProvider(),
            MockLLMProvider(),
            MockTTSProvider(),
        )

    @pytest.mark.asyncio
    async def test_initial_state_progression(self, orchestrator: Orchestrator) -> None:
        """Test state progresses from INIT."""
        await orchestrator.start_session(call_id="call-123")

        assert orchestrator.call_state == CallState.INIT

        # After processing, should auto-progress
        await orchestrator.process_audio(b"audio")

        # Should have moved past INIT
        assert orchestrator.call_state != CallState.INIT

    @pytest.mark.asyncio
    async def test_language_change(self, orchestrator: Orchestrator) -> None:
        """Test language can be changed."""
        await orchestrator.start_session(call_id="call-123", initial_language="en")
        assert orchestrator.language == "en"

        orchestrator.set_language("es")
        assert orchestrator.language == "es"

    @pytest.mark.asyncio
    async def test_invalid_language(self, orchestrator: Orchestrator) -> None:
        """Test invalid language raises error."""
        await orchestrator.start_session(call_id="call-123")

        with pytest.raises(ValueError, match="Unsupported language"):
            orchestrator.set_language("fr")


class TestGreeting:
    """Tests for greeting generation."""

    @pytest.mark.asyncio
    async def test_generate_greeting_english(self) -> None:
        """Test generating English greeting."""
        orchestrator = Orchestrator(
            MockSTTProvider(),
            MockLLMProvider(),
            MockTTSProvider(),
        )

        await orchestrator.start_session(call_id="call-123", initial_language="en")
        greeting = await orchestrator.generate_greeting()

        assert greeting.audio_bytes == b"mock_audio_data"
        # Greeting should be in history
        history = orchestrator.conversation_history
        assert any("Hello" in (m.content or "") for m in history)

    @pytest.mark.asyncio
    async def test_generate_greeting_spanish(self) -> None:
        """Test generating Spanish greeting."""
        tts = MockTTSProvider()
        orchestrator = Orchestrator(
            MockSTTProvider(),
            MockLLMProvider(),
            tts,
        )

        await orchestrator.start_session(call_id="call-123", initial_language="es")
        await orchestrator.generate_greeting()

        # Should use Spanish voice
        assert len(tts.synthesize_calls) == 1
        assert tts.synthesize_calls[0][1] == Language.SPANISH

    @pytest.mark.asyncio
    async def test_generate_greeting_no_session(self) -> None:
        """Test greeting fails without session."""
        orchestrator = Orchestrator(
            MockSTTProvider(),
            MockLLMProvider(),
            MockTTSProvider(),
        )

        with pytest.raises(OrchestratorError, match="Session not started"):
            await orchestrator.generate_greeting()


class TestTranscript:
    """Tests for transcript generation."""

    @pytest.mark.asyncio
    async def test_get_transcript(self) -> None:
        """Test getting conversation transcript."""
        orchestrator = Orchestrator(
            MockSTTProvider(),
            MockLLMProvider(),
            MockTTSProvider(),
        )

        await orchestrator.start_session(call_id="call-123")
        await orchestrator.process_audio(b"audio1")
        await orchestrator.process_audio(b"audio2")

        transcript = orchestrator.get_transcript()

        assert "User:" in transcript
        assert "Assistant:" in transcript
        # Should have multiple turns
        assert transcript.count("User:") == 2


class TestSessionStats:
    """Tests for session statistics."""

    @pytest.mark.asyncio
    async def test_get_session_stats(self) -> None:
        """Test getting session statistics."""
        orchestrator = Orchestrator(
            MockSTTProvider(),
            MockLLMProvider(),
            MockTTSProvider(),
        )

        await orchestrator.start_session(call_id="call-123")
        await orchestrator.process_audio(b"audio")

        stats = orchestrator.get_session_stats()

        assert stats["call_id"] == "call-123"
        assert stats["turns_count"] == 1
        assert "duration_seconds" in stats
        assert "average_turn_latency_ms" in stats
        assert stats["language"] == "en"

    @pytest.mark.asyncio
    async def test_get_session_stats_no_session(self) -> None:
        """Test stats empty without session."""
        orchestrator = Orchestrator(
            MockSTTProvider(),
            MockLLMProvider(),
            MockTTSProvider(),
        )

        stats = orchestrator.get_session_stats()
        assert stats == {}


class TestLatencyMetrics:
    """Tests for LatencyMetrics dataclass."""

    def test_latency_metrics_reset(self) -> None:
        """Test resetting latency metrics."""
        metrics = LatencyMetrics(
            stt_latency_ms=100.0,
            llm_latency_ms=200.0,
            tts_latency_ms=50.0,
            tool_latency_ms=30.0,
            total_turn_latency_ms=400.0,
        )

        metrics.reset()

        assert metrics.stt_latency_ms == 0.0
        assert metrics.llm_latency_ms == 0.0
        assert metrics.tts_latency_ms == 0.0
        assert metrics.tool_latency_ms == 0.0
        assert metrics.total_turn_latency_ms == 0.0


class TestConversationTurn:
    """Tests for ConversationTurn dataclass."""

    def test_conversation_turn_defaults(self) -> None:
        """Test ConversationTurn default values."""
        turn = ConversationTurn()

        assert turn.user_text == ""
        assert turn.assistant_text == ""
        assert turn.tool_calls == []
        assert turn.tool_results == []
        assert turn.timestamp > 0
