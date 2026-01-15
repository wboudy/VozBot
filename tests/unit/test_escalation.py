"""Tests for escalation trigger detection.

Verifies:
- Explicit request keyword detection (English/Spanish)
- Emergency keyword detection
- Legal keyword detection
- Frustration/sentiment detection
- Repeated failure escalation
- Configurable thresholds
- False positive rate <5% on test corpus
"""

from __future__ import annotations

import pytest

from vozbot.agent.escalation import (
    EscalationConfig,
    EscalationDetector,
    EscalationResult,
    TriggerType,
)


class TestEscalationDetectorInit:
    """Tests for EscalationDetector initialization."""

    def test_init_default_config(self) -> None:
        """Test initialization with default config."""
        detector = EscalationDetector()

        assert detector.config.min_confidence_threshold == 0.6
        assert detector.config.repeated_failure_count == 3
        assert detector.config.frustration_word_threshold == 2
        assert detector.failed_intent_count == 0

    def test_init_custom_config(self) -> None:
        """Test initialization with custom config."""
        config = EscalationConfig(
            min_confidence_threshold=0.8,
            repeated_failure_count=5,
            frustration_word_threshold=3,
        )
        detector = EscalationDetector(config=config)

        assert detector.config.min_confidence_threshold == 0.8
        assert detector.config.repeated_failure_count == 5
        assert detector.config.frustration_word_threshold == 3

    def test_reset_clears_state(self) -> None:
        """Test that reset clears failed intents and history."""
        detector = EscalationDetector()
        detector.record_failed_intent()
        detector.record_failed_intent()
        detector.analyze("test message")

        detector.reset()

        assert detector.failed_intent_count == 0
        summary = detector.get_escalation_summary()
        assert summary["conversation_length"] == 0


class TestExplicitRequestDetection:
    """Tests for explicit human request keyword detection."""

    @pytest.fixture
    def detector(self) -> EscalationDetector:
        """Create a detector with default config."""
        return EscalationDetector()

    @pytest.mark.parametrize(
        "text,expected_trigger",
        [
            ("I want to speak to a human", TriggerType.EXPLICIT_REQUEST),
            ("Can I talk to a person", TriggerType.EXPLICIT_REQUEST),
            ("Let me speak to an agent", TriggerType.EXPLICIT_REQUEST),
            ("Transfer me to someone", TriggerType.EXPLICIT_REQUEST),
            ("I need a representative", TriggerType.EXPLICIT_REQUEST),
            ("Connect me to a live agent", TriggerType.EXPLICIT_REQUEST),
            ("I want to talk to a real person", TriggerType.EXPLICIT_REQUEST),
            ("Let me speak with someone please", TriggerType.EXPLICIT_REQUEST),
            ("Get me an operator", TriggerType.EXPLICIT_REQUEST),
        ],
    )
    def test_english_explicit_request_keywords(
        self, detector: EscalationDetector, text: str, expected_trigger: TriggerType
    ) -> None:
        """Test English explicit request keywords trigger escalation."""
        result = detector.analyze(text, language="en")

        assert result.should_escalate is True
        assert result.trigger_type == expected_trigger
        assert result.confidence >= 0.8

    @pytest.mark.parametrize(
        "text,expected_trigger",
        [
            ("Quiero hablar con una persona", TriggerType.EXPLICIT_REQUEST),
            ("Necesito un agente", TriggerType.EXPLICIT_REQUEST),
            ("Transferirme por favor", TriggerType.EXPLICIT_REQUEST),
            ("Conectarme con alguien", TriggerType.EXPLICIT_REQUEST),
            ("Quiero hablar con un representante", TriggerType.EXPLICIT_REQUEST),
            ("Necesito un agente en vivo", TriggerType.EXPLICIT_REQUEST),
            ("Quiero una persona real", TriggerType.EXPLICIT_REQUEST),
        ],
    )
    def test_spanish_explicit_request_keywords(
        self, detector: EscalationDetector, text: str, expected_trigger: TriggerType
    ) -> None:
        """Test Spanish explicit request keywords trigger escalation."""
        result = detector.analyze(text, language="es")

        assert result.should_escalate is True
        assert result.trigger_type == expected_trigger
        assert result.confidence >= 0.8

    def test_case_insensitive_matching(self, detector: EscalationDetector) -> None:
        """Test that keyword matching is case insensitive."""
        result = detector.analyze("I WANT TO SPEAK TO A HUMAN", language="en")

        assert result.should_escalate is True
        assert result.trigger_type == TriggerType.EXPLICIT_REQUEST


