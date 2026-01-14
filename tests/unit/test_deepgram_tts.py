"""Tests for the DeepgramTTS adapter."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

import pytest

from vozbot.speech.tts import (
    AudioFormat,
    AudioResult,
    DeepgramTTS,
    Language,
    TTSError,
    TTSInvalidTextError,
    TTSRateLimitError,
    TTSTimeoutError,
    Voice,
    VoiceGender,
)


class TestDeepgramTTSInit:
    """Tests for DeepgramTTS initialization."""

    def test_init_with_default_values(self) -> None:
        """Test initialization with default values."""
        tts = DeepgramTTS(api_key="test-key")

        assert tts.api_key == "test-key"
        assert tts.timeout == 30.0
        assert tts.cache_enabled is True
        assert tts.max_cache_size == 100
        assert tts.default_english_voice == "aura-2-thalia-en"
        assert tts.default_spanish_voice == "aura-2-estrella-es"

    def test_init_with_custom_values(self) -> None:
        """Test initialization with custom values."""
        tts = DeepgramTTS(
            api_key="custom-key",
            timeout=60.0,
            cache_enabled=False,
            max_cache_size=50,
        )

        assert tts.api_key == "custom-key"
        assert tts.timeout == 60.0
        assert tts.cache_enabled is False
        assert tts.max_cache_size == 50

    def test_init_from_env_var(self) -> None:
        """Test initialization reads API key from environment."""
        with patch.dict("os.environ", {"DEEPGRAM_API_KEY": "env-key"}):
            tts = DeepgramTTS()
            assert tts.api_key == "env-key"

    def test_client_raises_without_api_key(self) -> None:
        """Test that accessing client without API key raises ValueError."""
        tts = DeepgramTTS(api_key="")

        with pytest.raises(ValueError) as exc_info:
            _ = tts.client

        assert "DEEPGRAM_API_KEY" in str(exc_info.value)


class TestDeepgramTTSSynthesize:
    """Tests for the synthesize method."""

    @pytest.fixture
    def tts(self) -> DeepgramTTS:
        """Create a DeepgramTTS instance for testing."""
        return DeepgramTTS(api_key="test-key", cache_enabled=False)

    @pytest.fixture
    def mock_audio_bytes(self) -> bytes:
        """Create mock audio bytes."""
        return b"fake mp3 audio data for testing purposes"

    def test_synthesize_empty_text_raises_error(self, tts: DeepgramTTS) -> None:
        """Test that empty text raises TTSInvalidTextError."""
        with pytest.raises(TTSInvalidTextError) as exc_info:
            asyncio.run(tts.synthesize("", Language.ENGLISH, "aura-2-thalia-en"))

        assert "empty" in str(exc_info.value).lower()

    def test_synthesize_whitespace_only_raises_error(self, tts: DeepgramTTS) -> None:
        """Test that whitespace-only text raises TTSInvalidTextError."""
        with pytest.raises(TTSInvalidTextError):
            asyncio.run(tts.synthesize("   ", Language.ENGLISH, "aura-2-thalia-en"))

    def test_synthesize_returns_audio_result(
        self, tts: DeepgramTTS, mock_audio_bytes: bytes
    ) -> None:
        """Test that synthesize returns an AudioResult."""
        with patch.object(tts, "_synthesize_sync", return_value=mock_audio_bytes):
            result = asyncio.run(
                tts.synthesize(
                    "Hello, world!",
                    Language.ENGLISH,
                    "aura-2-thalia-en",
                )
            )

            assert isinstance(result, AudioResult)
            assert isinstance(result.audio_bytes, bytes)
            assert len(result.audio_bytes) > 0
            assert result.format == AudioFormat.MP3
            assert result.sample_rate == 24000
            assert result.duration > 0

    def test_synthesize_with_wav_format(
        self, tts: DeepgramTTS, mock_audio_bytes: bytes
    ) -> None:
        """Test synthesize with WAV audio format."""
        with patch.object(tts, "_synthesize_sync", return_value=mock_audio_bytes):
            result = asyncio.run(
                tts.synthesize(
                    "Test audio",
                    Language.ENGLISH,
                    "aura-2-thalia-en",
                    audio_format=AudioFormat.WAV,
                )
            )

            assert result.format == AudioFormat.WAV

    def test_synthesize_with_pcm_format(
        self, tts: DeepgramTTS, mock_audio_bytes: bytes
    ) -> None:
        """Test synthesize with PCM audio format."""
        with patch.object(tts, "_synthesize_sync", return_value=mock_audio_bytes):
            result = asyncio.run(
                tts.synthesize(
                    "Test audio",
                    Language.ENGLISH,
                    "aura-2-thalia-en",
                    audio_format=AudioFormat.PCM,
                )
            )

            assert result.format == AudioFormat.PCM

    def test_synthesize_spanish_text(
        self, tts: DeepgramTTS, mock_audio_bytes: bytes
    ) -> None:
        """Test synthesize with Spanish language."""
        with patch.object(tts, "_synthesize_sync", return_value=mock_audio_bytes):
            result = asyncio.run(
                tts.synthesize(
                    "Hola, gracias por llamar!",
                    Language.SPANISH,
                    "aura-2-estrella-es",
                )
            )

            assert isinstance(result, AudioResult)
            assert len(result.audio_bytes) > 0

    def test_synthesize_uses_default_voice_for_invalid_voice(
        self, tts: DeepgramTTS, mock_audio_bytes: bytes
    ) -> None:
        """Test that invalid voice falls back to default."""
        with patch.object(tts, "_synthesize_sync", return_value=mock_audio_bytes) as mock:
            asyncio.run(
                tts.synthesize(
                    "Hello",
                    Language.ENGLISH,
                    "invalid-voice-id",
                )
            )

            # Verify the call was made (voice validation happens internally)
            mock.assert_called_once()
            # Check that the default voice was used
            call_args = mock.call_args
            assert call_args[0][1] == "aura-2-thalia-en"  # default English voice

    def test_synthesize_timeout_raises_error(self, tts: DeepgramTTS) -> None:
        """Test that timeout raises TTSTimeoutError."""
        tts.timeout = 0.001  # Very short timeout

        def slow_synthesize(*args, **kwargs):
            """Blocking sleep to simulate slow API call."""
            time.sleep(1)
            return b"audio"

        with patch.object(tts, "_synthesize_sync", side_effect=slow_synthesize):
            with pytest.raises(TTSTimeoutError) as exc_info:
                asyncio.run(
                    tts.synthesize("Hello", Language.ENGLISH, "aura-2-thalia-en")
                )

            assert "timed out" in str(exc_info.value).lower()

    def test_synthesize_rate_limit_raises_error(self, tts: DeepgramTTS) -> None:
        """Test that rate limit error is properly raised."""
        with (
            patch.object(
                tts,
                "_synthesize_sync",
                side_effect=Exception("Rate limit exceeded"),
            ),
            pytest.raises(TTSRateLimitError),
        ):
            asyncio.run(
                tts.synthesize("Hello", Language.ENGLISH, "aura-2-thalia-en")
            )

    def test_synthesize_empty_response_raises_error(self, tts: DeepgramTTS) -> None:
        """Test that empty response raises TTSError."""
        with patch.object(tts, "_synthesize_sync", return_value=b""):
            with pytest.raises(TTSError) as exc_info:
                asyncio.run(
                    tts.synthesize("Hello", Language.ENGLISH, "aura-2-thalia-en")
                )

            assert "empty" in str(exc_info.value).lower()


class TestDeepgramTTSCaching:
    """Tests for the caching functionality."""

    @pytest.fixture
    def tts(self) -> DeepgramTTS:
        """Create a DeepgramTTS instance with caching enabled."""
        return DeepgramTTS(api_key="test-key", cache_enabled=True, max_cache_size=3)

    @pytest.fixture
    def mock_audio_bytes(self) -> bytes:
        """Create mock audio bytes."""
        return b"fake audio data"

    def test_cache_hit_returns_cached_result(
        self, tts: DeepgramTTS, mock_audio_bytes: bytes
    ) -> None:
        """Test that repeated calls return cached results."""
        with patch.object(tts, "_synthesize_sync", return_value=mock_audio_bytes) as mock:
            # First call - should hit API
            result1 = asyncio.run(
                tts.synthesize("Hello", Language.ENGLISH, "aura-2-thalia-en")
            )

            # Second call with same params - should use cache
            result2 = asyncio.run(
                tts.synthesize("Hello", Language.ENGLISH, "aura-2-thalia-en")
            )

            # API should only be called once
            mock.assert_called_once()
            assert result1.audio_bytes == result2.audio_bytes

    def test_different_text_not_cached(
        self, tts: DeepgramTTS, mock_audio_bytes: bytes
    ) -> None:
        """Test that different text results in new API calls."""
        with patch.object(tts, "_synthesize_sync", return_value=mock_audio_bytes) as mock:
            asyncio.run(tts.synthesize("Hello", Language.ENGLISH, "aura-2-thalia-en"))
            asyncio.run(tts.synthesize("Goodbye", Language.ENGLISH, "aura-2-thalia-en"))

            # Should be called twice for different text
            assert mock.call_count == 2

    def test_different_voice_not_cached(
        self, tts: DeepgramTTS, mock_audio_bytes: bytes
    ) -> None:
        """Test that different voice results in new API calls."""
        with patch.object(tts, "_synthesize_sync", return_value=mock_audio_bytes) as mock:
            asyncio.run(tts.synthesize("Hello", Language.ENGLISH, "aura-2-thalia-en"))
            asyncio.run(tts.synthesize("Hello", Language.ENGLISH, "aura-2-zeus-en"))

            assert mock.call_count == 2

    def test_cache_eviction_when_full(
        self, tts: DeepgramTTS, mock_audio_bytes: bytes
    ) -> None:
        """Test that oldest entries are evicted when cache is full."""
        with patch.object(tts, "_synthesize_sync", return_value=mock_audio_bytes):
            # Fill the cache (max_cache_size=3)
            asyncio.run(tts.synthesize("Text1", Language.ENGLISH, "aura-2-thalia-en"))
            asyncio.run(tts.synthesize("Text2", Language.ENGLISH, "aura-2-thalia-en"))
            asyncio.run(tts.synthesize("Text3", Language.ENGLISH, "aura-2-thalia-en"))

            # Add one more (should evict Text1)
            asyncio.run(tts.synthesize("Text4", Language.ENGLISH, "aura-2-thalia-en"))

            assert len(tts._cache) == 3

    def test_clear_cache(self, tts: DeepgramTTS, mock_audio_bytes: bytes) -> None:
        """Test clearing the cache."""
        with patch.object(tts, "_synthesize_sync", return_value=mock_audio_bytes):
            asyncio.run(tts.synthesize("Hello", Language.ENGLISH, "aura-2-thalia-en"))
            assert len(tts._cache) == 1

            tts.clear_cache()
            assert len(tts._cache) == 0

    def test_cache_disabled(self, mock_audio_bytes: bytes) -> None:
        """Test that caching can be disabled."""
        tts = DeepgramTTS(api_key="test-key", cache_enabled=False)

        with patch.object(tts, "_synthesize_sync", return_value=mock_audio_bytes) as mock:
            asyncio.run(tts.synthesize("Hello", Language.ENGLISH, "aura-2-thalia-en"))
            asyncio.run(tts.synthesize("Hello", Language.ENGLISH, "aura-2-thalia-en"))

            # Should be called twice when caching is disabled
            assert mock.call_count == 2


class TestDeepgramTTSVoices:
    """Tests for voice-related functionality."""

    @pytest.fixture
    def tts(self) -> DeepgramTTS:
        """Create a DeepgramTTS instance for testing."""
        return DeepgramTTS(api_key="test-key")

    def test_get_available_voices_english(self, tts: DeepgramTTS) -> None:
        """Test getting available English voices."""
        voices = asyncio.run(tts.get_available_voices(Language.ENGLISH))

        assert isinstance(voices, list)
        assert len(voices) > 0
        assert all(isinstance(v, Voice) for v in voices)
        assert all(v.language == Language.ENGLISH for v in voices)

    def test_get_available_voices_spanish(self, tts: DeepgramTTS) -> None:
        """Test getting available Spanish voices."""
        voices = asyncio.run(tts.get_available_voices(Language.SPANISH))

        assert isinstance(voices, list)
        assert len(voices) > 0
        assert all(isinstance(v, Voice) for v in voices)
        assert all(v.language == Language.SPANISH for v in voices)

    def test_english_voices_have_both_genders(self, tts: DeepgramTTS) -> None:
        """Test that English voices include both male and female options."""
        voices = asyncio.run(tts.get_available_voices(Language.ENGLISH))

        male_voices = [v for v in voices if v.gender == VoiceGender.MALE]
        female_voices = [v for v in voices if v.gender == VoiceGender.FEMALE]

        assert len(male_voices) > 0, "Should have at least one male English voice"
        assert len(female_voices) > 0, "Should have at least one female English voice"

    def test_spanish_voices_have_both_genders(self, tts: DeepgramTTS) -> None:
        """Test that Spanish voices include both male and female options."""
        voices = asyncio.run(tts.get_available_voices(Language.SPANISH))

        male_voices = [v for v in voices if v.gender == VoiceGender.MALE]
        female_voices = [v for v in voices if v.gender == VoiceGender.FEMALE]

        assert len(male_voices) > 0, "Should have at least one male Spanish voice"
        assert len(female_voices) > 0, "Should have at least one female Spanish voice"

    def test_get_default_voice_english(self, tts: DeepgramTTS) -> None:
        """Test getting default English voice."""
        voice = asyncio.run(tts.get_default_voice(Language.ENGLISH))

        assert isinstance(voice, Voice)
        assert voice.language == Language.ENGLISH

    def test_get_default_voice_spanish(self, tts: DeepgramTTS) -> None:
        """Test getting default Spanish voice."""
        voice = asyncio.run(tts.get_default_voice(Language.SPANISH))

        assert isinstance(voice, Voice)
        assert voice.language == Language.SPANISH

    def test_get_voices_by_gender_female(self, tts: DeepgramTTS) -> None:
        """Test filtering voices by female gender."""
        voices = asyncio.run(
            tts.get_voices_by_gender(Language.ENGLISH, VoiceGender.FEMALE)
        )

        assert len(voices) > 0
        assert all(v.gender == VoiceGender.FEMALE for v in voices)

    def test_get_voices_by_gender_male(self, tts: DeepgramTTS) -> None:
        """Test filtering voices by male gender."""
        voices = asyncio.run(
            tts.get_voices_by_gender(Language.SPANISH, VoiceGender.MALE)
        )

        assert len(voices) > 0
        assert all(v.gender == VoiceGender.MALE for v in voices)

    def test_voice_ids_are_valid_format(self, tts: DeepgramTTS) -> None:
        """Test that all voice IDs follow expected format."""
        english_voices = asyncio.run(tts.get_available_voices(Language.ENGLISH))
        spanish_voices = asyncio.run(tts.get_available_voices(Language.SPANISH))

        for voice in english_voices:
            assert voice.id.startswith("aura-2-"), f"English voice {voice.id} has unexpected format"
            assert voice.id.endswith("-en"), f"English voice {voice.id} should end with -en"

        for voice in spanish_voices:
            assert voice.id.startswith("aura-2-"), f"Spanish voice {voice.id} has unexpected format"
            assert voice.id.endswith("-es"), f"Spanish voice {voice.id} should end with -es"


class TestDeepgramTTSIntegration:
    """Tests for TTSProvider interface compliance."""

    @pytest.fixture
    def tts(self) -> DeepgramTTS:
        """Create a DeepgramTTS instance for testing."""
        return DeepgramTTS(api_key="test-key")

    def test_is_tts_provider(self, tts: DeepgramTTS) -> None:
        """Test that DeepgramTTS is a valid TTSProvider."""
        from vozbot.speech.tts.base import TTSProvider

        assert isinstance(tts, TTSProvider)

    def test_synthesize_signature_matches_interface(self, tts: DeepgramTTS) -> None:
        """Test that synthesize method signature matches TTSProvider."""
        import inspect

        from vozbot.speech.tts.base import TTSProvider

        # Get the method signatures
        tts_sig = inspect.signature(TTSProvider.synthesize)
        impl_sig = inspect.signature(DeepgramTTS.synthesize)

        # Verify parameter names match (excluding self)
        tts_params = list(tts_sig.parameters.keys())[1:]  # Skip 'self'
        impl_params = list(impl_sig.parameters.keys())[1:]  # Skip 'self'

        assert tts_params == impl_params

    def test_get_available_voices_signature_matches_interface(
        self, tts: DeepgramTTS
    ) -> None:
        """Test that get_available_voices method signature matches TTSProvider."""
        import inspect

        from vozbot.speech.tts.base import TTSProvider

        tts_sig = inspect.signature(TTSProvider.get_available_voices)
        impl_sig = inspect.signature(DeepgramTTS.get_available_voices)

        tts_params = list(tts_sig.parameters.keys())[1:]
        impl_params = list(impl_sig.parameters.keys())[1:]

        assert tts_params == impl_params


class TestDeepgramTTSEdgeCases:
    """Tests for edge cases and special scenarios."""

    @pytest.fixture
    def tts(self) -> DeepgramTTS:
        """Create a DeepgramTTS instance for testing."""
        return DeepgramTTS(api_key="test-key", cache_enabled=False)

    @pytest.fixture
    def mock_audio_bytes(self) -> bytes:
        """Create mock audio bytes."""
        return b"fake audio data"

    def test_long_text_synthesis(
        self, tts: DeepgramTTS, mock_audio_bytes: bytes
    ) -> None:
        """Test synthesis of long text."""
        long_text = "This is a very long sentence. " * 100

        with patch.object(tts, "_synthesize_sync", return_value=mock_audio_bytes):
            result = asyncio.run(
                tts.synthesize(long_text, Language.ENGLISH, "aura-2-thalia-en")
            )

            assert isinstance(result, AudioResult)
            # Duration should be longer for longer text
            assert result.duration > 10  # At least 10 seconds for 100 sentences

    def test_special_characters_in_text(
        self, tts: DeepgramTTS, mock_audio_bytes: bytes
    ) -> None:
        """Test synthesis with special characters."""
        special_text = "Hello! How are you? That's $100.00, isn't it?"

        with patch.object(tts, "_synthesize_sync", return_value=mock_audio_bytes):
            result = asyncio.run(
                tts.synthesize(special_text, Language.ENGLISH, "aura-2-thalia-en")
            )

            assert isinstance(result, AudioResult)

    def test_unicode_spanish_text(
        self, tts: DeepgramTTS, mock_audio_bytes: bytes
    ) -> None:
        """Test synthesis with Spanish unicode characters."""
        spanish_text = "Buenos dias! Como esta usted? El nino tiene tres anos."

        with patch.object(tts, "_synthesize_sync", return_value=mock_audio_bytes):
            result = asyncio.run(
                tts.synthesize(spanish_text, Language.SPANISH, "aura-2-estrella-es")
            )

            assert isinstance(result, AudioResult)

    def test_estimate_duration(self, tts: DeepgramTTS) -> None:
        """Test duration estimation logic."""
        # Short text
        short_duration = tts._estimate_duration("Hello world")
        assert short_duration >= 0.5  # Minimum duration

        # Longer text
        long_duration = tts._estimate_duration(
            "This is a much longer sentence with many more words"
        )
        assert long_duration > short_duration

    def test_cache_key_generation(self, tts: DeepgramTTS) -> None:
        """Test cache key generation is consistent."""
        key1 = tts._get_cache_key("Hello", "voice1", AudioFormat.MP3)
        key2 = tts._get_cache_key("Hello", "voice1", AudioFormat.MP3)
        key3 = tts._get_cache_key("Hello", "voice2", AudioFormat.MP3)

        assert key1 == key2  # Same inputs = same key
        assert key1 != key3  # Different voice = different key
