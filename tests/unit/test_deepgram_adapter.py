"""Unit tests for the DeepgramSTT adapter implementation.

Tests cover:
- DeepgramSTT class implementing STTProvider ABC
- Batch transcription with mocked responses
- Streaming transcription with mocked WebSocket
- Error handling for timeout, invalid audio, rate limits
- Language validation
- Confidence threshold configuration
"""

import asyncio
import os
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vozbot.speech.stt import (
    DeepgramSTT,
    STTError,
    STTInvalidAudioError,
    STTProvider,
    STTRateLimitError,
    STTTimeoutError,
    TranscriptResult,
)


class TestDeepgramSTTInterface:
    """Tests that DeepgramSTT implements STTProvider correctly."""

    def test_deepgram_stt_extends_stt_provider(self) -> None:
        """Verify DeepgramSTT extends STTProvider ABC."""
        adapter = DeepgramSTT(api_key="test_key")
        assert isinstance(adapter, STTProvider)

    def test_adapter_has_all_required_methods(self) -> None:
        """Verify DeepgramSTT implements all abstract methods."""
        adapter = DeepgramSTT(api_key="test_key")

        assert hasattr(adapter, "transcribe")
        assert hasattr(adapter, "transcribe_stream")
        assert callable(adapter.transcribe)
        assert callable(adapter.transcribe_stream)


class TestDeepgramSTTInitialization:
    """Tests for DeepgramSTT initialization."""

    def test_init_with_explicit_api_key(self) -> None:
        """Test initialization with explicitly provided API key."""
        adapter = DeepgramSTT(api_key="dg_test_key_12345")

        assert adapter.api_key == "dg_test_key_12345"
        assert adapter.confidence_threshold == 0.8  # Default
        assert adapter.timeout == 30.0  # Default
        assert adapter._client is None  # Lazy initialization

    def test_init_with_env_var(self) -> None:
        """Test initialization from environment variable."""
        with patch.dict(os.environ, {"DEEPGRAM_API_KEY": "dg_env_key_67890"}):
            adapter = DeepgramSTT()

            assert adapter.api_key == "dg_env_key_67890"

    def test_explicit_api_key_overrides_env_var(self) -> None:
        """Test that explicit API key takes precedence over env var."""
        with patch.dict(os.environ, {"DEEPGRAM_API_KEY": "dg_env_key"}):
            adapter = DeepgramSTT(api_key="dg_explicit_key")

            assert adapter.api_key == "dg_explicit_key"

    def test_init_with_custom_confidence_threshold(self) -> None:
        """Test initialization with custom confidence threshold."""
        adapter = DeepgramSTT(api_key="test_key", confidence_threshold=0.9)

        assert adapter.confidence_threshold == 0.9

    def test_init_with_custom_timeout(self) -> None:
        """Test initialization with custom timeout."""
        adapter = DeepgramSTT(api_key="test_key", timeout=60.0)

        assert adapter.timeout == 60.0

    def test_init_rejects_invalid_confidence_threshold_too_high(self) -> None:
        """Test that confidence threshold > 1.0 raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            DeepgramSTT(api_key="test_key", confidence_threshold=1.5)

        assert "confidence_threshold" in str(exc_info.value)

    def test_init_rejects_invalid_confidence_threshold_negative(self) -> None:
        """Test that negative confidence threshold raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            DeepgramSTT(api_key="test_key", confidence_threshold=-0.1)

        assert "confidence_threshold" in str(exc_info.value)

    def test_init_accepts_boundary_confidence_thresholds(self) -> None:
        """Test that boundary values 0.0 and 1.0 are accepted."""
        adapter1 = DeepgramSTT(api_key="test_key", confidence_threshold=0.0)
        adapter2 = DeepgramSTT(api_key="test_key", confidence_threshold=1.0)

        assert adapter1.confidence_threshold == 0.0
        assert adapter2.confidence_threshold == 1.0