class TestEmergencyDetection:
    """Tests for emergency keyword detection."""

    @pytest.fixture
    def detector(self) -> EscalationDetector:
        """Create a detector with default config."""
        return EscalationDetector()

    @pytest.mark.parametrize(
        "text",
        [
            "This is an emergency",
            "I need help immediately",
            "This is urgent",
            "Call 911",
            "I need police",
            "Call an ambulance",
            "There's a fire",
            "Right now please",
        ],
    )
    def test_english_emergency_keywords(
        self, detector: EscalationDetector, text: str
    ) -> None:
        """Test English emergency keywords trigger escalation."""
        result = detector.analyze(text, language="en")

        assert result.should_escalate is True
        assert result.trigger_type == TriggerType.EMERGENCY
        assert result.confidence >= 0.9

    @pytest.mark.parametrize(
        "text",
        [
            "Es una emergencia",
            "Es urgente",
            "Necesito policia",
            "Llamen una ambulancia",
            "Hay un incendio, bomberos",
            "Ahora mismo por favor",
            "Inmediatamente",
        ],
    )
    def test_spanish_emergency_keywords(
        self, detector: EscalationDetector, text: str
    ) -> None:
        """Test Spanish emergency keywords trigger escalation."""
        result = detector.analyze(text, language="es")

        assert result.should_escalate is True
        assert result.trigger_type == TriggerType.EMERGENCY
        assert result.confidence >= 0.9

    def test_emergency_detection_can_be_disabled(self) -> None:
        """Test that emergency detection can be disabled."""
        config = EscalationConfig(enable_emergency_detection=False)
        detector = EscalationDetector(config=config)

        result = detector.analyze("This is an emergency", language="en")

        # Should not escalate based on emergency (might escalate on other triggers)
        assert result.trigger_type != TriggerType.EMERGENCY


class TestLegalDetection:
    """Tests for legal keyword detection."""

    @pytest.fixture
    def detector(self) -> EscalationDetector:
        """Create a detector with default config."""
        return EscalationDetector()

    @pytest.mark.parametrize(
        "text",
        [
            "I'm going to sue you",
            "I need to talk to my lawyer",
            "This is a legal matter",
            "I'm taking legal action",
            "I'll see you in court",
            "This is harassment",
            "You're discriminating against me",
            "I want to file a complaint",
            "I know my rights",
            "I'm going to report you",
            "I need an attorney",
        ],
    )
    def test_english_legal_keywords(
        self, detector: EscalationDetector, text: str
    ) -> None:
        """Test English legal keywords trigger escalation."""
        result = detector.analyze(text, language="en")

        assert result.should_escalate is True
        assert result.trigger_type == TriggerType.LEGAL
        assert result.confidence >= 0.75

    @pytest.mark.parametrize(
        "text",
        [
            "Voy a demandar",
            "Necesito hablar con mi abogado",
            "Es un asunto legal",
            "Voy a tomar accion legal",
            "Los veo en el tribunal",
            "Esto es acoso",
            "Estan discriminando",
            "Quiero hacer una queja",
            "Conozco mis derechos",
            "Los voy a reportar",
        ],
    )
    def test_spanish_legal_keywords(
        self, detector: EscalationDetector, text: str
    ) -> None:
        """Test Spanish legal keywords trigger escalation."""
        result = detector.analyze(text, language="es")

        assert result.should_escalate is True
        assert result.trigger_type == TriggerType.LEGAL
        assert result.confidence >= 0.75

    def test_legal_detection_can_be_disabled(self) -> None:
        """Test that legal detection can be disabled."""
        config = EscalationConfig(enable_legal_detection=False)
        detector = EscalationDetector(config=config)

        result = detector.analyze("I'm going to sue you", language="en")

        # Should not escalate based on legal trigger
        assert result.trigger_type != TriggerType.LEGAL


