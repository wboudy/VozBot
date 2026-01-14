"""Base TTS provider interface.

This module defines the abstract base class for text-to-speech providers,
enabling pluggable implementations for different TTS services
(e.g., Deepgram, Google Cloud TTS, Amazon Polly).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class AudioFormat(Enum):
    """Supported audio output formats."""

    MP3 = "mp3"
    WAV = "wav"
    PCM = "pcm"


class VoiceGender(Enum):
    """Voice gender options."""

    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"


class Language(Enum):
    """Supported languages for TTS synthesis."""

    ENGLISH = "en"
    SPANISH = "es"


@dataclass
class Voice:
    """Representation of a TTS voice.

    Attributes:
        id: Unique identifier for the voice from the TTS provider.
        name: Human-readable name of the voice.
        language: Language code for the voice.
        gender: Gender classification of the voice.
    """

    id: str
    name: str
    language: Language
    gender: VoiceGender


@dataclass
class AudioResult:
    """Result of a TTS synthesis operation.

    Attributes:
        audio_bytes: The synthesized audio data.
        format: The audio format of the result.
        duration: Duration of the audio in seconds.
        sample_rate: Sample rate of the audio in Hz.
    """

    audio_bytes: bytes
    format: AudioFormat
    duration: float
    sample_rate: int


class TTSProvider(ABC):
    """Abstract base class for text-to-speech provider adapters.

    This interface defines the contract that all TTS provider
    implementations must follow. Implementations should handle
    provider-specific API calls and error handling.

    All methods are async to support non-blocking I/O operations
    with TTS APIs.

    Example:
        ```python
        class DeepgramTTSProvider(TTSProvider):
            async def synthesize(
                self,
                text: str,
                language: Language,
                voice: str,
                audio_format: AudioFormat = AudioFormat.MP3,
            ) -> AudioResult:
                # Deepgram-specific implementation
                ...
        ```
    """

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        language: Language,
        voice: str,
        audio_format: AudioFormat = AudioFormat.MP3,
    ) -> AudioResult:
        """Synthesize speech from text.

        Args:
            text: The text to convert to speech.
            language: The language for synthesis (en or es).
            voice: The voice ID to use for synthesis.
            audio_format: The desired output audio format.

        Returns:
            AudioResult containing the synthesized audio data.

        Raises:
            TTSError: If synthesis fails.
        """
        ...

    @abstractmethod
    async def get_available_voices(self, language: Language) -> list[Voice]:
        """Get available voices for a given language.

        Args:
            language: The language to filter voices by.

        Returns:
            List of Voice objects available for the specified language.

        Raises:
            TTSError: If voices cannot be retrieved.
        """
        ...
