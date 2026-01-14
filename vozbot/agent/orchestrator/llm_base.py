"""LLM Provider abstract base class and related types.

This module defines the interface for LLM providers, enabling pluggable
implementations for different LLM services (e.g., OpenAI, Anthropic, local models).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator


class FinishReason(str, Enum):
    """Reason for completion termination."""

    STOP = "stop"  # Natural completion
    LENGTH = "length"  # Max tokens reached
    TOOL_CALLS = "tool_calls"  # Model wants to call tools
    CONTENT_FILTER = "content_filter"  # Content filtered
    ERROR = "error"  # Error occurred


class MessageRole(str, Enum):
    """Role for messages in conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """A message in a conversation following OpenAI format.

    Attributes:
        role: The role of the message sender.
        content: The text content of the message.
        name: Optional name for tool messages (function name).
        tool_call_id: Optional ID for tool response messages.
        tool_calls: Optional list of tool calls (for assistant messages).
    """

    role: MessageRole
    content: str | None = None
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to OpenAI-compatible dict format."""
        result: dict[str, Any] = {"role": self.role.value}

        if self.content is not None:
            result["content"] = self.content

        if self.name is not None:
            result["name"] = self.name

        if self.tool_call_id is not None:
            result["tool_call_id"] = self.tool_call_id

        if self.tool_calls:
            result["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]

        return result


@dataclass
class ToolCall:
    """Represents a tool/function call from the LLM.

    Attributes:
        id: Unique identifier for this tool call.
        name: Name of the function to call.
        arguments: Arguments to pass to the function (parsed JSON as dict).
    """

    id: str
    name: str
    arguments: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to OpenAI-compatible dict format."""
        import json

        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": json.dumps(self.arguments),
            },
        }


@dataclass
class TokenUsage:
    """Token usage statistics for an LLM call.

    Attributes:
        prompt_tokens: Number of tokens in the prompt.
        completion_tokens: Number of tokens in the completion.
        total_tokens: Total tokens used.
    """

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class LLMResponse:
    """Response from an LLM completion call.

    Attributes:
        content: The text content of the response (may be None if tool_calls present).
        tool_calls: List of tool calls requested by the model.
        usage: Token usage statistics.
        finish_reason: Reason the completion finished.
        model: The model that generated this response.
    """

    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: TokenUsage | None = None
    finish_reason: FinishReason = FinishReason.STOP
    model: str | None = None

    @property
    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return len(self.tool_calls) > 0


@dataclass
class LLMChunk:
    """A chunk of streaming response from an LLM.

    Attributes:
        content: Delta text content (may be empty).
        tool_calls: Partial tool call data in this chunk.
        finish_reason: Set on the final chunk.
        model: The model generating this stream.
    """

    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: FinishReason | None = None
    model: str | None = None


@dataclass
class Tool:
    """Definition of a tool/function that can be called by the LLM.

    Follows OpenAI function calling format.

    Attributes:
        name: The name of the function.
        description: Description of what the function does.
        parameters: JSON Schema for the function parameters.
    """

    name: str
    description: str
    parameters: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to OpenAI-compatible tool format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class LLMProvider(ABC):
    """Abstract base class for LLM provider adapters.

    This interface defines the contract that all LLM provider
    implementations must follow. Implementations should handle
    provider-specific API calls, authentication, and error handling.

    All methods are async to support non-blocking I/O operations
    with LLM APIs.

    Example:
        ```python
        class OpenAIProvider(LLMProvider):
            async def complete(
                self,
                messages: list[Message],
                tools: list[Tool] | None = None,
                **kwargs: Any,
            ) -> LLMResponse:
                # OpenAI-specific implementation
                ...
        ```
    """

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion from the LLM.

        Args:
            messages: List of messages in the conversation.
            tools: Optional list of tools the model can call.
            **kwargs: Provider-specific options (temperature, max_tokens, etc.).

        Returns:
            LLMResponse containing the completion result.

        Raises:
            LLMError: If the completion fails.
        """
        ...

    @abstractmethod
    async def stream_complete(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[LLMChunk]:
        """Stream a completion from the LLM.

        Args:
            messages: List of messages in the conversation.
            tools: Optional list of tools the model can call.
            **kwargs: Provider-specific options (temperature, max_tokens, etc.).

        Yields:
            LLMChunk objects containing incremental response data.

        Raises:
            LLMError: If the streaming fails.
        """
        ...
        # Note: yield statement needed in concrete implementations
        # This is just for type checking
        if False:
            yield LLMChunk()


class LLMError(Exception):
    """Base exception for LLM-related errors."""

    pass


class RateLimitError(LLMError):
    """Raised when rate limit is exceeded."""

    pass


class ContextLengthError(LLMError):
    """Raised when context length is exceeded."""

    pass


class AuthenticationError(LLMError):
    """Raised when authentication fails."""

    pass