class TestFrustrationDetection:
    """Tests for frustration/sentiment detection."""

    @pytest.fixture
    def detector(self) -> EscalationDetector:
        """Create a detector with default config."""
        return EscalationDetector()

    @pytest.mark.parametrize(
        "text",
        [
            "This is ridiculous and terrible",
            "I'm very frustrated with this",
            "This is completely useless and stupid",
            "I'm so annoyed and upset",
            "This is awful and horrible service",
            "I'm fed up and frustrated with this",
            "I'm sick of this terrible nonsense",
            "What a waste of time, this is ridiculous",
            "This is absolutely unacceptable and terrible",
            "I give up, forget it",
        ],
    )
    def test_english_frustration_triggers(
        self, detector: EscalationDetector, text: str
    ) -> None:
        """Test English frustration phrases trigger escalation."""
        result = detector.analyze(text, language="en")

        assert result.should_escalate is True
        assert result.trigger_type == TriggerType.FRUSTRATION
        assert result.confidence >= 0.6

    @pytest.mark.parametrize(
        "text",
        [
            "Esto es ridiculo y terrible",
            "Estoy muy frustrado y molesto",
            "Esto es completamente inutil y horrible",
            "Estoy muy molesto y enojado",
            "Es un servicio horrible y terrible",
            "Estoy harto y frustrado de esto",
            "Es una perdida de tiempo ridicula",
            "Esto es inaceptable y terrible",
            "Me rindo, olvidalo",
        ],
    )
    def test_spanish_frustration_triggers(
        self, detector: EscalationDetector, text: str
    ) -> None:
        """Test Spanish frustration phrases trigger escalation."""
        result = detector.analyze(text, language="es")

        assert result.should_escalate is True
        assert result.trigger_type == TriggerType.FRUSTRATION
        assert result.confidence >= 0.6

    def test_single_frustration_word_low_confidence(self) -> None:
        """Test that a single frustration word has lower confidence."""
        config = EscalationConfig(
            frustration_word_threshold=2,
            min_confidence_threshold=0.6,
        )
        detector = EscalationDetector(config=config)

        result = detector.analyze("I'm frustrated", language="en")

        # Single word below threshold should not trigger
        assert result.should_escalate is False

    def test_intensifier_boosts_confidence(self) -> None:
        """Test that intensifiers boost confidence."""
        detector = EscalationDetector()

        # With intensifier
        result_with_intensifier = detector.analyze(
            "I am extremely frustrated and very upset", language="en"
        )

        # Without intensifier (reset detector)
        detector.reset()
        result_without_intensifier = detector.analyze(
            "I am frustrated and upset", language="en"
        )

        # Both should escalate but intensifier version should have higher confidence
        assert result_with_intensifier.confidence >= result_without_intensifier.confidence

    def test_sentiment_detection_can_be_disabled(self) -> None:
        """Test that sentiment detection can be disabled."""
        config = EscalationConfig(enable_sentiment_analysis=False)
        detector = EscalationDetector(config=config)

        result = detector.analyze("I'm very frustrated and upset", language="en")

        # Should not escalate based on frustration
        assert result.trigger_type != TriggerType.FRUSTRATION


