"""Tests for the STTProvider abstract base class."""

import asyncio
from collections.abc import AsyncIterator

import pytest

from vozbot.speech.stt.base import (
    STTProvider,
    SupportedLanguage,
    TranscriptChunk,
    TranscriptResult,
)


class TestTranscriptResult:
    """Tests for the TranscriptResult dataclass."""

    def test_create_transcript_result(self) -> None:
        """Test creating a TranscriptResult instance with all fields."""
        result = TranscriptResult(
            text="Hello, how can I help you?",
            confidence=0.95,
            language="en",
            duration=2.5,
        )

        assert result.text == "Hello, how can I help you?"
        assert result.confidence == 0.95
        assert result.language == "en"
        assert result.duration == 2.5

    def test_transcript_result_equality(self) -> None:
        """Test that two TranscriptResult instances with same values are equal."""
        result1 = TranscriptResult(
            text="Test transcription",
            confidence=0.9,
            language="es",
            duration=1.5,
        )
        result2 = TranscriptResult(
            text="Test transcription",
            confidence=0.9,
            language="es",
            duration=1.5,
        )

        assert result1 == result2

    def test_transcript_result_different_values_not_equal(self) -> None:
        """Test that TranscriptResult instances with different values are not equal."""
        result1 = TranscriptResult(
            text="Hello",
            confidence=0.9,
            language="en",
            duration=1.0,
        )
        result2 = TranscriptResult(
            text="Goodbye",
            confidence=0.9,
            language="en",
            duration=1.0,
        )

        assert result1 != result2


class TestTranscriptChunk:
    """Tests for the TranscriptChunk dataclass."""

    def test_create_partial_chunk(self) -> None:
        """Test creating a partial (non-final) TranscriptChunk."""
        chunk = TranscriptChunk(
            partial_text="Hello",
            is_final=False,
        )

        assert chunk.partial_text == "Hello"
        assert chunk.is_final is False

    def test_create_final_chunk(self) -> None:
        """Test creating a final TranscriptChunk."""
        chunk = TranscriptChunk(
            partial_text="Hello, how can I help you?",
            is_final=True,
        )

        assert chunk.partial_text == "Hello, how can I help you?"
        assert chunk.is_final is True

    def test_transcript_chunk_equality(self) -> None:
        """Test that two TranscriptChunk instances with same values are equal."""
        chunk1 = TranscriptChunk(partial_text="Test", is_final=True)
        chunk2 = TranscriptChunk(partial_text="Test", is_final=True)

        assert chunk1 == chunk2


class TestSupportedLanguage:
    """Tests for the SupportedLanguage enum."""

    def test_english_language_value(self) -> None:
        """Test that English has correct value."""
        assert SupportedLanguage.ENGLISH.value == "en"

    def test_spanish_language_value(self) -> None:
        """Test that Spanish has correct value."""
        assert SupportedLanguage.SPANISH.value == "es"

    def test_supported_languages_count(self) -> None:
        """Verify expected number of supported languages."""
        # Currently supporting English and Spanish
        assert len(SupportedLanguage) == 2

    def test_can_create_from_value(self) -> None:
        """Test that enum can be created from string value."""
        assert SupportedLanguage("en") == SupportedLanguage.ENGLISH
        assert SupportedLanguage("es") == SupportedLanguage.SPANISH


class TestSTTProviderABC:
    """Tests for the STTProvider abstract base class."""

    def test_cannot_instantiate_directly(self) -> None:
        """Verify that STTProvider cannot be instantiated directly."""
        with pytest.raises(TypeError) as exc_info:
            STTProvider()  # type: ignore[abstract]

        # Check that the error mentions abstract methods
        error_message = str(exc_info.value)
        assert "abstract" in error_message.lower() or "instantiate" in error_message.lower()

    def test_subclass_must_implement_transcribe(self) -> None:
        """Verify that a subclass missing transcribe cannot be instantiated."""

        class IncompleteSTT(STTProvider):
            """Incomplete implementation missing transcribe method."""

            async def transcribe_stream(
                self,
                audio_stream: AsyncIterator[bytes],
                language: str = "en",
            ) -> AsyncIterator[TranscriptChunk]:
                yield TranscriptChunk(partial_text="", is_final=True)

        with pytest.raises(TypeError) as exc_info:
            IncompleteSTT()  # type: ignore[abstract]

        error_message = str(exc_info.value)
        assert "abstract" in error_message.lower()

    def test_subclass_must_implement_transcribe_stream(self) -> None:
        """Verify that a subclass missing transcribe_stream cannot be instantiated."""

        class IncompleteSTT(STTProvider):
            """Incomplete implementation missing transcribe_stream method."""

            async def transcribe(
                self,
                audio_bytes: bytes,
                language: str = "en",
            ) -> TranscriptResult:
                return TranscriptResult(
                    text="",
                    confidence=0.0,
                    language=language,
                    duration=0.0,
                )

        with pytest.raises(TypeError) as exc_info:
            IncompleteSTT()  # type: ignore[abstract]

        error_message = str(exc_info.value)
        assert "abstract" in error_message.lower()

    def test_complete_subclass_can_be_instantiated(self) -> None:
        """Verify that a complete implementation can be instantiated."""

        class CompleteSTT(STTProvider):
            """Complete implementation of all required methods."""

            async def transcribe(
                self,
                audio_bytes: bytes,
                language: str = "en",
            ) -> TranscriptResult:
                return TranscriptResult(
                    text="Test transcription",
                    confidence=0.95,
                    language=language,
                    duration=1.0,
                )

            async def transcribe_stream(
                self,
                audio_stream: AsyncIterator[bytes],
                language: str = "en",
            ) -> AsyncIterator[TranscriptChunk]:
                yield TranscriptChunk(partial_text="Test", is_final=True)

        # Should not raise
        stt = CompleteSTT()
        assert isinstance(stt, STTProvider)


