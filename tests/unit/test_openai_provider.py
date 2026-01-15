"""Tests for OpenAI LLM provider."""

from __future__ import annotations

import json
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vozbot.agent.orchestrator.llm_base import (
    AuthenticationError,
    ContextLengthError,
    FinishReason,
    LLMError,
    Message,
    MessageRole,
    RateLimitError,
    Tool,
)
from vozbot.agent.orchestrator.openai_provider import OpenAIProvider


class TestOpenAIProviderInit:
    """Tests for OpenAIProvider initialization."""

    def test_init_with_explicit_api_key(self) -> None:
        """Test initialization with explicit API key."""
        with patch("vozbot.agent.orchestrator.openai_provider.AsyncOpenAI"):
            provider = OpenAIProvider(api_key="test-key")
            assert provider._api_key == "test-key"

    def test_init_with_env_api_key(self) -> None:
        """Test initialization with API key from environment."""
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "env-key"}),
            patch("vozbot.agent.orchestrator.openai_provider.AsyncOpenAI"),
        ):
            provider = OpenAIProvider()
            assert provider._api_key == "env-key"

    def test_init_without_api_key_raises(self) -> None:
        """Test that missing API key raises AuthenticationError."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(AuthenticationError, match="OPENAI_API_KEY not set"):
                OpenAIProvider()

    def test_init_default_model(self) -> None:
        """Test default model is gpt-4o-mini."""
        with patch("vozbot.agent.orchestrator.openai_provider.AsyncOpenAI"):
            provider = OpenAIProvider(api_key="test-key")
            assert provider.model == "gpt-4o-mini"

    def test_init_custom_model(self) -> None:
        """Test custom model configuration."""
        with patch("vozbot.agent.orchestrator.openai_provider.AsyncOpenAI"):
            provider = OpenAIProvider(api_key="test-key", model="gpt-4o")
            assert provider.model == "gpt-4o"

    def test_init_model_from_env(self) -> None:
        """Test model from environment variable."""
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "key", "OPENAI_MODEL": "gpt-4"}),
            patch("vozbot.agent.orchestrator.openai_provider.AsyncOpenAI"),
        ):
            provider = OpenAIProvider()
            assert provider.model == "gpt-4"


class TestOpenAIProviderComplete:
    """Tests for OpenAIProvider.complete()."""

    @pytest.fixture
    def provider(self) -> OpenAIProvider:
        """Create provider with mocked client."""
        with patch("vozbot.agent.orchestrator.openai_provider.AsyncOpenAI") as mock_cls:
            provider = OpenAIProvider(api_key="test-key")
            provider._client = mock_cls.return_value
            return provider

    @pytest.fixture
    def mock_response(self) -> MagicMock:
        """Create mock ChatCompletion response."""
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "Hello! How can I help you?"
        response.choices[0].message.tool_calls = None
        response.choices[0].finish_reason = "stop"
        response.usage = MagicMock()
        response.usage.prompt_tokens = 10
        response.usage.completion_tokens = 20
        response.usage.total_tokens = 30
        response.model = "gpt-4o-mini"
        return response

    @pytest.mark.asyncio
    async def test_complete_simple_message(
        self, provider: OpenAIProvider, mock_response: MagicMock
    ) -> None:
        """Test basic completion without tools."""
        provider._client.chat.completions.create = AsyncMock(return_value=mock_response)

        messages = [Message(role=MessageRole.USER, content="Hello")]
        response = await provider.complete(messages)

        assert response.content == "Hello! How can I help you?"
        assert response.finish_reason == FinishReason.STOP
        assert response.usage is not None
        assert response.usage.total_tokens == 30
        assert provider.total_tokens_used == 30

    @pytest.mark.asyncio
    async def test_complete_with_tool_calls(self, provider: OpenAIProvider) -> None:
        """Test completion with tool calls."""
        # Mock response with tool call
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = None
        response.choices[0].message.tool_calls = [MagicMock()]
        response.choices[0].message.tool_calls[0].id = "call_123"
        response.choices[0].message.tool_calls[0].function.name = "create_callback_task"
        response.choices[0].message.tool_calls[0].function.arguments = json.dumps({
            "call_id": "uuid-123",
            "callback_number": "+15551234567",
            "priority": "normal",
        })
        response.choices[0].finish_reason = "tool_calls"
        response.usage = MagicMock()
        response.usage.prompt_tokens = 50
        response.usage.completion_tokens = 30
        response.usage.total_tokens = 80
        response.model = "gpt-4o-mini"

        provider._client.chat.completions.create = AsyncMock(return_value=response)

        messages = [Message(role=MessageRole.USER, content="I need a callback")]
        tools = [Tool(
            name="create_callback_task",
            description="Create a callback task",
            parameters={"type": "object", "properties": {}},
        )]

        result = await provider.complete(messages, tools=tools)

        assert result.content is None
        assert result.has_tool_calls
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "create_callback_task"
        assert result.tool_calls[0].arguments["call_id"] == "uuid-123"
        assert result.finish_reason == FinishReason.TOOL_CALLS

    @pytest.mark.asyncio
    async def test_complete_token_tracking(
        self, provider: OpenAIProvider, mock_response: MagicMock
    ) -> None:
        """Test that tokens are accumulated across calls."""
        provider._client.chat.completions.create = AsyncMock(return_value=mock_response)

        messages = [Message(role=MessageRole.USER, content="Hello")]

        await provider.complete(messages)
        assert provider.total_tokens_used == 30

        await provider.complete(messages)
        assert provider.total_tokens_used == 60


class TestOpenAIProviderStreamComplete:
    """Tests for OpenAIProvider.stream_complete()."""

    @pytest.fixture
    def provider(self) -> OpenAIProvider:
        """Create provider with mocked client."""
        with patch("vozbot.agent.orchestrator.openai_provider.AsyncOpenAI") as mock_cls:
            provider = OpenAIProvider(api_key="test-key")
            provider._client = mock_cls.return_value
            return provider

    @pytest.mark.asyncio
    async def test_stream_complete_yields_chunks(self, provider: OpenAIProvider) -> None:
        """Test streaming yields content chunks."""
        # Create mock chunks
        chunks = []
        for content in ["Hello", ", how", " can", " I help?"]:
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta.content = content
            chunk.choices[0].delta.tool_calls = None
            chunk.choices[0].finish_reason = None
            chunk.model = "gpt-4o-mini"
            chunks.append(chunk)

        # Final chunk with finish reason
        final_chunk = MagicMock()
        final_chunk.choices = [MagicMock()]
        final_chunk.choices[0].delta.content = ""
        final_chunk.choices[0].delta.tool_calls = None
        final_chunk.choices[0].finish_reason = "stop"
        final_chunk.model = "gpt-4o-mini"
        chunks.append(final_chunk)

        async def mock_stream() -> AsyncIterator[MagicMock]:
            for chunk in chunks:
                yield chunk

        provider._client.chat.completions.create = AsyncMock(return_value=mock_stream())

        messages = [Message(role=MessageRole.USER, content="Hello")]
        collected = []
        async for chunk in provider.stream_complete(messages):
            collected.append(chunk.content)

        assert "Hello" in collected
        assert collected[-1] == ""  # Final chunk is empty

    @pytest.mark.asyncio
    async def test_stream_complete_with_tool_calls(self, provider: OpenAIProvider) -> None:
        """Test streaming with tool call accumulation."""
        # Create mock chunks for tool call
        chunks = []

        # First chunk with tool call ID
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta.content = None
        tc1 = MagicMock()
        tc1.index = 0
        tc1.id = "call_abc"
        tc1.function = MagicMock()
        tc1.function.name = "create_callback_task"
        tc1.function.arguments = '{"call_id":'
        chunk1.choices[0].delta.tool_calls = [tc1]
        chunk1.choices[0].finish_reason = None
        chunk1.model = "gpt-4o-mini"
        chunks.append(chunk1)

        # Second chunk continuing arguments
        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta.content = None
        tc2 = MagicMock()
        tc2.index = 0
        tc2.id = None
        tc2.function = MagicMock()
        tc2.function.name = None
        tc2.function.arguments = '"uuid","callback_number":"+1555"}'
        chunk2.choices[0].delta.tool_calls = [tc2]
        chunk2.choices[0].finish_reason = None
        chunk2.model = "gpt-4o-mini"
        chunks.append(chunk2)

        # Final chunk
        chunk3 = MagicMock()
        chunk3.choices = [MagicMock()]
        chunk3.choices[0].delta.content = None
        chunk3.choices[0].delta.tool_calls = None
        chunk3.choices[0].finish_reason = "tool_calls"
        chunk3.model = "gpt-4o-mini"
        chunks.append(chunk3)

        async def mock_stream() -> AsyncIterator[MagicMock]:
            for chunk in chunks:
                yield chunk

        provider._client.chat.completions.create = AsyncMock(return_value=mock_stream())

        messages = [Message(role=MessageRole.USER, content="I need a callback")]
        final_chunk = None
        async for chunk in provider.stream_complete(messages):
            if chunk.finish_reason == FinishReason.TOOL_CALLS:
                final_chunk = chunk

        assert final_chunk is not None
        assert len(final_chunk.tool_calls) == 1
        assert final_chunk.tool_calls[0].name == "create_callback_task"


class TestOpenAIProviderErrorHandling:
    """Tests for error handling in OpenAIProvider."""

    @pytest.fixture
    def provider(self) -> OpenAIProvider:
        """Create provider with mocked client."""
        with patch("vozbot.agent.orchestrator.openai_provider.AsyncOpenAI") as mock_cls:
            provider = OpenAIProvider(api_key="test-key")
            provider._client = mock_cls.return_value
            return provider

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, provider: OpenAIProvider) -> None:
        """Test rate limit error is properly converted."""
        from openai import RateLimitError as OpenAIRateLimit

        error = OpenAIRateLimit(
            message="Rate limit exceeded",
            response=MagicMock(),
            body=None,
        )
        provider._client.chat.completions.create = AsyncMock(side_effect=error)

        messages = [Message(role=MessageRole.USER, content="Hello")]

        with pytest.raises(RateLimitError):
            await provider.complete(messages)

    @pytest.mark.asyncio
    async def test_auth_error(self, provider: OpenAIProvider) -> None:
        """Test authentication error is properly converted."""
        from openai import AuthenticationError as OpenAIAuth

        error = OpenAIAuth(
            message="Invalid API key",
            response=MagicMock(),
            body=None,
        )
        provider._client.chat.completions.create = AsyncMock(side_effect=error)

        messages = [Message(role=MessageRole.USER, content="Hello")]

        with pytest.raises(AuthenticationError):
            await provider.complete(messages)

    @pytest.mark.asyncio
    async def test_context_length_error(self, provider: OpenAIProvider) -> None:
        """Test context length error is properly converted."""
        from openai import BadRequestError

        error = BadRequestError(
            message="This model's maximum context_length is 128000 tokens",
            response=MagicMock(),
            body=None,
        )
        provider._client.chat.completions.create = AsyncMock(side_effect=error)

        messages = [Message(role=MessageRole.USER, content="Hello")]

        with pytest.raises(ContextLengthError):
            await provider.complete(messages)

    @pytest.mark.asyncio
    async def test_generic_error(self, provider: OpenAIProvider) -> None:
        """Test generic errors are wrapped in LLMError."""
        provider._client.chat.completions.create = AsyncMock(
            side_effect=Exception("Unknown error")
        )

        messages = [Message(role=MessageRole.USER, content="Hello")]

        with pytest.raises(LLMError, match="Unknown error"):
            await provider.complete(messages)


class TestOpenAIProviderIntegration:
    """Integration-style tests for OpenAIProvider."""

    @pytest.fixture
    def provider(self) -> OpenAIProvider:
        """Create provider with mocked client."""
        with patch("vozbot.agent.orchestrator.openai_provider.AsyncOpenAI") as mock_cls:
            provider = OpenAIProvider(api_key="test-key")
            provider._client = mock_cls.return_value
            return provider

    @pytest.mark.asyncio
    async def test_conversation_with_tool_call(self, provider: OpenAIProvider) -> None:
        """Test a conversation flow that results in a tool call."""
        # Mock response that includes a tool call with valid callback task args
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = None
        response.choices[0].message.tool_calls = [MagicMock()]
        response.choices[0].message.tool_calls[0].id = "call_xyz"
        response.choices[0].message.tool_calls[0].function.name = "create_callback_task"
        response.choices[0].message.tool_calls[0].function.arguments = json.dumps({
            "call_id": "call-uuid-123",
            "callback_number": "+15551234567",
            "priority": "high",
            "name": "John Doe",
            "notes": "Needs appointment for dental checkup",
        })
        response.choices[0].finish_reason = "tool_calls"
        response.usage = MagicMock()
        response.usage.prompt_tokens = 100
        response.usage.completion_tokens = 50
        response.usage.total_tokens = 150
        response.model = "gpt-4o-mini"

        provider._client.chat.completions.create = AsyncMock(return_value=response)

        # Simulate conversation
        messages = [
            Message(role=MessageRole.SYSTEM, content="You are VozBot..."),
            Message(role=MessageRole.USER, content="I need to schedule a dental appointment"),
            Message(
                role=MessageRole.ASSISTANT,
                content="I'd be happy to help. May I have your name?",
            ),
            Message(role=MessageRole.USER, content="John Doe"),
            Message(
                role=MessageRole.ASSISTANT,
                content="What's the best number to call you back?",
            ),
            Message(role=MessageRole.USER, content="555-123-4567"),
        ]

        from vozbot.agent.tools.schemas import get_all_tool_schemas

        # Convert to Tool objects
        tools = [
            Tool(
                name=schema["function"]["name"],
                description=schema["function"]["description"],
                parameters=schema["function"]["parameters"],
            )
            for schema in get_all_tool_schemas()
        ]

        result = await provider.complete(messages, tools=tools)

        # Verify the response has the tool call with valid arguments
        assert result.has_tool_calls
        assert result.tool_calls[0].name == "create_callback_task"
        args = result.tool_calls[0].arguments
        assert args["call_id"] == "call-uuid-123"
        assert args["callback_number"] == "+15551234567"
        assert args["priority"] == "high"
        assert args["name"] == "John Doe"