class TestRepeatedFailureDetection:
    """Tests for repeated failure escalation."""

    def test_no_escalation_below_threshold(self) -> None:
        """Test no escalation when failures below threshold."""
        detector = EscalationDetector()

        detector.record_failed_intent()
        detector.record_failed_intent()

        result = detector.analyze("hello", language="en")

        assert result.should_escalate is False

    def test_escalation_at_threshold(self) -> None:
        """Test escalation when failures reach threshold."""
        detector = EscalationDetector()

        detector.record_failed_intent()
        detector.record_failed_intent()
        detector.record_failed_intent()

        result = detector.analyze("hello", language="en")

        assert result.should_escalate is True
        assert result.trigger_type == TriggerType.REPEATED_FAILURE
        assert "3" in str(result.matched_triggers)

    def test_escalation_above_threshold(self) -> None:
        """Test escalation confidence increases above threshold."""
        detector = EscalationDetector()

        # 5 failures
        for _ in range(5):
            detector.record_failed_intent()

        result = detector.analyze("hello", language="en")

        assert result.should_escalate is True
        assert result.trigger_type == TriggerType.REPEATED_FAILURE
        # Higher confidence than at threshold
        assert result.confidence > 0.7

    def test_configurable_failure_threshold(self) -> None:
        """Test custom failure threshold."""
        config = EscalationConfig(repeated_failure_count=5)
        detector = EscalationDetector(config=config)

        # 4 failures - below threshold
        for _ in range(4):
            detector.record_failed_intent()

        result = detector.analyze("hello", language="en")
        assert result.should_escalate is False

        # 5th failure - at threshold
        detector.record_failed_intent()
        result = detector.analyze("hello", language="en")
        assert result.should_escalate is True

    def test_clear_failed_intents(self) -> None:
        """Test clearing failed intent counter."""
        detector = EscalationDetector()

        detector.record_failed_intent()
        detector.record_failed_intent()
        detector.clear_failed_intents()

        assert detector.failed_intent_count == 0


class TestRepetitionIndicators:
    """Tests for repetition indicator detection."""

    @pytest.fixture
    def detector(self) -> EscalationDetector:
        """Create a detector with default config."""
        return EscalationDetector()

    @pytest.mark.parametrize(
        "text",
        [
            "I already said I need an appointment",
            "I told you my name already",
            "How many times do I have to say this",
            "I just said that",
            "Let me repeat myself",
            "I already explained this",
        ],
    )
    def test_english_repetition_indicators(
        self, detector: EscalationDetector, text: str
    ) -> None:
        """Test English repetition indicators trigger escalation."""
        result = detector.analyze(text, language="en")

        assert result.should_escalate is True
        assert result.trigger_type == TriggerType.FRUSTRATION

    @pytest.mark.parametrize(
        "text",
        [
            "Ya dije que necesito una cita",
            "Ya te dije mi nombre",
            "Cuantas veces tengo que decir esto",
            "Otra vez lo mismo",
            "Ya explique esto",
        ],
    )
    def test_spanish_repetition_indicators(
        self, detector: EscalationDetector, text: str
    ) -> None:
        """Test Spanish repetition indicators trigger escalation."""
        result = detector.analyze(text, language="es")

        assert result.should_escalate is True
        assert result.trigger_type == TriggerType.FRUSTRATION


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.fixture
    def detector(self) -> EscalationDetector:
        """Create a detector with default config."""
        return EscalationDetector()

    def test_empty_input(self, detector: EscalationDetector) -> None:
        """Test empty input returns no escalation."""
        result = detector.analyze("", language="en")

        assert result.should_escalate is False
        assert result.trigger_type == TriggerType.NONE

    def test_whitespace_only_input(self, detector: EscalationDetector) -> None:
        """Test whitespace-only input returns no escalation."""
        result = detector.analyze("   \n\t  ", language="en")

        assert result.should_escalate is False
        assert result.trigger_type == TriggerType.NONE

    def test_neutral_message_no_escalation(self, detector: EscalationDetector) -> None:
        """Test neutral messages don't trigger escalation."""
        neutral_messages = [
            "Hello, I'd like to schedule an appointment",
            "My name is John Smith",
            "I'm calling about my insurance policy",
            "When is the office open?",
            "Can you tell me about your services?",
            "Thank you for your help",
        ]

        for message in neutral_messages:
            result = detector.analyze(message, language="en")
            assert result.should_escalate is False, f"Falsely escalated: {message}"

    def test_partial_keyword_no_match(self, detector: EscalationDetector) -> None:
        """Test partial keywords don't trigger false positives."""
        # "humanity" contains "human" but shouldn't match
        result = detector.analyze("I believe in humanity", language="en")
        assert result.should_escalate is False

    def test_word_boundary_matching(self, detector: EscalationDetector) -> None:
        """Test keywords are matched with word boundaries."""
        # "personal" contains "person" but shouldn't match
        result = detector.analyze("I have a personal question", language="en")
        assert result.trigger_type != TriggerType.EXPLICIT_REQUEST

        # "agent" should match
        result = detector.analyze("I want an agent", language="en")
        assert result.should_escalate is True

    def test_multiple_trigger_types_highest_confidence_wins(
        self, detector: EscalationDetector
    ) -> None:
        """Test that multiple triggers return the highest confidence one."""
        # Emergency should win over frustration
        result = detector.analyze(
            "This is an emergency and I'm frustrated", language="en"
        )

        assert result.should_escalate is True
        # Emergency typically has higher confidence
        assert result.trigger_type == TriggerType.EMERGENCY

    def test_minimum_threshold_respected(self) -> None:
        """Test that minimum confidence threshold is respected."""
        config = EscalationConfig(min_confidence_threshold=0.99)
        detector = EscalationDetector(config=config)

        # Even explicit request might not meet 0.99 threshold
        result = detector.analyze("I want a person", language="en")

        # With such a high threshold, might not escalate
        # (depends on implementation, but tests threshold is applied)
        if result.should_escalate:
            assert result.confidence >= 0.99


