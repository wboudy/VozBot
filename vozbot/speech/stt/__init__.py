"""Speech-to-text implementations.

This module provides the STT provider interface and implementations.
"""

from vozbot.speech.stt.base import (
    STTProvider,
    SupportedLanguage,
    TranscriptChunk,
    TranscriptResult,
)

__all__ = [
    "STTProvider",
    "SupportedLanguage",
    "TranscriptChunk",
    "TranscriptResult",
]