class TestDeepgramClientProperty:
    """Tests for the lazy-loaded Deepgram client property."""

    def test_client_raises_without_api_key(self) -> None:
        """Test that accessing client without API key raises ValueError."""
        adapter = DeepgramSTT(api_key="")

        with pytest.raises(ValueError) as exc_info:
            _ = adapter.client

        assert "api key not configured" in str(exc_info.value).lower()

    @patch("vozbot.speech.stt.deepgram_adapter.AsyncDeepgramClient")
    def test_client_lazy_initialization(self, mock_client_class: MagicMock) -> None:
        """Test that client is lazily initialized."""
        mock_client_class.return_value = MagicMock()

        adapter = DeepgramSTT(api_key="dg_test_key")

        # Client not created yet
        mock_client_class.assert_not_called()

        # Access client
        _ = adapter.client

        # Now it should be created
        mock_client_class.assert_called_once()

    @patch("vozbot.speech.stt.deepgram_adapter.AsyncDeepgramClient")
    def test_client_cached_after_first_access(self, mock_client_class: MagicMock) -> None:
        """Test that client is cached after first access."""
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance

        adapter = DeepgramSTT(api_key="dg_test_key")

        # Access client multiple times
        client1 = adapter.client
        client2 = adapter.client
        client3 = adapter.client

        # Should only create once
        mock_client_class.assert_called_once()
        assert client1 is client2 is client3


class TestLanguageValidation:
    """Tests for language code validation."""

    def test_validate_english_language(self) -> None:
        """Test that 'en' is accepted and mapped correctly."""
        adapter = DeepgramSTT(api_key="test_key")
        result = adapter._validate_language("en")
        assert result == "en-US"

    def test_validate_spanish_language(self) -> None:
        """Test that 'es' is accepted and mapped correctly."""
        adapter = DeepgramSTT(api_key="test_key")
        result = adapter._validate_language("es")
        assert result == "es"

    def test_validate_unsupported_language(self) -> None:
        """Test that unsupported language raises ValueError."""
        adapter = DeepgramSTT(api_key="test_key")

        with pytest.raises(ValueError) as exc_info:
            adapter._validate_language("fr")

        assert "unsupported language" in str(exc_info.value).lower()
        assert "fr" in str(exc_info.value)


