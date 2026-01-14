"""Deepgram implementation of the TTSProvider interface.

Provides text-to-speech synthesis using the Deepgram Aura API for
generating natural-sounding speech in English and Spanish.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from io import BytesIO

from deepgram import DeepgramClient

from vozbot.speech.tts.base import (
    AudioFormat,
    AudioResult,
    Language,
    TTSProvider,
    Voice,
    VoiceGender,
)


class TTSError(Exception):
    """Base exception for TTS-related errors."""

    pass


class TTSTimeoutError(TTSError):
    """Raised when TTS API times out."""

    pass


class TTSInvalidTextError(TTSError):
    """Raised when text input is invalid or empty."""

    pass


class TTSRateLimitError(TTSError):
    """Raised when API rate limits are exceeded."""

    pass


class DeepgramTTS(TTSProvider):
    """Deepgram implementation of the TTSProvider interface.

    Uses the Deepgram Aura-2 API for high-quality text-to-speech synthesis
    with support for English and Spanish voices in both male and female options.

    Environment Variables:
        DEEPGRAM_API_KEY: Deepgram API key for authentication

    Attributes:
        default_english_voice: Default voice ID for English synthesis.
        default_spanish_voice: Default voice ID for Spanish synthesis.

    Example:
        ```python
        tts = DeepgramTTS()

        # Synthesize speech
        result = await tts.synthesize(
            text="Hello, thank you for calling!",
            language=Language.ENGLISH,
            voice="aura-2-thalia-en",
        )
        print(f"Generated {len(result.audio_bytes)} bytes of audio")

        # Get available voices
        voices = await tts.get_available_voices(Language.SPANISH)
        for voice in voices:
            print(f"{voice.name} ({voice.gender.value})")
        ```
    """

    # Voice catalog - English voices (Aura-2)
    _ENGLISH_VOICES = [
        Voice(id="aura-2-thalia-en", name="Thalia", language=Language.ENGLISH, gender=VoiceGender.FEMALE),
        Voice(id="aura-2-asteria-en", name="Asteria", language=Language.ENGLISH, gender=VoiceGender.FEMALE),
        Voice(id="aura-2-athena-en", name="Athena", language=Language.ENGLISH, gender=VoiceGender.FEMALE),
        Voice(id="aura-2-luna-en", name="Luna", language=Language.ENGLISH, gender=VoiceGender.FEMALE),
        Voice(id="aura-2-helena-en", name="Helena", language=Language.ENGLISH, gender=VoiceGender.FEMALE),
        Voice(id="aura-2-zeus-en", name="Zeus", language=Language.ENGLISH, gender=VoiceGender.MALE),
        Voice(id="aura-2-orion-en", name="Orion", language=Language.ENGLISH, gender=VoiceGender.MALE),
        Voice(id="aura-2-apollo-en", name="Apollo", language=Language.ENGLISH, gender=VoiceGender.MALE),
        Voice(id="aura-2-arcas-en", name="Arcas", language=Language.ENGLISH, gender=VoiceGender.MALE),
        Voice(id="aura-2-hermes-en", name="Hermes", language=Language.ENGLISH, gender=VoiceGender.MALE),
    ]

    # Voice catalog - Spanish voices (Aura-2)
    _SPANISH_VOICES = [
        Voice(id="aura-2-estrella-es", name="Estrella (MX)", language=Language.SPANISH, gender=VoiceGender.FEMALE),
        Voice(id="aura-2-selena-es", name="Selena (LATAM)", language=Language.SPANISH, gender=VoiceGender.FEMALE),
        Voice(id="aura-2-carina-es", name="Carina (ES)", language=Language.SPANISH, gender=VoiceGender.FEMALE),
        Voice(id="aura-2-diana-es", name="Diana (ES)", language=Language.SPANISH, gender=VoiceGender.FEMALE),
        Voice(id="aura-2-celeste-es", name="Celeste (CO)", language=Language.SPANISH, gender=VoiceGender.FEMALE),
        Voice(id="aura-2-sirio-es", name="Sirio (MX)", language=Language.SPANISH, gender=VoiceGender.MALE),
        Voice(id="aura-2-javier-es", name="Javier (MX)", language=Language.SPANISH, gender=VoiceGender.MALE),
        Voice(id="aura-2-aquila-es", name="Aquila (LATAM)", language=Language.SPANISH, gender=VoiceGender.MALE),
        Voice(id="aura-2-nestor-es", name="Nestor (ES)", language=Language.SPANISH, gender=VoiceGender.MALE),
        Voice(id="aura-2-alvaro-es", name="Alvaro (ES)", language=Language.SPANISH, gender=VoiceGender.MALE),
    ]

    # Format mapping to Deepgram encoding names
    _FORMAT_MAP = {
        AudioFormat.MP3: "mp3",
        AudioFormat.WAV: "linear16",
        AudioFormat.PCM: "linear16",
    }

    # Container format for WAV
    _CONTAINER_MAP = {
        AudioFormat.MP3: None,
        AudioFormat.WAV: "wav",
        AudioFormat.PCM: "none",
    }

    # Sample rates for different formats
    _SAMPLE_RATES = {
        AudioFormat.MP3: 24000,
        AudioFormat.WAV: 24000,
        AudioFormat.PCM: 24000,
    }

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 30.0,
        cache_enabled: bool = True,
        max_cache_size: int = 100,
    ) -> None:
        """Initialize the Deepgram TTS adapter.

        Args:
            api_key: Deepgram API key. Defaults to DEEPGRAM_API_KEY env var.
            timeout: API request timeout in seconds. Defaults to 30.0.
            cache_enabled: Whether to cache synthesized audio for repeated phrases.
                Defaults to True.
            max_cache_size: Maximum number of cached audio results. Defaults to 100.
        """
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY", "")
        self.timeout = timeout
        self.cache_enabled = cache_enabled
        self.max_cache_size = max_cache_size

        # Lazy initialization of client
        self._client: DeepgramClient | None = None

        # In-memory cache for frequently used phrases
        self._cache: dict[str, AudioResult] = {}

        # Default voices
        self.default_english_voice = "aura-2-thalia-en"
        self.default_spanish_voice = "aura-2-estrella-es"

    @property
    def client(self) -> DeepgramClient:
        """Get or create the Deepgram client.

        Returns:
            DeepgramClient instance.

        Raises:
            ValueError: If API key is not configured.
        """
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "Deepgram API key not configured. "
                    "Set DEEPGRAM_API_KEY environment variable."
                )
            self._client = DeepgramClient(api_key=self.api_key)
        return self._client

    def _get_cache_key(
        self,
        text: str,
        voice: str,
        audio_format: AudioFormat,
    ) -> str:
        """Generate a cache key for the given synthesis parameters.

        Args:
            text: The text to synthesize.
            voice: The voice ID.
            audio_format: The audio format.

        Returns:
            A hash string for caching.
        """
        key_string = f"{text}:{voice}:{audio_format.value}"
        return hashlib.md5(key_string.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> AudioResult | None:
        """Get a cached audio result if available.

        Args:
            cache_key: The cache key to look up.

        Returns:
            Cached AudioResult or None if not found.
        """
        if not self.cache_enabled:
            return None
        return self._cache.get(cache_key)

    def _store_in_cache(self, cache_key: str, result: AudioResult) -> None:
        """Store an audio result in the cache.

        Args:
            cache_key: The cache key.
            result: The AudioResult to cache.
        """
        if not self.cache_enabled:
            return

        # Evict oldest entries if cache is full
        if len(self._cache) >= self.max_cache_size:
            # Remove first (oldest) entry
            first_key = next(iter(self._cache))
            del self._cache[first_key]

        self._cache[cache_key] = result

    def _validate_voice(self, voice: str, language: Language) -> str:
        """Validate that the voice is available for the given language.

        Args:
            voice: The voice ID to validate.
            language: The target language.

        Returns:
            The validated voice ID, or a default if invalid.
        """
        voice_list = self._ENGLISH_VOICES if language == Language.ENGLISH else self._SPANISH_VOICES
        voice_ids = [v.id for v in voice_list]

        if voice in voice_ids:
            return voice

        # Fall back to default voice for the language
        return self.default_english_voice if language == Language.ENGLISH else self.default_spanish_voice

    def _estimate_duration(self, text: str) -> float:
        """Estimate audio duration based on text length.

        Uses average speaking rate of ~150 words per minute.

        Args:
            text: The text to estimate duration for.

        Returns:
            Estimated duration in seconds.
        """
        words = len(text.split())
        # Average speaking rate: 150 words per minute = 2.5 words per second
        return max(0.5, words / 2.5)

    async def synthesize(
        self,
        text: str,
        language: Language,
        voice: str,
        audio_format: AudioFormat = AudioFormat.MP3,
    ) -> AudioResult:
        """Synthesize speech from text using Deepgram's Aura-2 API.

        Args:
            text: The text to convert to speech.
            language: The language for synthesis (en or es).
            voice: The voice ID to use for synthesis.
            audio_format: The desired output audio format. Defaults to MP3.

        Returns:
            AudioResult containing the synthesized audio data.

        Raises:
            TTSError: If synthesis fails.
            TTSTimeoutError: If the API request times out.
            TTSInvalidTextError: If the text input is invalid.
            TTSRateLimitError: If rate limits are exceeded.
        """
        # Validate input
        if not text or not text.strip():
            raise TTSInvalidTextError("Text input cannot be empty")

        # Normalize text
        text = text.strip()

        # Validate voice for language
        voice = self._validate_voice(voice, language)

        # Check cache first
        cache_key = self._get_cache_key(text, voice, audio_format)
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result

        # Map audio format to Deepgram encoding
        encoding = self._FORMAT_MAP.get(audio_format, "mp3")
        container = self._CONTAINER_MAP.get(audio_format)
        sample_rate = self._SAMPLE_RATES.get(audio_format, 24000)

        try:
            # Make API request with timeout
            audio_bytes = await asyncio.wait_for(
                self._synthesize_async(text, voice, encoding, container, sample_rate),
                timeout=self.timeout,
            )

            if not audio_bytes:
                raise TTSError("Deepgram returned empty audio data")

            # Estimate duration (Deepgram doesn't always return exact duration)
            duration = self._estimate_duration(text)

            result = AudioResult(
                audio_bytes=audio_bytes,
                format=audio_format,
                duration=duration,
                sample_rate=sample_rate,
            )

            # Cache the result
            self._store_in_cache(cache_key, result)

            return result

        except TimeoutError as e:
            raise TTSTimeoutError(
                f"Deepgram TTS API request timed out after {self.timeout}s"
            ) from e
        except Exception as e:
            error_msg = str(e).lower()
            if "rate" in error_msg and "limit" in error_msg:
                raise TTSRateLimitError(f"Deepgram rate limit exceeded: {e}") from e
            if "413" in error_msg or "too large" in error_msg:
                raise TTSInvalidTextError(f"Text too long for synthesis: {e}") from e
            if "422" in error_msg or "invalid" in error_msg:
                raise TTSInvalidTextError(f"Invalid text for synthesis: {e}") from e
            if isinstance(e, (TTSError, TTSTimeoutError, TTSInvalidTextError, TTSRateLimitError)):
                raise
            raise TTSError(f"Deepgram TTS synthesis failed: {e}") from e

    async def _synthesize_async(
        self,
        text: str,
        model: str,
        encoding: str,
        container: str | None,
        sample_rate: int,
    ) -> bytes:
        """Make async TTS request to Deepgram.

        Args:
            text: The text to synthesize.
            model: The voice model to use.
            encoding: The audio encoding format.
            container: The container format (wav, ogg, or none).
            sample_rate: The sample rate in Hz.

        Returns:
            The audio bytes.
        """
        # Use the sync-to-async approach since Deepgram SDK uses sync methods
        return await asyncio.to_thread(
            self._synthesize_sync, text, model, encoding, container, sample_rate
        )

    def _synthesize_sync(
        self,
        text: str,
        model: str,
        encoding: str,
        container: str | None,
        sample_rate: int,
    ) -> bytes:
        """Make synchronous TTS request to Deepgram.

        Args:
            text: The text to synthesize.
            model: The voice model to use.
            encoding: The audio encoding format.
            container: The container format (wav, ogg, or none).
            sample_rate: The sample rate in Hz.

        Returns:
            The audio bytes.
        """
        # Build kwargs for the API call
        kwargs: dict[str, str | float | None] = {
            "text": text,
            "model": model,
            "encoding": encoding,
            "sample_rate": float(sample_rate),
        }

        if container:
            kwargs["container"] = container

        # Call the Deepgram TTS API - returns an iterator of bytes
        audio_iterator = self.client.speak.v1.audio.generate(**kwargs)  # type: ignore[arg-type]

        # Collect all audio chunks
        audio_buffer = BytesIO()
        for chunk in audio_iterator:
            audio_buffer.write(chunk)

        return audio_buffer.getvalue()

    async def get_available_voices(self, language: Language) -> list[Voice]:
        """Get available voices for a given language.

        Args:
            language: The language to filter voices by.

        Returns:
            List of Voice objects available for the specified language.

        Raises:
            TTSError: If voices cannot be retrieved.
        """
        if language == Language.ENGLISH:
            return list(self._ENGLISH_VOICES)
        elif language == Language.SPANISH:
            return list(self._SPANISH_VOICES)
        else:
            raise TTSError(f"Unsupported language: {language}")

    async def get_default_voice(self, language: Language) -> Voice:
        """Get the default voice for a given language.

        Args:
            language: The target language.

        Returns:
            The default Voice for the language.

        Raises:
            TTSError: If language is not supported.
        """
        voices = await self.get_available_voices(language)
        if not voices:
            raise TTSError(f"No voices available for language: {language}")
        return voices[0]

    async def get_voices_by_gender(
        self,
        language: Language,
        gender: VoiceGender,
    ) -> list[Voice]:
        """Get voices filtered by language and gender.

        Args:
            language: The target language.
            gender: The desired voice gender.

        Returns:
            List of Voice objects matching the criteria.
        """
        voices = await self.get_available_voices(language)
        return [v for v in voices if v.gender == gender]

    def clear_cache(self) -> None:
        """Clear the audio cache."""
        self._cache.clear()