class TestEscalationResult:
    """Tests for EscalationResult dataclass."""

    def test_to_dict_serialization(self) -> None:
        """Test EscalationResult serializes correctly."""
        result = EscalationResult(
            should_escalate=True,
            trigger_type=TriggerType.EXPLICIT_REQUEST,
            confidence=0.85,
            matched_triggers=["human", "person"],
            reason="User requested human agent",
        )

        data = result.to_dict()

        assert data["should_escalate"] is True
        assert data["trigger_type"] == "explicit_request"
        assert data["confidence"] == 0.85
        assert data["matched_triggers"] == ["human", "person"]
        assert data["reason"] == "User requested human agent"

    def test_default_values(self) -> None:
        """Test EscalationResult default values."""
        result = EscalationResult(
            should_escalate=False,
            trigger_type=TriggerType.NONE,
            confidence=0.0,
        )

        assert result.matched_triggers == []
        assert result.reason == ""


class TestEscalationSummary:
    """Tests for escalation summary functionality."""

    def test_get_escalation_summary(self) -> None:
        """Test getting escalation summary."""
        detector = EscalationDetector()

        detector.record_failed_intent()
        detector.analyze("test message 1")
        detector.analyze("test message 2")

        summary = detector.get_escalation_summary()

        assert summary["failed_intent_count"] == 1
        assert summary["conversation_length"] == 2
        assert "config" in summary
        assert summary["config"]["repeated_failure_count"] == 3


