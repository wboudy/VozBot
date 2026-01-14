"""Deepgram implementation of the STTProvider interface.

Provides speech-to-text transcription using the Deepgram API for both
batch and streaming audio processing.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from deepgram import AsyncDeepgramClient
from deepgram.core.api_error import ApiError

from vozbot.speech.stt.base import STTProvider, TranscriptChunk, TranscriptResult

if TYPE_CHECKING:
    from deepgram.types.listen_v1response import ListenV1Response


class STTError(Exception):
    """Base exception for STT-related errors."""

    pass


class STTTimeoutError(STTError):
    """Raised when STT API times out."""

    pass


class STTInvalidAudioError(STTError):
    """Raised when audio data is invalid or unsupported."""

    pass


class STTRateLimitError(STTError):
    """Raised when API rate limits are exceeded."""

    pass


class DeepgramSTT(STTProvider):
    """Deepgram implementation of the STTProvider interface.

    Uses the Deepgram API for accurate speech-to-text transcription
    with support for both batch and real-time streaming modes.

    Environment Variables:
        DEEPGRAM_API_KEY: Deepgram API key for authentication

    Attributes:
        confidence_threshold: Minimum confidence score to accept transcription.
            Defaults to 0.8.

    Example:
        ```python
        stt = DeepgramSTT()

        # Batch transcription
        result = await stt.transcribe(audio_bytes, language="en")
        print(f"Transcribed: {result.text} (confidence: {result.confidence})")

        # Streaming transcription
        async for chunk in stt.transcribe_stream(audio_stream, "es"):
            if chunk.is_final:
                print(f"Final: {chunk.partial_text}")
        ```
    """

    # Supported language codes for Deepgram
    _LANGUAGE_MAP = {
        "en": "en-US",
        "es": "es",
    }

    def __init__(
        self,
        api_key: str | None = None,
        confidence_threshold: float = 0.8,
        timeout: float = 30.0,
    ) -> None:
        """Initialize the Deepgram STT adapter.

        Args:
            api_key: Deepgram API key. Defaults to DEEPGRAM_API_KEY env var.
            confidence_threshold: Minimum confidence score (0.0-1.0) to accept.
                Defaults to 0.8.
            timeout: API request timeout in seconds. Defaults to 30.0.

        Raises:
            ValueError: If confidence_threshold is not between 0 and 1.
        """
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be between 0.0 and 1.0")

        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY", "")
        self.confidence_threshold = confidence_threshold
        self.timeout = timeout

        # Lazy initialization of client
        self._client: AsyncDeepgramClient | None = None

    @property
    def client(self) -> AsyncDeepgramClient:
        """Get or create the Deepgram client.

        Returns:
            AsyncDeepgramClient instance.

        Raises:
            ValueError: If API key is not configured.
        """
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "Deepgram API key not configured. "
                    "Set DEEPGRAM_API_KEY environment variable."
                )
            self._client = AsyncDeepgramClient(api_key=self.api_key)
        return self._client

    def _validate_language(self, language: str) -> str:
        """Validate and map language code to Deepgram format.

        Args:
            language: Language code ("en" or "es").

        Returns:
            Deepgram-compatible language code.

        Raises:
            ValueError: If language is not supported.
        """
        if language not in self._LANGUAGE_MAP:
            supported = ", ".join(self._LANGUAGE_MAP.keys())
            raise ValueError(
                f"Unsupported language: {language}. "
                f"Supported languages: {supported}"
            )
        return self._LANGUAGE_MAP[language]

    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str = "en",
    ) -> TranscriptResult:
        """Transcribe audio data to text using Deepgram's batch API.

        Args:
            audio_bytes: Raw audio data as bytes (supports WAV, MP3, FLAC, etc.).
            language: Language code for transcription ("en" or "es").
                Defaults to "en".

        Returns:
            TranscriptResult containing the transcribed text, confidence score,
            language, and audio duration.

        Raises:
            STTError: If transcription fails.
            STTTimeoutError: If the API request times out.
            STTInvalidAudioError: If the audio data is invalid.
            STTRateLimitError: If rate limits are exceeded.
            ValueError: If an unsupported language is specified.
        """
        dg_language = self._validate_language(language)

        if not audio_bytes:
            raise STTInvalidAudioError("Audio data cannot be empty")

        try:
            response: ListenV1Response = await asyncio.wait_for(
                self.client.listen.v1.media.transcribe_file(
                    request=audio_bytes,
                    model="nova-2",
                    language=dg_language,
                    smart_format=True,
                    punctuate=True,
                ),
                timeout=self.timeout,
            )

            # Extract results from response
            results = response.results
            if results is None or not results.channels:
                return TranscriptResult(
                    text="",
                    confidence=0.0,
                    language=language,
                    duration=0.0,
                )

            channel = results.channels[0]
            if not channel.alternatives:
                return TranscriptResult(
                    text="",
                    confidence=0.0,
                    language=language,
                    duration=0.0,
                )

            alternative = channel.alternatives[0]
            transcript = alternative.transcript or ""
            confidence = alternative.confidence or 0.0

            # Get duration from metadata
            duration = 0.0
            if response.metadata is not None:
                duration = getattr(response.metadata, "duration", 0.0) or 0.0

            return TranscriptResult(
                text=transcript,
                confidence=confidence,
                language=language,
                duration=duration,
            )

        except TimeoutError as e:
            raise STTTimeoutError(
                f"Deepgram API request timed out after {self.timeout}s"
            ) from e
        except ApiError as e:
            error_msg = str(e).lower()
            if "rate" in error_msg and "limit" in error_msg:
                raise STTRateLimitError(f"Deepgram rate limit exceeded: {e}") from e
            if "invalid" in error_msg or "format" in error_msg:
                raise STTInvalidAudioError(f"Invalid audio format: {e}") from e
            raise STTError(f"Deepgram transcription failed: {e}") from e
        except Exception as e:
            raise STTError(f"Unexpected error during transcription: {e}") from e

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        language: str = "en",
    ) -> AsyncIterator[TranscriptChunk]:
        """Transcribe streaming audio data in real-time using Deepgram WebSocket.

        This method processes audio chunks as they arrive and yields
        partial transcription results for low-latency applications.

        Args:
            audio_stream: Async iterator yielding audio data chunks.
            language: Language code for transcription ("en" or "es").
                Defaults to "en".

        Yields:
            TranscriptChunk objects containing partial transcriptions.
            Chunks with is_final=True indicate completed utterances.

        Raises:
            STTError: If transcription fails.
            ValueError: If an unsupported language is specified.
        """
        dg_language = self._validate_language(language)

        # Queue to receive transcription results
        result_queue: asyncio.Queue[TranscriptChunk | Exception | None] = asyncio.Queue()
        connection_started = asyncio.Event()

        try:
            # Get the WebSocket connection as an async iterator
            async for socket_client in self.client.listen.v1.connect(
                model="nova-2",
                language=dg_language,
                smart_format="true",
                punctuate="true",
                interim_results="true",
                encoding="linear16",
                sample_rate="16000",
                channels="1",
            ):
                connection_started.set()

                # Capture socket_client in closure to avoid B023 warning
                client = socket_client

                # Task to send audio data
                async def send_audio(sock: object = client) -> None:
                    try:
                        async for chunk in audio_stream:
                            if chunk:
                                await sock.send(chunk)  # type: ignore[union-attr]
                        # Signal end of audio
                        await sock.finish()  # type: ignore[union-attr]
                    except Exception as e:
                        await result_queue.put(e)

                # Task to receive results
                async def receive_results(sock: object = client) -> None:
                    try:
                        async for message in sock:  # type: ignore[union-attr]
                            # Parse the message
                            if hasattr(message, "channel"):
                                channel = message.channel
                                if channel and hasattr(channel, "alternatives"):
                                    alternatives = channel.alternatives
                                    if alternatives:
                                        transcript = alternatives[0].transcript or ""
                                        is_final = getattr(message, "is_final", False) or getattr(
                                            message, "speech_final", False
                                        )

                                        if transcript:
                                            chunk = TranscriptChunk(
                                                partial_text=transcript,
                                                is_final=is_final,
                                            )
                                            await result_queue.put(chunk)
                    except Exception as e:
                        await result_queue.put(e)
                    finally:
                        await result_queue.put(None)

                # Start both tasks
                send_task = asyncio.create_task(send_audio())
                receive_task = asyncio.create_task(receive_results())

                try:
                    # Yield results as they come in
                    while True:
                        item = await result_queue.get()

                        if item is None:
                            # Connection closed
                            break
                        elif isinstance(item, Exception):
                            # Re-raise errors
                            raise STTError(f"Stream transcription error: {item}") from item
                        else:
                            # Yield the chunk
                            yield item
                finally:
                    # Ensure tasks are cancelled if we exit early
                    for task in [send_task, receive_task]:
                        if not task.done():
                            task.cancel()
                            with contextlib.suppress(asyncio.CancelledError):
                                await task

                # Only process one connection
                break

            if not connection_started.is_set():
                raise STTError("Failed to start Deepgram WebSocket connection")

        except ApiError as e:
            error_msg = str(e).lower()
            if "rate" in error_msg and "limit" in error_msg:
                raise STTRateLimitError(f"Deepgram rate limit exceeded: {e}") from e
            raise STTError(f"Deepgram streaming failed: {e}") from e
        except STTError:
            raise
        except Exception as e:
            raise STTError(f"Unexpected error during stream transcription: {e}") from e
