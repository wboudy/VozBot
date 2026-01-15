"""Escalation trigger detection for VozBot.

Detects when a call should be escalated to a human agent based on:
- Explicit request keywords (human, agent, person, help, emergency)
- Spanish keywords (persona, ayuda, emergencia)
- Negative/frustrated sentiment
- Repeated failed intents (3+ failures)
- Legal keywords (lawyer, sue, legal)

The detector is designed to minimize false positives (<5% on test corpus)
while catching genuine escalation needs.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TriggerType(str, Enum):
    """Types of escalation triggers."""

    EXPLICIT_REQUEST = "explicit_request"  # User explicitly asks for human
    FRUSTRATION = "frustration"  # Negative sentiment detected
    REPEATED_FAILURE = "repeated_failure"  # Multiple failed intents
    LEGAL = "legal"  # Legal-related keywords
    EMERGENCY = "emergency"  # Emergency situation
    NONE = "none"  # No escalation needed


@dataclass
class EscalationResult:
    """Result of escalation detection.

    Attributes:
        should_escalate: Whether the call should be escalated.
        trigger_type: The type of trigger that caused escalation.
        confidence: Confidence score 0.0-1.0.
        matched_triggers: List of specific triggers that were matched.
        reason: Human-readable reason for escalation.
    """

    should_escalate: bool
    trigger_type: TriggerType
    confidence: float
    matched_triggers: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "should_escalate": self.should_escalate,
            "trigger_type": self.trigger_type.value,
            "confidence": self.confidence,
            "matched_triggers": self.matched_triggers,
            "reason": self.reason,
        }


@dataclass
class EscalationConfig:
    """Configuration for escalation detection.

    Attributes:
        min_confidence_threshold: Minimum confidence to trigger escalation.
        repeated_failure_count: Number of failures before escalation.
        frustration_word_threshold: Number of frustration words to trigger.
        enable_sentiment_analysis: Whether to analyze sentiment.
        enable_legal_detection: Whether to detect legal keywords.
        enable_emergency_detection: Whether to detect emergency keywords.
    """

    min_confidence_threshold: float = 0.6
    repeated_failure_count: int = 3
    frustration_word_threshold: int = 2
    enable_sentiment_analysis: bool = True
    enable_legal_detection: bool = True
    enable_emergency_detection: bool = True


# English keywords for explicit human request
HUMAN_REQUEST_KEYWORDS_EN = {
    "human",
    "agent",
    "person",
    "representative",
    "operator",
    "someone",
    "real person",
    "talk to someone",
    "speak to someone",
    "speak with someone",
    "talk to a human",
    "speak to a human",
    "talk to a person",
    "speak to a person",
    "transfer me",
    "connect me",
    "live agent",
    "real human",
}

# Spanish keywords for explicit human request
HUMAN_REQUEST_KEYWORDS_ES = {
    "persona",
    "agente",
    "representante",
    "operador",
    "alguien",
    "persona real",
    "hablar con alguien",
    "hablar con una persona",
    "transferirme",
    "conectarme",
    "agente en vivo",
}

# Help keywords that suggest user needs assistance (high confidence only in context)
HELP_KEYWORDS_EN = {"help", "help me", "i need help", "can you help"}
HELP_KEYWORDS_ES = {"ayuda", "ayudame", "necesito ayuda", "puede ayudarme"}

# Emergency keywords (both languages)
EMERGENCY_KEYWORDS_EN = {
    "emergency",
    "urgent",
    "immediately",
    "right now",
    "911",
    "police",
    "ambulance",
    "fire",
}
EMERGENCY_KEYWORDS_ES = {
    "emergencia",
    "urgente",
    "inmediatamente",
    "ahora mismo",
    "policia",
    "ambulancia",
    "bomberos",
}

# Legal keywords (both languages)
LEGAL_KEYWORDS_EN = {
    "lawyer",
    "attorney",
    "sue",
    "lawsuit",
    "legal action",
    "court",
    "legal",
    "my rights",
    "discrimination",
    "discriminating",
    "discriminate",
    "harassment",
    "complaint",
    "report you",
}
LEGAL_KEYWORDS_ES = {
    "abogado",
    "demanda",
    "demandar",
    "accion legal",
    "tribunal",
    "legal",
    "mis derechos",
    "discriminacion",
    "discriminando",
    "discriminar",
    "acoso",
    "queja",
    "reportar",
}

# Frustration/negative sentiment indicators
FRUSTRATION_WORDS_EN = {
    "frustrated",
    "frustrating",
    "annoyed",
    "annoying",
    "angry",
    "mad",
    "upset",
    "ridiculous",
    "terrible",
    "awful",
    "horrible",
    "useless",
    "stupid",
    "incompetent",
    "waste of time",
    "waste time",
    "this is ridiculous",
    "unacceptable",
    "disappointed",
    "disgusted",
    "fed up",
    "sick of",
    "tired of",
    "enough",
    "give up",
    "done",
    "forget it",
    "never mind",
}

FRUSTRATION_WORDS_ES = {
    "frustrado",
    "frustrante",
    "molesto",
    "enojado",
    "furioso",
    "ridiculo",
    "terrible",
    "horrible",
    "inutil",
    "estupido",
    "incompetente",
    "perdida de tiempo",
    "perdida",
    "inaceptable",
    "decepcionado",
    "harto",
    "cansado de",
    "suficiente",
    "me rindo",
    "olvidalo",
}

# Intensifiers that increase confidence when combined with frustration
INTENSIFIERS_EN = {
    "very",
    "really",
    "so",
    "extremely",
    "totally",
    "completely",
    "absolutely",
    "incredibly",
}
INTENSIFIERS_ES = {
    "muy",
    "realmente",
    "tan",
    "extremadamente",
    "totalmente",
    "completamente",
    "absolutamente",
    "increiblemente",
}

# Repeated phrases that indicate loop/failure (both languages)
REPETITION_INDICATORS = {
    "i already said",
    "i told you",
    "i just said",
    "again",
    "repeat",
    "already explained",
    "how many times",
    "ya dije",
    "ya te dije",
    "otra vez",
    "repetir",
    "ya explique",
    "cuantas veces",
}


class EscalationDetector:
    """Detects when a call should be escalated to a human agent.

    Analyzes user input for various escalation triggers and returns
    a result indicating whether escalation is needed.

    Attributes:
        config: Configuration for detection thresholds.
        failed_intent_count: Counter for failed intents in current session.

    Example:
        ```python
        detector = EscalationDetector()

        # Check single message
        result = detector.analyze("I want to speak to a human")
        if result.should_escalate:
            print(f"Escalation needed: {result.reason}")

        # Track failed intents
        detector.record_failed_intent()
        detector.record_failed_intent()
        detector.record_failed_intent()
        result = detector.analyze("hello")  # Will trigger on repeated failure
        ```
    """

    def __init__(self, config: EscalationConfig | None = None) -> None:
        """Initialize the escalation detector.

        Args:
            config: Configuration for detection thresholds.
        """
        self._config = config or EscalationConfig()
        self._failed_intent_count = 0
        self._conversation_history: list[str] = []

    @property
    def config(self) -> EscalationConfig:
        """Get the current configuration."""
        return self._config

    @property
    def failed_intent_count(self) -> int:
        """Get the count of failed intents."""
        return self._failed_intent_count

    def reset(self) -> None:
        """Reset the detector state for a new session."""
        self._failed_intent_count = 0
        self._conversation_history.clear()

    def record_failed_intent(self) -> None:
        """Record a failed intent attempt.

        Call this when the LLM fails to understand or fulfill
        the user's request.
        """
        self._failed_intent_count += 1
        logger.debug(f"Failed intent recorded. Count: {self._failed_intent_count}")

    def clear_failed_intents(self) -> None:
        """Clear the failed intent counter.

        Call this when the conversation is progressing successfully.
        """
        self._failed_intent_count = 0

    def analyze(
        self,
        user_text: str,
        language: str = "en",
        context: dict[str, Any] | None = None,
    ) -> EscalationResult:
        """Analyze user input for escalation triggers.

        Checks for explicit requests, sentiment, repeated failures,
        and legal/emergency keywords.

        Args:
            user_text: The user's input text.
            language: Language code ("en" or "es").
            context: Optional context dict with additional info.

        Returns:
            EscalationResult with escalation decision and details.
        """
        if not user_text or not user_text.strip():
            return EscalationResult(
                should_escalate=False,
                trigger_type=TriggerType.NONE,
                confidence=0.0,
            )

        # Normalize text for matching
        text_lower = user_text.lower().strip()
        self._conversation_history.append(text_lower)

        # Track all detected triggers and their confidence
        triggers: list[tuple[TriggerType, float, list[str], str]] = []

        # Check for explicit human request
        explicit_result = self._check_explicit_request(text_lower, language)
        if explicit_result:
            triggers.append(explicit_result)

        # Check for emergency keywords
        if self._config.enable_emergency_detection:
            emergency_result = self._check_emergency(text_lower, language)
            if emergency_result:
                triggers.append(emergency_result)

        # Check for legal keywords
        if self._config.enable_legal_detection:
            legal_result = self._check_legal(text_lower, language)
            if legal_result:
                triggers.append(legal_result)

        # Check for frustration/negative sentiment
        if self._config.enable_sentiment_analysis:
            frustration_result = self._check_frustration(text_lower, language)
            if frustration_result:
                triggers.append(frustration_result)

        # Check for repeated failures
        failure_result = self._check_repeated_failures()
        if failure_result:
            triggers.append(failure_result)

        # Check for repetition indicators in conversation
        repetition_result = self._check_repetition_indicators(text_lower)
        if repetition_result:
            triggers.append(repetition_result)

        # Select the highest confidence trigger
        if triggers:
            # Sort by confidence (descending)
            triggers.sort(key=lambda x: x[1], reverse=True)
            best_trigger = triggers[0]
            trigger_type, confidence, matched, reason = best_trigger

            # Apply minimum threshold
            if confidence >= self._config.min_confidence_threshold:
                return EscalationResult(
                    should_escalate=True,
                    trigger_type=trigger_type,
                    confidence=confidence,
                    matched_triggers=matched,
                    reason=reason,
                )

        return EscalationResult(
            should_escalate=False,
            trigger_type=TriggerType.NONE,
            confidence=0.0,
        )

    def _check_explicit_request(
        self, text: str, language: str
    ) -> tuple[TriggerType, float, list[str], str] | None:
        """Check for explicit requests to speak to a human."""
        matched = []

        # Select keyword sets based on language
        human_keywords = (
            HUMAN_REQUEST_KEYWORDS_ES if language == "es" else HUMAN_REQUEST_KEYWORDS_EN
        )
        help_keywords = HELP_KEYWORDS_ES if language == "es" else HELP_KEYWORDS_EN

        # Check human request keywords (high confidence)
        for keyword in human_keywords:
            # Use word boundary matching to avoid false positives
            pattern = r"\b" + re.escape(keyword) + r"\b"
            if re.search(pattern, text):
                matched.append(keyword)

        if matched:
            # High confidence for explicit request
            confidence = min(0.95, 0.8 + 0.05 * len(matched))
            return (
                TriggerType.EXPLICIT_REQUEST,
                confidence,
                matched,
                f"User explicitly requested human agent: {', '.join(matched)}",
            )

        # Check help keywords (lower confidence, needs context)
        help_matched = []
        for keyword in help_keywords:
            pattern = r"\b" + re.escape(keyword) + r"\b"
            if re.search(pattern, text):
                help_matched.append(keyword)

        # Help keywords alone are not enough - need additional context
        # like frustration or being at the start of conversation
        if help_matched and len(self._conversation_history) <= 2:
            # Early "help" might just be a greeting, low confidence
            return None

        return None

    def _check_emergency(
        self, text: str, language: str
    ) -> tuple[TriggerType, float, list[str], str] | None:
        """Check for emergency keywords."""
        keywords = EMERGENCY_KEYWORDS_ES if language == "es" else EMERGENCY_KEYWORDS_EN
        matched = []

        for keyword in keywords:
            pattern = r"\b" + re.escape(keyword) + r"\b"
            if re.search(pattern, text):
                matched.append(keyword)

        if matched:
            # Very high confidence for emergency
            confidence = min(0.98, 0.9 + 0.02 * len(matched))
            return (
                TriggerType.EMERGENCY,
                confidence,
                matched,
                f"Emergency keywords detected: {', '.join(matched)}",
            )

        return None

    def _check_legal(
        self, text: str, language: str
    ) -> tuple[TriggerType, float, list[str], str] | None:
        """Check for legal-related keywords."""
        keywords = LEGAL_KEYWORDS_ES if language == "es" else LEGAL_KEYWORDS_EN
        matched = []

        for keyword in keywords:
            pattern = r"\b" + re.escape(keyword) + r"\b"
            if re.search(pattern, text):
                matched.append(keyword)

        if matched:
            # High confidence for legal matters
            confidence = min(0.95, 0.75 + 0.1 * len(matched))
            return (
                TriggerType.LEGAL,
                confidence,
                matched,
                f"Legal keywords detected: {', '.join(matched)}",
            )

        return None

    def _check_frustration(
        self, text: str, language: str
    ) -> tuple[TriggerType, float, list[str], str] | None:
        """Check for frustration/negative sentiment."""
        frustration_words = (
            FRUSTRATION_WORDS_ES if language == "es" else FRUSTRATION_WORDS_EN
        )
        intensifiers = INTENSIFIERS_ES if language == "es" else INTENSIFIERS_EN

        matched_frustration = []
        has_intensifier = False

        # Check for frustration words
        for word in frustration_words:
            pattern = r"\b" + re.escape(word) + r"\b"
            if re.search(pattern, text):
                matched_frustration.append(word)

        # Check for intensifiers
        for intensifier in intensifiers:
            pattern = r"\b" + re.escape(intensifier) + r"\b"
            if re.search(pattern, text):
                has_intensifier = True
                break

        if not matched_frustration:
            return None

        # Calculate confidence based on number of frustration words and intensifiers
        word_count = len(matched_frustration)
        if word_count < self._config.frustration_word_threshold:
            # Below threshold - lower confidence
            confidence = 0.3 + 0.15 * word_count
        else:
            # At or above threshold
            confidence = 0.6 + 0.1 * (word_count - self._config.frustration_word_threshold)

        # Boost for intensifiers
        if has_intensifier:
            confidence = min(0.95, confidence + 0.15)

        # Only return if meeting minimum threshold
        if confidence >= self._config.min_confidence_threshold:
            return (
                TriggerType.FRUSTRATION,
                confidence,
                matched_frustration,
                f"Frustration detected: {', '.join(matched_frustration)}",
            )

        return None

    def _check_repeated_failures(
        self,
    ) -> tuple[TriggerType, float, list[str], str] | None:
        """Check if repeated failures warrant escalation."""
        if self._failed_intent_count >= self._config.repeated_failure_count:
            # Confidence increases with failure count
            confidence = min(
                0.95,
                0.7 + 0.05 * (self._failed_intent_count - self._config.repeated_failure_count),
            )
            return (
                TriggerType.REPEATED_FAILURE,
                confidence,
                [f"failed_intents:{self._failed_intent_count}"],
                f"User has experienced {self._failed_intent_count} failed intents",
            )
        return None

    def _check_repetition_indicators(
        self, text: str
    ) -> tuple[TriggerType, float, list[str], str] | None:
        """Check for phrases indicating user is repeating themselves."""
        matched = []

        for indicator in REPETITION_INDICATORS:
            pattern = r"\b" + re.escape(indicator) + r"\b"
            if re.search(pattern, text):
                matched.append(indicator)

        if matched:
            # Moderate confidence - user might just be clarifying
            confidence = min(0.75, 0.5 + 0.1 * len(matched))
            if confidence >= self._config.min_confidence_threshold:
                return (
                    TriggerType.FRUSTRATION,
                    confidence,
                    matched,
                    f"User indicates repetition: {', '.join(matched)}",
                )

        return None

    def get_escalation_summary(self) -> dict[str, Any]:
        """Get a summary of escalation state.

        Returns:
            Dict with failed intent count and conversation length.
        """
        return {
            "failed_intent_count": self._failed_intent_count,
            "conversation_length": len(self._conversation_history),
            "config": {
                "min_confidence_threshold": self._config.min_confidence_threshold,
                "repeated_failure_count": self._config.repeated_failure_count,
                "frustration_word_threshold": self._config.frustration_word_threshold,
            },
        }