class TestFalsePositiveRate:
    """Tests to verify false positive rate is below 5%.

    Uses a corpus of neutral/normal messages that should NOT trigger escalation.
    """

    @pytest.fixture
    def detector(self) -> EscalationDetector:
        """Create a detector with default config."""
        return EscalationDetector()

    def test_false_positive_rate_english(self, detector: EscalationDetector) -> None:
        """Test false positive rate on English neutral corpus."""
        # Corpus of 100 neutral messages that should NOT trigger escalation
        neutral_corpus = [
            "Hello, I'd like to schedule an appointment",
            "My name is John Smith",
            "I'm calling about my insurance policy",
            "When is the office open",
            "Can you tell me about your services",
            "Thank you for your help",
            "What time do you close",
            "I need to make an appointment",
            "Is Dr. Johnson available today",
            "I'd like to check on my claim",
            "Can you look up my account",
            "I'm a new patient",
            "I've been a customer for years",
            "What insurance do you accept",
            "Do you have any openings tomorrow",
            "I need to reschedule my appointment",
            "Can I get a callback",
            "My phone number is 555-1234",
            "I prefer morning appointments",
            "Is there a copay",
            "What are your office hours",
            "I need to update my address",
            "Can you send me the forms",
            "I'm calling to confirm my appointment",
            "Do I need a referral",
            "How long is the wait",
            "I'll hold please",
            "Yes that works for me",
            "No I don't have any questions",
            "That sounds good",
            "Perfect thank you",
            "I understand",
            "Let me check my calendar",
            "I can come in on Tuesday",
            "The appointment is for my daughter",
            "I need a prescription refill",
            "Can you fax the records",
            "I'll bring my insurance card",
            "What documents do I need",
            "Is parking available",
            "How do I get there",
            "What's the address",
            "I'm on my way",
            "I'll be there in 10 minutes",
            "Sorry I'm running late",
            "I need to cancel my appointment",
            "Can we move it to next week",
            "I'm feeling better now",
            "The pain is gone",
            "I'm here for a checkup",
            "This is a routine visit",
            "I have a question about billing",
            "Can you explain this charge",
            "I already paid that",
            "The check is in the mail",
            "I'll pay when I arrive",
            "Do you accept credit cards",
            "What's my balance",
            "I don't see that charge",
            "Let me look at my records",
            "I think there's a mistake",
            "Can you send me an itemized bill",
            "I have a high deductible plan",
            "My coverage changed",
            "I got a new insurance card",
            "Here's my member ID",
            "The group number is 12345",
            "I'm on Medicare",
            "I have Medicaid too",
            "It's secondary insurance",
            "Please bill my primary first",
            "The claim was denied",
            "I'm appealing the decision",
            "Can you resubmit it",
            "What's the diagnosis code",
            "I need a prior authorization",
            "How long does that take",
            "I'll wait for the approval",
            "It should be covered",
            "My plan covers that",
            "I've met my deductible",
            "This is preventive care",
            "It's an annual exam",
            "I haven't been in a while",
            "My last visit was in March",
            "I see Dr. Garcia",
            "She referred me to you",
            "I was told to call",
            "They said you could help",
            "I'm not sure who to ask",
            "Maybe you can help me",
            "I'm confused about the process",
            "Can you walk me through it",
            "What's the next step",
            "I'll do that today",
            "Thanks for explaining",
            "That makes sense",
            "I appreciate your patience",
            "You've been very helpful",
            "Have a nice day",
        ]

        false_positives = 0
        for message in neutral_corpus:
            # Reset between messages to avoid accumulated state
            detector.reset()
            result = detector.analyze(message, language="en")
            if result.should_escalate:
                false_positives += 1

        false_positive_rate = false_positives / len(neutral_corpus)

        # Assert false positive rate is below 5%
        assert false_positive_rate < 0.05, (
            f"False positive rate {false_positive_rate:.1%} exceeds 5% threshold. "
            f"False positives: {false_positives}/{len(neutral_corpus)}"
        )

    def test_false_positive_rate_spanish(self, detector: EscalationDetector) -> None:
        """Test false positive rate on Spanish neutral corpus."""
        neutral_corpus_es = [
            "Hola, quisiera hacer una cita",
            "Mi nombre es Juan Garcia",
            "Llamo por mi poliza de seguro",
            "A que hora abren",
            "Me puede decir sobre sus servicios",
            "Gracias por su ayuda",
            "A que hora cierran",
            "Necesito hacer una cita",
            "Esta disponible el doctor hoy",
            "Quisiera revisar mi reclamacion",
            "Puede buscar mi cuenta",
            "Soy paciente nuevo",
            "Soy cliente desde hace anos",
            "Que seguro aceptan",
            "Tienen disponibilidad manana",
            "Necesito cambiar mi cita",
            "Pueden llamarme despues",
            "Mi numero es 555-1234",
            "Prefiero citas en la manana",
            "Hay copago",
            "Cual es el horario",
            "Necesito actualizar mi direccion",
            "Me pueden enviar los formularios",
            "Llamo para confirmar mi cita",
            "Necesito una referencia",
            "Cuanto tiempo tengo que esperar",
            "Espero por favor",
            "Si eso me funciona",
            "No tengo preguntas",
            "Me parece bien",
            "Perfecto gracias",
            "Entiendo",
            "Deje revisar mi calendario",
            "Puedo ir el martes",
            "La cita es para mi hija",
            "Necesito una receta",
            "Pueden enviar el fax",
            "Traigo mi tarjeta de seguro",
            "Que documentos necesito",
            "Hay estacionamiento",
            "Como llego",
            "Cual es la direccion",
            "Voy en camino",
            "Llego en 10 minutos",
            "Disculpe voy tarde",
            "Necesito cancelar mi cita",
            "Podemos moverla a la proxima semana",
            "Ya me siento mejor",
            "Ya no me duele",
            "Vengo por un chequeo",
        ]

        false_positives = 0
        for message in neutral_corpus_es:
            detector.reset()
            result = detector.analyze(message, language="es")
            if result.should_escalate:
                false_positives += 1

        false_positive_rate = false_positives / len(neutral_corpus_es)

        assert false_positive_rate < 0.05, (
            f"Spanish false positive rate {false_positive_rate:.1%} exceeds 5% threshold. "
            f"False positives: {false_positives}/{len(neutral_corpus_es)}"
        )