class MockSTTProvider(STTProvider):
    """Mock implementation for testing async methods."""

    def __init__(self) -> None:
        self.transcribe_calls: list[tuple[bytes, str]] = []
        self.stream_calls: list[str] = []

    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str = "en",
    ) -> TranscriptResult:
        self.transcribe_calls.append((audio_bytes, language))
        return TranscriptResult(
            text="Hello, how can I help you?",
            confidence=0.95,
            language=language,
            duration=2.5,
        )

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        language: str = "en",
    ) -> AsyncIterator[TranscriptChunk]:
        self.stream_calls.append(language)
        # Consume the stream
        async for _ in audio_stream:
            pass
        yield TranscriptChunk(partial_text="Hello", is_final=False)
        yield TranscriptChunk(partial_text="Hello, how can I help you?", is_final=True)


class TestSTTProviderMethods:
    """Tests for STTProvider method signatures and behavior."""

    @pytest.fixture
    def mock_stt(self) -> MockSTTProvider:
        """Create a mock STT provider for testing."""
        return MockSTTProvider()

    def test_transcribe_returns_transcript_result(self, mock_stt: MockSTTProvider) -> None:
        """Test transcribe method returns TranscriptResult."""
        audio_data = b"fake audio data"
        result = asyncio.run(mock_stt.transcribe(audio_data, "en"))

        assert isinstance(result, TranscriptResult)
        assert result.text == "Hello, how can I help you?"
        assert result.confidence == 0.95
        assert result.language == "en"
        assert result.duration == 2.5

    def test_transcribe_records_call(self, mock_stt: MockSTTProvider) -> None:
        """Test that transcribe call is recorded."""
        audio_data = b"test audio"
        asyncio.run(mock_stt.transcribe(audio_data, "es"))

        assert (audio_data, "es") in mock_stt.transcribe_calls

    def test_transcribe_default_language(self, mock_stt: MockSTTProvider) -> None:
        """Test transcribe uses English as default language."""
        audio_data = b"test audio"
        result = asyncio.run(mock_stt.transcribe(audio_data))

        assert result.language == "en"
        assert (audio_data, "en") in mock_stt.transcribe_calls

    def test_transcribe_stream_yields_chunks(self, mock_stt: MockSTTProvider) -> None:
        """Test transcribe_stream yields TranscriptChunk objects."""

        async def run_stream() -> list[TranscriptChunk]:
            chunks = []

            async def audio_generator() -> AsyncIterator[bytes]:
                yield b"chunk1"
                yield b"chunk2"

            async for chunk in mock_stt.transcribe_stream(audio_generator(), "en"):
                chunks.append(chunk)
            return chunks

        chunks = asyncio.run(run_stream())

        assert len(chunks) == 2
        assert all(isinstance(c, TranscriptChunk) for c in chunks)
        assert chunks[0].partial_text == "Hello"
        assert chunks[0].is_final is False
        assert chunks[1].partial_text == "Hello, how can I help you?"
        assert chunks[1].is_final is True

    def test_transcribe_stream_records_language(self, mock_stt: MockSTTProvider) -> None:
        """Test that transcribe_stream records the language used."""

        async def run_stream() -> None:
            async def audio_generator() -> AsyncIterator[bytes]:
                yield b"data"

            async for _ in mock_stt.transcribe_stream(audio_generator(), "es"):
                pass

        asyncio.run(run_stream())

        assert "es" in mock_stt.stream_calls