class TestDeepgramTranscribe:
    """Tests for the transcribe (batch) method."""

    @pytest.fixture
    def mock_deepgram_response(self) -> MagicMock:
        """Create a mock Deepgram prerecorded response."""
        response = MagicMock()
        response.results = MagicMock()
        response.results.channels = [MagicMock()]
        response.results.channels[0].alternatives = [MagicMock()]
        response.results.channels[0].alternatives[0].transcript = "Hello, how can I help you?"
        response.results.channels[0].alternatives[0].confidence = 0.95
        response.metadata = MagicMock()
        response.metadata.duration = 2.5
        return response

    @pytest.fixture
    def adapter_with_mock_client(self) -> DeepgramSTT:
        """Create a DeepgramSTT with a mocked client."""
        adapter = DeepgramSTT(api_key="dg_test_key")
        adapter._client = MagicMock()
        return adapter

    async def test_transcribe_returns_transcript_result(
        self,
        adapter_with_mock_client: DeepgramSTT,
        mock_deepgram_response: MagicMock,
    ) -> None:
        """Test transcribe method returns TranscriptResult."""
        # Setup mock
        mock_transcribe = AsyncMock(return_value=mock_deepgram_response)
        adapter_with_mock_client._client.listen.v1.media.transcribe_file = mock_transcribe

        audio_data = b"fake audio data"
        result = await adapter_with_mock_client.transcribe(audio_data, "en")

        assert isinstance(result, TranscriptResult)
        assert result.text == "Hello, how can I help you?"
        assert result.confidence == 0.95
        assert result.language == "en"
        assert result.duration == 2.5

    async def test_transcribe_with_spanish(
        self,
        adapter_with_mock_client: DeepgramSTT,
        mock_deepgram_response: MagicMock,
    ) -> None:
        """Test transcribe with Spanish language."""
        mock_deepgram_response.results.channels[0].alternatives[0].transcript = (
            "Hola, como puedo ayudarle?"
        )
        mock_transcribe = AsyncMock(return_value=mock_deepgram_response)
        adapter_with_mock_client._client.listen.v1.media.transcribe_file = mock_transcribe

        result = await adapter_with_mock_client.transcribe(b"audio", "es")

        assert result.text == "Hola, como puedo ayudarle?"
        assert result.language == "es"

    async def test_transcribe_empty_audio_raises_error(
        self,
        adapter_with_mock_client: DeepgramSTT,
    ) -> None:
        """Test that empty audio raises STTInvalidAudioError."""
        with pytest.raises(STTInvalidAudioError) as exc_info:
            await adapter_with_mock_client.transcribe(b"", "en")

        assert "empty" in str(exc_info.value).lower()

    async def test_transcribe_invalid_language_raises_error(
        self,
        adapter_with_mock_client: DeepgramSTT,
    ) -> None:
        """Test that unsupported language raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            await adapter_with_mock_client.transcribe(b"audio", "fr")

        assert "unsupported language" in str(exc_info.value).lower()

    async def test_transcribe_timeout_raises_error(
        self,
        adapter_with_mock_client: DeepgramSTT,
    ) -> None:
        """Test that API timeout raises STTTimeoutError."""
        # Create an async mock that times out
        async def timeout_mock(*args: object, **kwargs: object) -> None:
            await asyncio.sleep(100)

        adapter_with_mock_client._client.listen.v1.media.transcribe_file = timeout_mock
        adapter_with_mock_client.timeout = 0.01  # Very short timeout

        with pytest.raises(STTTimeoutError) as exc_info:
            await adapter_with_mock_client.transcribe(b"audio", "en")

        assert "timed out" in str(exc_info.value).lower()

    async def test_transcribe_empty_response_returns_empty_result(
        self,
        adapter_with_mock_client: DeepgramSTT,
    ) -> None:
        """Test handling of empty response from Deepgram."""
        empty_response = MagicMock()
        empty_response.results = MagicMock()
        empty_response.results.channels = []

        mock_transcribe = AsyncMock(return_value=empty_response)
        adapter_with_mock_client._client.listen.v1.media.transcribe_file = mock_transcribe

        result = await adapter_with_mock_client.transcribe(b"audio", "en")

        assert result.text == ""
        assert result.confidence == 0.0
        assert result.language == "en"

    async def test_transcribe_no_alternatives_returns_empty_result(
        self,
        adapter_with_mock_client: DeepgramSTT,
    ) -> None:
        """Test handling when no alternatives in response."""
        response = MagicMock()
        response.results = MagicMock()
        response.results.channels = [MagicMock()]
        response.results.channels[0].alternatives = []

        mock_transcribe = AsyncMock(return_value=response)
        adapter_with_mock_client._client.listen.v1.media.transcribe_file = mock_transcribe

        result = await adapter_with_mock_client.transcribe(b"audio", "en")

        assert result.text == ""
        assert result.confidence == 0.0

    async def test_transcribe_null_results_returns_empty_result(
        self,
        adapter_with_mock_client: DeepgramSTT,
    ) -> None:
        """Test handling when results is None."""
        response = MagicMock()
        response.results = None

        mock_transcribe = AsyncMock(return_value=response)
        adapter_with_mock_client._client.listen.v1.media.transcribe_file = mock_transcribe

        result = await adapter_with_mock_client.transcribe(b"audio", "en")

        assert result.text == ""
        assert result.confidence == 0.0


class TestDeepgramTranscribeStream:
    """Tests for the transcribe_stream (streaming) method."""

    @pytest.fixture
    def adapter_with_mock_client(self) -> DeepgramSTT:
        """Create a DeepgramSTT with a mocked client."""
        adapter = DeepgramSTT(api_key="dg_test_key")
        adapter._client = MagicMock()
        return adapter

    async def test_transcribe_stream_invalid_language_raises_error(
        self,
        adapter_with_mock_client: DeepgramSTT,
    ) -> None:
        """Test that unsupported language raises ValueError."""

        async def audio_gen() -> AsyncIterator[bytes]:
            yield b"audio"

        with pytest.raises(ValueError) as exc_info:
            async for _ in adapter_with_mock_client.transcribe_stream(audio_gen(), "fr"):
                pass

        assert "unsupported language" in str(exc_info.value).lower()

    async def test_transcribe_stream_connection_not_started(
        self,
        adapter_with_mock_client: DeepgramSTT,
    ) -> None:
        """Test handling when WebSocket connection is not established."""
        # Mock an empty async iterator (no connections established)
        async def empty_connect(*args: object, **kwargs: object) -> AsyncIterator[MagicMock]:
            return
            yield  # Make it an async generator

        adapter_with_mock_client._client.listen.v1.connect = empty_connect

        async def audio_gen() -> AsyncIterator[bytes]:
            yield b"audio"

        with pytest.raises(STTError) as exc_info:
            async for _ in adapter_with_mock_client.transcribe_stream(audio_gen(), "en"):
                pass

        assert "failed to start" in str(exc_info.value).lower()


class TestDeepgramErrorHandling:
    """Tests for error handling in DeepgramSTT."""

    @pytest.fixture
    def adapter_with_mock_client(self) -> DeepgramSTT:
        """Create a DeepgramSTT with a mocked client."""
        adapter = DeepgramSTT(api_key="dg_test_key")
        adapter._client = MagicMock()
        return adapter

    async def test_rate_limit_error_handling(
        self,
        adapter_with_mock_client: DeepgramSTT,
    ) -> None:
        """Test that rate limit errors are properly wrapped."""
        from deepgram.core.api_error import ApiError

        error = ApiError(
            headers=None,
            status_code=429,
            body="Rate limit exceeded",
        )

        async def raise_error(*args: object, **kwargs: object) -> None:
            raise error

        adapter_with_mock_client._client.listen.v1.media.transcribe_file = raise_error

        with pytest.raises(STTRateLimitError):
            await adapter_with_mock_client.transcribe(b"audio", "en")

    async def test_invalid_format_error_handling(
        self,
        adapter_with_mock_client: DeepgramSTT,
    ) -> None:
        """Test that invalid format errors are properly wrapped."""
        from deepgram.core.api_error import ApiError

        error = ApiError(
            headers=None,
            status_code=400,
            body="Invalid audio format",
        )

        async def raise_error(*args: object, **kwargs: object) -> None:
            raise error

        adapter_with_mock_client._client.listen.v1.media.transcribe_file = raise_error

        with pytest.raises(STTInvalidAudioError):
            await adapter_with_mock_client.transcribe(b"audio", "en")

    async def test_generic_deepgram_error_handling(
        self,
        adapter_with_mock_client: DeepgramSTT,
    ) -> None:
        """Test that generic Deepgram errors are wrapped in STTError."""
        from deepgram.core.api_error import ApiError

        error = ApiError(
            headers=None,
            status_code=500,
            body="Unknown server error",
        )

        async def raise_error(*args: object, **kwargs: object) -> None:
            raise error

        adapter_with_mock_client._client.listen.v1.media.transcribe_file = raise_error

        with pytest.raises(STTError) as exc_info:
            await adapter_with_mock_client.transcribe(b"audio", "en")

        # Should not be a more specific subclass
        assert type(exc_info.value) is STTError

    async def test_unexpected_error_handling(
        self,
        adapter_with_mock_client: DeepgramSTT,
    ) -> None:
        """Test that unexpected errors are wrapped in STTError."""

        async def raise_error(*args: object, **kwargs: object) -> None:
            raise RuntimeError("Unexpected failure")

        adapter_with_mock_client._client.listen.v1.media.transcribe_file = raise_error

        with pytest.raises(STTError) as exc_info:
            await adapter_with_mock_client.transcribe(b"audio", "en")

        assert "unexpected" in str(exc_info.value).lower()


class TestExportedSymbols:
    """Tests for proper module exports."""

    def test_deepgram_stt_exported_from_package(self) -> None:
        """Test that DeepgramSTT is exported from stt package."""
        from vozbot.speech.stt import DeepgramSTT as Exported

        assert Exported is DeepgramSTT

    def test_error_classes_exported_from_package(self) -> None:
        """Test that error classes are exported from stt package."""
        from vozbot.speech.stt import STTError as ExportedError
        from vozbot.speech.stt import STTInvalidAudioError as ExportedInvalid
        from vozbot.speech.stt import STTRateLimitError as ExportedRate
        from vozbot.speech.stt import STTTimeoutError as ExportedTimeout

        assert ExportedError is STTError
        assert ExportedTimeout is STTTimeoutError
        assert ExportedInvalid is STTInvalidAudioError
        assert ExportedRate is STTRateLimitError

    def test_error_inheritance(self) -> None:
        """Test that error classes have proper inheritance."""
        assert issubclass(STTTimeoutError, STTError)
        assert issubclass(STTInvalidAudioError, STTError)
        assert issubclass(STTRateLimitError, STTError)
        assert issubclass(STTError, Exception)