class TestTruePositiveRate:
    """Tests to verify true positive rate for genuine escalation cases."""

    @pytest.fixture
    def detector(self) -> EscalationDetector:
        """Create a detector with default config."""
        return EscalationDetector()

    def test_true_positive_rate_explicit_requests(
        self, detector: EscalationDetector
    ) -> None:
        """Test that explicit human requests are detected."""
        explicit_requests = [
            "I want to speak to a human",
            "Let me talk to a real person",
            "Transfer me to an agent",
            "Get me a representative",
            "I need to speak with someone",
            "Connect me to a live agent please",
            "Let me speak to a person please",
            "Can I please get a human on the phone",
        ]

        true_positives = 0
        for message in explicit_requests:
            detector.reset()
            result = detector.analyze(message, language="en")
            if result.should_escalate and result.trigger_type == TriggerType.EXPLICIT_REQUEST:
                true_positives += 1

        true_positive_rate = true_positives / len(explicit_requests)

        # Expect at least 90% true positive rate for explicit requests
        assert true_positive_rate >= 0.9, (
            f"True positive rate {true_positive_rate:.1%} below 90% for explicit requests"
        )

    def test_true_positive_rate_emergencies(
        self, detector: EscalationDetector
    ) -> None:
        """Test that emergencies are detected."""
        emergencies = [
            "This is an emergency",
            "I need help immediately",
            "This is urgent please hurry",
            "Call 911",
            "I need police",
            "Someone needs an ambulance",
        ]

        true_positives = 0
        for message in emergencies:
            detector.reset()
            result = detector.analyze(message, language="en")
            if result.should_escalate and result.trigger_type == TriggerType.EMERGENCY:
                true_positives += 1

        true_positive_rate = true_positives / len(emergencies)

        assert true_positive_rate >= 0.9, (
            f"True positive rate {true_positive_rate:.1%} below 90% for emergencies"
        )
