"""OpenAI LLM provider implementation.

This module provides the OpenAI adapter for the LLMProvider interface,
supporting GPT-4o models with tool calling, streaming, and token tracking.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, AsyncIterator

from openai import AsyncOpenAI
from openai import AuthenticationError as OpenAIAuth
from openai import BadRequestError
from openai import RateLimitError as OpenAIRateLimit
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from .llm_base import (
    AuthenticationError,
    ContextLengthError,
    FinishReason,
    LLMChunk,
    LLMError,
    LLMProvider,
    LLMResponse,
    Message,
    RateLimitError,
    TokenUsage,
    Tool,
    ToolCall,
)

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider using GPT-4o models.

    Implements the LLMProvider interface for OpenAI's API, supporting:
    - Non-streaming completions with tool calling
    - Streaming completions with real-time chunks
    - Token usage tracking across calls
    - Proper error handling and exception mapping

    Attributes:
        model: The OpenAI model being used.
        total_tokens_used: Cumulative token count across all calls.

    Example:
        ```python
        provider = OpenAIProvider()
        response = await provider.complete(
            messages=[Message(role=MessageRole.USER, content="Hello")],
        )
        print(response.content)
        ```
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        """Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key. Defaults to OPENAI_API_KEY env var.
            model: Model name. Defaults to OPENAI_MODEL env var or gpt-4o-mini.

        Raises:
            AuthenticationError: If no API key is provided or found.
        """
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self._api_key:
            raise AuthenticationError("OPENAI_API_KEY not set")

        self._model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self._client = AsyncOpenAI(api_key=self._api_key)
        self._total_tokens_used = 0

    @property
    def model(self) -> str:
        """Get the current model name."""
        return self._model

    @property
    def total_tokens_used(self) -> int:
        """Get total tokens used across all calls."""
        return self._total_tokens_used

    async def complete(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion from OpenAI.

        Args:
            messages: List of messages in the conversation.
            tools: Optional list of tools the model can call.
            **kwargs: Additional OpenAI parameters (temperature, max_tokens, etc.).

        Returns:
            LLMResponse containing the completion result.

        Raises:
            RateLimitError: If rate limit is exceeded.
            AuthenticationError: If authentication fails.
            ContextLengthError: If context length is exceeded.
            LLMError: For other API errors.
        """
        # Convert messages to OpenAI format
        openai_messages = [m.to_dict() for m in messages]

        # Build request params
        params: dict[str, Any] = {
            "model": self._model,
            "messages": openai_messages,
            **kwargs,
        }

        # Add tools if provided
        if tools:
            params["tools"] = [t.to_dict() for t in tools]

        try:
            logger.debug(f"OpenAI complete request: model={self._model}, messages={len(messages)}")
            response: ChatCompletion = await self._client.chat.completions.create(**params)
            result = self._parse_response(response)
            logger.debug(f"OpenAI complete response: finish_reason={result.finish_reason}, tool_calls={len(result.tool_calls)}")
            return result
        except (OpenAIRateLimit, OpenAIAuth, BadRequestError) as e:
            raise self._convert_exception(e) from e
        except Exception as e:
            logger.exception("OpenAI API call failed")
            raise LLMError(str(e)) from e

    async def stream_complete(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[LLMChunk]:
        """Stream a completion from OpenAI.

        Args:
            messages: List of messages in the conversation.
            tools: Optional list of tools the model can call.
            **kwargs: Additional OpenAI parameters.

        Yields:
            LLMChunk objects containing incremental response data.

        Raises:
            RateLimitError: If rate limit is exceeded.
            AuthenticationError: If authentication fails.
            ContextLengthError: If context length is exceeded.
            LLMError: For other API errors.
        """
        openai_messages = [m.to_dict() for m in messages]

        params: dict[str, Any] = {
            "model": self._model,
            "messages": openai_messages,
            "stream": True,
            **kwargs,
        }

        if tools:
            params["tools"] = [t.to_dict() for t in tools]

        try:
            logger.debug(f"OpenAI stream request: model={self._model}, messages={len(messages)}")
            stream = await self._client.chat.completions.create(**params)

            # Accumulate tool calls across chunks
            tool_call_accumulators: dict[int, dict[str, Any]] = {}

            async for chunk in stream:
                yield self._parse_chunk(chunk, tool_call_accumulators)

        except (OpenAIRateLimit, OpenAIAuth, BadRequestError) as e:
            raise self._convert_exception(e) from e
        except Exception as e:
            logger.exception("OpenAI streaming failed")
            raise LLMError(str(e)) from e

    def _parse_response(self, response: ChatCompletion) -> LLMResponse:
        """Parse OpenAI response to LLMResponse.

        Args:
            response: Raw OpenAI ChatCompletion response.

        Returns:
            Parsed LLMResponse object.
        """
        choice = response.choices[0]
        message = choice.message

        # Parse tool calls
        tool_calls: list[ToolCall] = []
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    arguments = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse tool call arguments: {tc.function.arguments}")
                    arguments = {}

                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=arguments,
                    )
                )

        # Parse usage
        usage = None
        if response.usage:
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )
            self._total_tokens_used += usage.total_tokens

        # Map finish reason
        finish_reason = self._map_finish_reason(choice.finish_reason)

        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=finish_reason,
            model=response.model,
        )

    def _parse_chunk(
        self,
        chunk: ChatCompletionChunk,
        accumulators: dict[int, dict[str, Any]],
    ) -> LLMChunk:
        """Parse streaming chunk.

        Args:
            chunk: Raw OpenAI streaming chunk.
            accumulators: Dict to accumulate tool call data across chunks.

        Returns:
            Parsed LLMChunk object.
        """
        if not chunk.choices:
            return LLMChunk(model=chunk.model)

        choice = chunk.choices[0]
        delta = choice.delta

        # Handle tool call deltas
        tool_calls: list[ToolCall] = []
        if delta.tool_calls:
            for tc_delta in delta.tool_calls:
                idx = tc_delta.index
                if idx not in accumulators:
                    accumulators[idx] = {
                        "id": "",
                        "name": "",
                        "arguments": "",
                    }

                if tc_delta.id:
                    accumulators[idx]["id"] = tc_delta.id
                if tc_delta.function:
                    if tc_delta.function.name:
                        accumulators[idx]["name"] = tc_delta.function.name
                    if tc_delta.function.arguments:
                        accumulators[idx]["arguments"] += tc_delta.function.arguments

        # Emit completed tool calls on finish
        finish_reason = None
        if choice.finish_reason:
            finish_reason = self._map_finish_reason(choice.finish_reason)
            if finish_reason == FinishReason.TOOL_CALLS:
                for acc in accumulators.values():
                    if acc["id"] and acc["name"]:
                        try:
                            args = json.loads(acc["arguments"]) if acc["arguments"] else {}
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse streamed tool arguments: {acc['arguments']}")
                            args = {}
                        tool_calls.append(
                            ToolCall(
                                id=acc["id"],
                                name=acc["name"],
                                arguments=args,
                            )
                        )

        return LLMChunk(
            content=delta.content or "",
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            model=chunk.model,
        )

    def _map_finish_reason(self, reason: str | None) -> FinishReason:
        """Map OpenAI finish reason to enum.

        Args:
            reason: Raw finish reason string from OpenAI.

        Returns:
            Mapped FinishReason enum value.
        """
        mapping = {
            "stop": FinishReason.STOP,
            "length": FinishReason.LENGTH,
            "tool_calls": FinishReason.TOOL_CALLS,
            "content_filter": FinishReason.CONTENT_FILTER,
        }
        return mapping.get(reason or "", FinishReason.STOP)

    def _convert_exception(self, e: Exception) -> LLMError:
        """Convert OpenAI exceptions to LLMError types.

        Args:
            e: Original OpenAI exception.

        Returns:
            Appropriate LLMError subclass.
        """
        if isinstance(e, OpenAIRateLimit):
            return RateLimitError(str(e))
        elif isinstance(e, OpenAIAuth):
            return AuthenticationError(str(e))
        elif isinstance(e, BadRequestError) and "context_length" in str(e).lower():
            return ContextLengthError(str(e))
        else:
            return LLMError(str(e))
