"""Speech-to-text implementations.

This module provides the STT provider interface and implementations.
"""

from vozbot.speech.stt.base import (
    STTProvider,
    SupportedLanguage,
    TranscriptChunk,
    TranscriptResult,
)
from vozbot.speech.stt.deepgram_adapter import (
    DeepgramSTT,
    STTError,
    STTInvalidAudioError,
    STTRateLimitError,
    STTTimeoutError,
)

__all__ = [
    "DeepgramSTT",
    "STTError",
    "STTInvalidAudioError",
    "STTProvider",
    "STTRateLimitError",
    "STTTimeoutError",
    "SupportedLanguage",
    "TranscriptChunk",
    "TranscriptResult",
]
