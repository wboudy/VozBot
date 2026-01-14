"""Tests for the TTSProvider abstract base class."""

import asyncio

import pytest

from vozbot.speech.tts.base import (
    AudioFormat,
    AudioResult,
    Language,
    TTSProvider,
    Voice,
    VoiceGender,
)


class TestAudioFormat:
    """Tests for the AudioFormat enum."""

    def test_all_format_values_exist(self) -> None:
        """Verify all expected audio format values are defined."""
        expected_formats = ["mp3", "wav", "pcm"]

        for format_value in expected_formats:
            assert AudioFormat(format_value) is not None

    def test_format_value_access(self) -> None:
        """Test accessing enum values."""
        assert AudioFormat.MP3.value == "mp3"
        assert AudioFormat.WAV.value == "wav"
        assert AudioFormat.PCM.value == "pcm"


class TestVoiceGender:
    """Tests for the VoiceGender enum."""

    def test_all_gender_values_exist(self) -> None:
        """Verify all expected voice gender values are defined."""
        expected_genders = ["male", "female", "neutral"]

        for gender_value in expected_genders:
            assert VoiceGender(gender_value) is not None

    def test_gender_value_access(self) -> None:
        """Test accessing enum values."""
        assert VoiceGender.MALE.value == "male"
        assert VoiceGender.FEMALE.value == "female"
        assert VoiceGender.NEUTRAL.value == "neutral"


class TestLanguage:
    """Tests for the Language enum."""

    def test_supported_languages_exist(self) -> None:
        """Verify English and Spanish are supported."""
        assert Language.ENGLISH.value == "en"
        assert Language.SPANISH.value == "es"

    def test_language_from_value(self) -> None:
        """Test creating Language from string value."""
        assert Language("en") == Language.ENGLISH
        assert Language("es") == Language.SPANISH


class TestVoice:
    """Tests for the Voice dataclass."""

    def test_create_voice(self) -> None:
        """Test creating a Voice instance with all fields."""
        voice = Voice(
            id="voice_123",
            name="Asteria",
            language=Language.ENGLISH,
            gender=VoiceGender.FEMALE,
        )

        assert voice.id == "voice_123"
        assert voice.name == "Asteria"
        assert voice.language == Language.ENGLISH
        assert voice.gender == VoiceGender.FEMALE

    def test_voice_equality(self) -> None:
        """Test that two Voice instances with same values are equal."""
        voice1 = Voice(
            id="voice_123",
            name="Asteria",
            language=Language.ENGLISH,
            gender=VoiceGender.FEMALE,
        )
        voice2 = Voice(
            id="voice_123",
            name="Asteria",
            language=Language.ENGLISH,
            gender=VoiceGender.FEMALE,
        )

        assert voice1 == voice2


class TestAudioResult:
    """Tests for the AudioResult dataclass."""

    def test_create_audio_result(self) -> None:
        """Test creating an AudioResult instance with all fields."""
        audio_data = b"fake audio data"
        result = AudioResult(
            audio_bytes=audio_data,
            format=AudioFormat.MP3,
            duration=5.5,
            sample_rate=22050,
        )

        assert result.audio_bytes == audio_data
        assert result.format == AudioFormat.MP3
        assert result.duration == 5.5
        assert result.sample_rate == 22050

    def test_audio_result_equality(self) -> None:
        """Test that two AudioResult instances with same values are equal."""
        audio_data = b"fake audio data"
        result1 = AudioResult(
            audio_bytes=audio_data,
            format=AudioFormat.WAV,
            duration=3.0,
            sample_rate=44100,
        )
        result2 = AudioResult(
            audio_bytes=audio_data,
            format=AudioFormat.WAV,
            duration=3.0,
            sample_rate=44100,
        )

        assert result1 == result2

    def test_audio_result_with_different_formats(self) -> None:
        """Test AudioResult can be created with all supported formats."""
        audio_data = b"audio"

        for audio_format in AudioFormat:
            result = AudioResult(
                audio_bytes=audio_data,
                format=audio_format,
                duration=1.0,
                sample_rate=16000,
            )
            assert result.format == audio_format


class TestTTSProviderABC:
    """Tests for the TTSProvider abstract base class."""

    def test_cannot_instantiate_directly(self) -> None:
        """Verify that TTSProvider cannot be instantiated directly."""
        with pytest.raises(TypeError) as exc_info:
            TTSProvider()  # type: ignore[abstract]

        # Check that the error mentions abstract methods
        error_message = str(exc_info.value)
        assert "abstract" in error_message.lower() or "instantiate" in error_message.lower()

    def test_subclass_must_implement_all_methods(self) -> None:
        """Verify that a subclass missing methods cannot be instantiated."""

        class IncompleteTTSProvider(TTSProvider):
            """Incomplete implementation missing required methods."""

            async def synthesize(
                self,
                text: str,
                language: Language,
                voice: str,
                audio_format: AudioFormat = AudioFormat.MP3,
            ) -> AudioResult:
                return AudioResult(
                    audio_bytes=b"",
                    format=audio_format,
                    duration=0.0,
                    sample_rate=22050,
                )

            # Missing: get_available_voices

        with pytest.raises(TypeError) as exc_info:
            IncompleteTTSProvider()  # type: ignore[abstract]

        error_message = str(exc_info.value)
        assert "abstract" in error_message.lower()

    def test_complete_subclass_can_be_instantiated(self) -> None:
        """Verify that a complete implementation can be instantiated."""

        class CompleteTTSProvider(TTSProvider):
            """Complete implementation of all required methods."""

            async def synthesize(
                self,
                text: str,
                language: Language,
                voice: str,
                audio_format: AudioFormat = AudioFormat.MP3,
            ) -> AudioResult:
                return AudioResult(
                    audio_bytes=b"audio data",
                    format=audio_format,
                    duration=1.0,
                    sample_rate=22050,
                )

            async def get_available_voices(self, language: Language) -> list[Voice]:
                return [
                    Voice(
                        id="voice_1",
                        name="Test Voice",
                        language=language,
                        gender=VoiceGender.NEUTRAL,
                    )
                ]

        # Should not raise
        provider = CompleteTTSProvider()
        assert isinstance(provider, TTSProvider)


