"""Text-to-speech implementations."""

from vozbot.speech.tts.base import (
    AudioFormat,
    AudioResult,
    Language,
    TTSProvider,
    Voice,
    VoiceGender,
)
from vozbot.speech.tts.deepgram_adapter import (
    DeepgramTTS,
    TTSError,
    TTSInvalidTextError,
    TTSRateLimitError,
    TTSTimeoutError,
)

__all__ = [
    "AudioFormat",
    "AudioResult",
    "DeepgramTTS",
    "Language",
    "TTSError",
    "TTSInvalidTextError",
    "TTSProvider",
    "TTSRateLimitError",
    "TTSTimeoutError",
    "Voice",
    "VoiceGender",
]
