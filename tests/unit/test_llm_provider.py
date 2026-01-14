"""Tests for the LLM provider abstract base class.

Verifies:
- ABC cannot be instantiated directly
- All dataclasses work correctly
- Type hints are complete
"""

from __future__ import annotations

import pytest
from typing import AsyncIterator, Any

from vozbot.agent.orchestrator.llm_base import (
    FinishReason,
    LLMChunk,
    LLMError,
    LLMProvider,
    LLMResponse,
    Message,
    MessageRole,
    TokenUsage,
    Tool,
    ToolCall,
    AuthenticationError,
    ContextLengthError,
    RateLimitError,
)


class TestLLMProviderABC:
    """Tests for LLMProvider abstract base class."""

    def test_cannot_instantiate_abc(self) -> None:
        """Verify LLMProvider cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            LLMProvider()  # type: ignore[abstract]

    def test_concrete_implementation_works(self) -> None:
        """Verify a concrete implementation can be instantiated."""

        class ConcreteProvider(LLMProvider):
            async def complete(
                self,
                messages: list[Message],
                tools: list[Tool] | None = None,
                **kwargs: Any,
            ) -> LLMResponse:
                return LLMResponse(content="test")

            async def stream_complete(
                self,
                messages: list[Message],
                tools: list[Tool] | None = None,
                **kwargs: Any,
            ) -> AsyncIterator[LLMChunk]:
                yield LLMChunk(content="test")

        # Should not raise
        provider = ConcreteProvider()
        assert provider is not None


class TestMessage:
    """Tests for Message dataclass."""

    def test_create_user_message(self) -> None:
        """Test creating a user message."""
        msg = Message(role=MessageRole.USER, content="Hello")
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello"
        assert msg.name is None
        assert msg.tool_call_id is None
        assert msg.tool_calls is None

    def test_create_system_message(self) -> None:
        """Test creating a system message."""
        msg = Message(role=MessageRole.SYSTEM, content="You are a helpful assistant")
        assert msg.role == MessageRole.SYSTEM
        assert msg.content == "You are a helpful assistant"

    def test_create_assistant_message_with_tool_calls(self) -> None:
        """Test creating an assistant message with tool calls."""
        tool_call = ToolCall(
            id="call_123",
            name="create_callback_task",
            arguments={"call_id": "abc", "callback_number": "+15551234567"},
        )
        msg = Message(
            role=MessageRole.ASSISTANT,
            content=None,
            tool_calls=[tool_call],
        )
        assert msg.role == MessageRole.ASSISTANT
        assert msg.content is None
        assert msg.tool_calls is not None
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].name == "create_callback_task"

    def test_create_tool_response_message(self) -> None:
        """Test creating a tool response message."""
        msg = Message(
            role=MessageRole.TOOL,
            content='{"success": true}',
            tool_call_id="call_123",
            name="create_callback_task",
        )
        assert msg.role == MessageRole.TOOL
        assert msg.tool_call_id == "call_123"
        assert msg.name == "create_callback_task"

    def test_to_dict_user_message(self) -> None:
        """Test converting user message to dict."""
        msg = Message(role=MessageRole.USER, content="Hello")
        result = msg.to_dict()
        assert result == {"role": "user", "content": "Hello"}

    def test_to_dict_with_tool_calls(self) -> None:
        """Test converting assistant message with tool calls to dict."""
        tool_call = ToolCall(
            id="call_123",
            name="test_func",
            arguments={"arg1": "value1"},
        )
        msg = Message(
            role=MessageRole.ASSISTANT,
            content=None,
            tool_calls=[tool_call],
        )
        result = msg.to_dict()
        assert result["role"] == "assistant"
        assert "tool_calls" in result
        assert len(result["tool_calls"]) == 1


class TestToolCall:
    """Tests for ToolCall dataclass."""

    def test_create_tool_call(self) -> None:
        """Test creating a tool call."""
        tc = ToolCall(
            id="call_abc",
            name="create_callback_task",
            arguments={"call_id": "123", "priority": "high"},
        )
        assert tc.id == "call_abc"
        assert tc.name == "create_callback_task"
        assert tc.arguments == {"call_id": "123", "priority": "high"}

    def test_to_dict(self) -> None:
        """Test converting tool call to dict."""
        tc = ToolCall(
            id="call_abc",
            name="test_func",
            arguments={"key": "value"},
        )
        result = tc.to_dict()
        assert result["id"] == "call_abc"
        assert result["type"] == "function"
        assert result["function"]["name"] == "test_func"
        # Arguments should be JSON string
        assert '"key"' in result["function"]["arguments"]


class TestTokenUsage:
    """Tests for TokenUsage dataclass."""

    def test_create_token_usage(self) -> None:
        """Test creating token usage."""
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_create_text_response(self) -> None:
        """Test creating a text response."""
        resp = LLMResponse(
            content="Hello, how can I help?",
            usage=TokenUsage(100, 20, 120),
            finish_reason=FinishReason.STOP,
        )
        assert resp.content == "Hello, how can I help?"
        assert resp.has_tool_calls is False
        assert resp.finish_reason == FinishReason.STOP

    def test_create_tool_call_response(self) -> None:
        """Test creating a response with tool calls."""
        tc = ToolCall(id="call_1", name="test", arguments={})
        resp = LLMResponse(
            content=None,
            tool_calls=[tc],
            finish_reason=FinishReason.TOOL_CALLS,
        )
        assert resp.content is None
        assert resp.has_tool_calls is True
        assert len(resp.tool_calls) == 1
        assert resp.finish_reason == FinishReason.TOOL_CALLS

    def test_default_values(self) -> None:
        """Test default values are set correctly."""
        resp = LLMResponse()
        assert resp.content is None
        assert resp.tool_calls == []
        assert resp.usage is None
        assert resp.finish_reason == FinishReason.STOP
        assert resp.model is None


class TestLLMChunk:
    """Tests for LLMChunk dataclass."""

    def test_create_content_chunk(self) -> None:
        """Test creating a content chunk."""
        chunk = LLMChunk(content="Hello")
        assert chunk.content == "Hello"
        assert chunk.tool_calls == []
        assert chunk.finish_reason is None

    def test_create_final_chunk(self) -> None:
        """Test creating a final chunk with finish reason."""
        chunk = LLMChunk(content="", finish_reason=FinishReason.STOP)
        assert chunk.finish_reason == FinishReason.STOP


class TestTool:
    """Tests for Tool dataclass."""

    def test_create_tool(self) -> None:
        """Test creating a tool definition."""
        tool = Tool(
            name="create_callback_task",
            description="Create a callback task for office staff",
            parameters={
                "type": "object",
                "properties": {
                    "call_id": {"type": "string"},
                    "callback_number": {"type": "string"},
                },
                "required": ["call_id", "callback_number"],
            },
        )
        assert tool.name == "create_callback_task"
        assert "callback task" in tool.description

    def test_to_dict(self) -> None:
        """Test converting tool to dict."""
        tool = Tool(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object", "properties": {}},
        )
        result = tool.to_dict()
        assert result["type"] == "function"
        assert result["function"]["name"] == "test_tool"
        assert result["function"]["description"] == "A test tool"
        assert "parameters" in result["function"]


class TestFinishReason:
    """Tests for FinishReason enum."""

    def test_all_finish_reasons(self) -> None:
        """Test all finish reasons are defined."""
        assert FinishReason.STOP.value == "stop"
        assert FinishReason.LENGTH.value == "length"
        assert FinishReason.TOOL_CALLS.value == "tool_calls"
        assert FinishReason.CONTENT_FILTER.value == "content_filter"
        assert FinishReason.ERROR.value == "error"


class TestMessageRole:
    """Tests for MessageRole enum."""

    def test_all_message_roles(self) -> None:
        """Test all message roles are defined."""
        assert MessageRole.SYSTEM.value == "system"
        assert MessageRole.USER.value == "user"
        assert MessageRole.ASSISTANT.value == "assistant"
        assert MessageRole.TOOL.value == "tool"


class TestExceptions:
    """Tests for LLM exception classes."""

    def test_llm_error(self) -> None:
        """Test LLMError can be raised."""
        with pytest.raises(LLMError):
            raise LLMError("Test error")

    def test_rate_limit_error_inheritance(self) -> None:
        """Test RateLimitError inherits from LLMError."""
        error = RateLimitError("Rate limited")
        assert isinstance(error, LLMError)

    def test_context_length_error_inheritance(self) -> None:
        """Test ContextLengthError inherits from LLMError."""
        error = ContextLengthError("Context too long")
        assert isinstance(error, LLMError)

    def test_authentication_error_inheritance(self) -> None:
        """Test AuthenticationError inherits from LLMError."""
        error = AuthenticationError("Invalid API key")
        assert isinstance(error, LLMError)
