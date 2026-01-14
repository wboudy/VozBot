"""Base speech-to-text provider interface.

This module defines the abstract base class for speech-to-text providers,
enabling pluggable implementations for different STT services
(e.g., Deepgram, Google Cloud Speech, AWS Transcribe).
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum


class SupportedLanguage(Enum):
    """Supported languages for speech-to-text transcription.

    Uses ISO 639-1 language codes.
    """

    ENGLISH = "en"
    SPANISH = "es"


@dataclass
class TranscriptResult:
    """Result of a complete transcription.

    Attributes:
        text: The transcribed text.
        confidence: Confidence score between 0.0 and 1.0.
        language: The detected or specified language code.
        duration: Duration of the audio in seconds.
    """

    text: str
    confidence: float
    language: str
    duration: float


@dataclass
class TranscriptChunk:
    """Chunk result from streaming transcription.

    Attributes:
        partial_text: The transcribed text so far in this utterance.
        is_final: Whether this chunk represents a final transcription
            for the current utterance (False for interim results).
    """

    partial_text: str
    is_final: bool


class STTProvider(ABC):
    """Abstract base class for speech-to-text provider adapters.

    This interface defines the contract that all STT provider
    implementations must follow. Implementations should handle
    provider-specific API calls and error handling.

    All methods are async to support non-blocking I/O operations
    with STT APIs.

    Example:
        ```python
        class DeepgramSTT(STTProvider):
            async def transcribe(
                self,
                audio_bytes: bytes,
                language: str = "en",
            ) -> TranscriptResult:
                # Deepgram-specific implementation
                ...
        ```
    """

    @abstractmethod
    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str = "en",
    ) -> TranscriptResult:
        """Transcribe audio data to text (batch mode).

        Args:
            audio_bytes: Raw audio data as bytes (PCM, WAV, or provider-specific format).
            language: Language code for transcription. Must be one of the
                supported languages ("en" for English, "es" for Spanish).
                Defaults to "en".

        Returns:
            TranscriptResult containing the transcribed text, confidence score,
            language, and audio duration.

        Raises:
            STTError: If transcription fails.
            ValueError: If an unsupported language is specified.
        """
        ...

    @abstractmethod
    def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        language: str = "en",
    ) -> AsyncIterator[TranscriptChunk]:
        """Transcribe streaming audio data in real-time.

        This method processes audio chunks as they arrive and yields
        partial transcription results for low-latency applications.

        Implementations should be async generators (using async def with yield).
        The abstract signature is declared without async to correctly type
        the AsyncIterator return.

        Args:
            audio_stream: Async iterator yielding audio data chunks.
            language: Language code for transcription. Must be one of the
                supported languages ("en" for English, "es" for Spanish).
                Defaults to "en".

        Yields:
            TranscriptChunk objects containing partial transcriptions.
            Chunks with is_final=True indicate completed utterances.

        Raises:
            STTError: If transcription fails.
            ValueError: If an unsupported language is specified.

        Example:
            ```python
            async for chunk in provider.transcribe_stream(audio_chunks, "en"):
                if chunk.is_final:
                    print(f"Final: {chunk.partial_text}")
                else:
                    print(f"Partial: {chunk.partial_text}")
            ```
        """
        ...