class MockTTSProvider(TTSProvider):
    """Mock implementation for testing async methods."""

    def __init__(self) -> None:
        self.synthesize_calls: list[tuple[str, Language, str, AudioFormat]] = []
        self.get_voices_calls: list[Language] = []

    async def synthesize(
        self,
        text: str,
        language: Language,
        voice: str,
        audio_format: AudioFormat = AudioFormat.MP3,
    ) -> AudioResult:
        self.synthesize_calls.append((text, language, voice, audio_format))
        # Return fake audio data
        return AudioResult(
            audio_bytes=text.encode("utf-8"),
            format=audio_format,
            duration=len(text) * 0.1,  # Fake duration based on text length
            sample_rate=22050,
        )

    async def get_available_voices(self, language: Language) -> list[Voice]:
        self.get_voices_calls.append(language)

        if language == Language.ENGLISH:
            return [
                Voice(
                    id="aura-asteria-en",
                    name="Asteria",
                    language=Language.ENGLISH,
                    gender=VoiceGender.FEMALE,
                ),
                Voice(
                    id="aura-orion-en",
                    name="Orion",
                    language=Language.ENGLISH,
                    gender=VoiceGender.MALE,
                ),
            ]
        elif language == Language.SPANISH:
            return [
                Voice(
                    id="aura-asteria-es",
                    name="Asteria (Spanish)",
                    language=Language.SPANISH,
                    gender=VoiceGender.FEMALE,
                ),
            ]
        return []


class TestTTSProviderMethods:
    """Tests for TTSProvider method signatures and behavior."""

    @pytest.fixture
    def mock_provider(self) -> MockTTSProvider:
        """Create a mock provider for testing method signatures."""
        return MockTTSProvider()

    def test_synthesize_returns_audio_result(self, mock_provider: MockTTSProvider) -> None:
        """Test synthesize method returns AudioResult."""
        result = asyncio.run(
            mock_provider.synthesize(
                text="Hello, world!",
                language=Language.ENGLISH,
                voice="aura-asteria-en",
            )
        )

        assert isinstance(result, AudioResult)
        assert isinstance(result.audio_bytes, bytes)
        assert isinstance(result.format, AudioFormat)
        assert isinstance(result.duration, float)
        assert isinstance(result.sample_rate, int)

    def test_synthesize_with_different_formats(self, mock_provider: MockTTSProvider) -> None:
        """Test synthesize method accepts different audio formats."""
        for audio_format in AudioFormat:
            result = asyncio.run(
                mock_provider.synthesize(
                    text="Test",
                    language=Language.ENGLISH,
                    voice="test-voice",
                    audio_format=audio_format,
                )
            )
            assert result.format == audio_format

    def test_synthesize_with_spanish(self, mock_provider: MockTTSProvider) -> None:
        """Test synthesize method works with Spanish language."""
        result = asyncio.run(
            mock_provider.synthesize(
                text="Hola, mundo!",
                language=Language.SPANISH,
                voice="aura-asteria-es",
            )
        )

        assert isinstance(result, AudioResult)
        assert (
            "Hola, mundo!",
            Language.SPANISH,
            "aura-asteria-es",
            AudioFormat.MP3,
        ) in mock_provider.synthesize_calls

    def test_get_available_voices_returns_list(self, mock_provider: MockTTSProvider) -> None:
        """Test get_available_voices returns list of Voice objects."""
        voices = asyncio.run(mock_provider.get_available_voices(Language.ENGLISH))

        assert isinstance(voices, list)
        assert len(voices) > 0
        assert all(isinstance(v, Voice) for v in voices)

    def test_get_available_voices_filters_by_language(
        self, mock_provider: MockTTSProvider
    ) -> None:
        """Test get_available_voices returns voices for specified language."""
        english_voices = asyncio.run(mock_provider.get_available_voices(Language.ENGLISH))
        spanish_voices = asyncio.run(mock_provider.get_available_voices(Language.SPANISH))

        assert all(v.language == Language.ENGLISH for v in english_voices)
        assert all(v.language == Language.SPANISH for v in spanish_voices)

    def test_synthesize_default_format_is_mp3(self, mock_provider: MockTTSProvider) -> None:
        """Test that default audio format is MP3."""
        result = asyncio.run(
            mock_provider.synthesize(
                text="Test",
                language=Language.ENGLISH,
                voice="test-voice",
                # Not providing audio_format, should default to MP3
            )
        )

        assert result.format == AudioFormat.MP3
        # Verify the call was recorded with MP3 format
        assert mock_provider.synthesize_calls[-1][3] == AudioFormat.MP3
