"""Tests for call state machine.

Verifies:
- State enum values
- StateMachine transitions
- Invalid transition prevention
- Bilingual prompts per state
- 100% state transition coverage
"""

from __future__ import annotations

import pytest

from vozbot.agent.state_machine.states import (
    CallState,
    InvalidTransitionError,
    STATE_CONFIGS,
    STATE_PROMPTS,
    StateConfig,
    StateMachine,
)


class TestCallStateEnum:
    """Tests for CallState enum."""

    def test_all_states_defined(self) -> None:
        """Verify all required states are defined."""
        required_states = [
            "INIT",
            "GREET",
            "LANGUAGE_SELECT",
            "CLASSIFY_CUSTOMER_TYPE",
            "INTENT_DISCOVERY",
            "INFO_COLLECTION",
            "CONFIRMATION",
            "CREATE_CALLBACK_TASK",
            "TRANSFER_OR_WRAPUP",
            "END",
            "ERROR",
            "TIMEOUT",
        ]
        for state_name in required_states:
            assert hasattr(CallState, state_name), f"Missing state: {state_name}"

    def test_state_values(self) -> None:
        """Test state values are correct."""
        assert CallState.INIT.value == "init"
        assert CallState.GREET.value == "greet"
        assert CallState.LANGUAGE_SELECT.value == "language_select"
        assert CallState.END.value == "end"


class TestStateConfig:
    """Tests for StateConfig dataclass."""

    def test_create_state_config(self) -> None:
        """Test creating a state config."""
        config = StateConfig(
            state=CallState.INIT,
            valid_transitions=[CallState.GREET, CallState.ERROR],
            timeout_seconds=5.0,
            timeout_target=CallState.GREET,
            prompts={"en": "Hello", "es": "Hola"},
        )
        assert config.state == CallState.INIT
        assert CallState.GREET in config.valid_transitions
        assert config.timeout_seconds == 5.0

    def test_all_states_have_config(self) -> None:
        """Verify every state has a config defined."""
        for state in CallState:
            assert state in STATE_CONFIGS, f"Missing config for state: {state}"


class TestStateMachine:
    """Tests for StateMachine class."""

    def test_initial_state(self) -> None:
        """Test state machine starts in INIT state."""
        sm = StateMachine(call_id="test-123")
        assert sm.current_state == CallState.INIT
        assert sm.call_id == "test-123"

    def test_custom_initial_state(self) -> None:
        """Test state machine can start in custom state."""
        sm = StateMachine(call_id="test-123", initial_state=CallState.GREET)
        assert sm.current_state == CallState.GREET

    def test_valid_transition(self) -> None:
        """Test valid state transition succeeds."""
        sm = StateMachine(call_id="test-123")
        assert sm.can_transition_to(CallState.GREET)
        sm.transition_to(CallState.GREET)
        assert sm.current_state == CallState.GREET

    def test_invalid_transition_raises(self) -> None:
        """Test invalid state transition raises error."""
        sm = StateMachine(call_id="test-123")
        # Cannot go from INIT to END directly
        assert not sm.can_transition_to(CallState.END)
        with pytest.raises(InvalidTransitionError) as exc_info:
            sm.transition_to(CallState.END)
        assert exc_info.value.from_state == CallState.INIT
        assert exc_info.value.to_state == CallState.END

    def test_transition_history(self) -> None:
        """Test transition history is recorded."""
        sm = StateMachine(call_id="test-123")
        sm.transition_to(CallState.GREET)
        sm.transition_to(CallState.LANGUAGE_SELECT)

        history = sm.history
        assert len(history) == 2
        assert history[0] == (CallState.INIT, CallState.GREET)
        assert history[1] == (CallState.GREET, CallState.LANGUAGE_SELECT)

    def test_get_valid_transitions(self) -> None:
        """Test getting list of valid transitions."""
        sm = StateMachine(call_id="test-123")
        valid = sm.get_valid_transitions()
        assert CallState.GREET in valid
        assert CallState.ERROR in valid

    def test_language_property(self) -> None:
        """Test language property getter/setter."""
        sm = StateMachine(call_id="test-123")
        assert sm.language == "en"  # Default

        sm.language = "es"
        assert sm.language == "es"

    def test_invalid_language_raises(self) -> None:
        """Test invalid language raises error."""
        sm = StateMachine(call_id="test-123")
        with pytest.raises(ValueError, match="Invalid language"):
            sm.language = "fr"

    def test_get_current_prompt_english(self) -> None:
        """Test getting prompt in English."""
        sm = StateMachine(call_id="test-123")
        sm.transition_to(CallState.GREET)
        prompt = sm.get_current_prompt()
        assert "Hello" in prompt or "Thank you" in prompt

    def test_get_current_prompt_spanish(self) -> None:
        """Test getting prompt in Spanish."""
        sm = StateMachine(call_id="test-123")
        sm.language = "es"
        sm.transition_to(CallState.GREET)
        prompt = sm.get_current_prompt()
        assert "Hola" in prompt or "Gracias" in prompt

    def test_get_timeout(self) -> None:
        """Test getting timeout for current state."""
        sm = StateMachine(call_id="test-123")
        timeout = sm.get_timeout()
        assert timeout > 0

    def test_handle_timeout(self) -> None:
        """Test timeout handling transitions to correct state."""
        sm = StateMachine(call_id="test-123")
        # INIT times out to GREET
        new_state = sm.handle_timeout()
        assert new_state == CallState.GREET
        assert sm.current_state == CallState.GREET

    def test_is_terminal_false(self) -> None:
        """Test is_terminal returns False for non-terminal state."""
        sm = StateMachine(call_id="test-123")
        assert sm.is_terminal() is False

    def test_is_terminal_true(self) -> None:
        """Test is_terminal returns True for END state."""
        sm = StateMachine(call_id="test-123", initial_state=CallState.END)
        assert sm.is_terminal() is True

    def test_reset(self) -> None:
        """Test reset returns to initial state."""
        sm = StateMachine(call_id="test-123")
        sm.transition_to(CallState.GREET)
        sm.language = "es"
        sm.context["key"] = "value"

        sm.reset()
        assert sm.current_state == CallState.INIT
        assert sm.language == "en"
        assert len(sm.history) == 0
        assert len(sm.context) == 0

    def test_to_dict(self) -> None:
        """Test serialization to dict."""
        sm = StateMachine(call_id="test-123")
        sm.transition_to(CallState.GREET)
        sm.language = "es"
        sm.context["customer_name"] = "Juan"

        data = sm.to_dict()
        assert data["call_id"] == "test-123"
        assert data["current_state"] == "greet"
        assert data["language"] == "es"
        assert len(data["history"]) == 1
        assert data["context"]["customer_name"] == "Juan"

    def test_from_dict(self) -> None:
        """Test deserialization from dict."""
        data = {
            "call_id": "test-456",
            "current_state": "intent_discovery",
            "language": "es",
            "history": [("init", "greet"), ("greet", "language_select")],
            "context": {"intent": "billing question"},
        }
        sm = StateMachine.from_dict(data)
        assert sm.call_id == "test-456"
        assert sm.current_state == CallState.INTENT_DISCOVERY
        assert sm.language == "es"
        assert len(sm.history) == 2
        assert sm.context["intent"] == "billing question"

    def test_context_property(self) -> None:
        """Test context property for storing state data."""
        sm = StateMachine(call_id="test-123")
        sm.context["customer_type"] = "existing"
        sm.context["intent"] = "billing"
        assert sm.context["customer_type"] == "existing"
        assert sm.context["intent"] == "billing"


class TestStatePrompts:
    """Tests for bilingual state prompts."""

    def test_all_states_have_prompts(self) -> None:
        """Verify every state has prompts defined."""
        for state in CallState:
            assert state in STATE_PROMPTS, f"Missing prompts for state: {state}"

    def test_all_prompts_are_bilingual(self) -> None:
        """Verify every state has both English and Spanish prompts."""
        for state, prompts in STATE_PROMPTS.items():
            assert "en" in prompts, f"Missing English prompt for {state}"
            assert "es" in prompts, f"Missing Spanish prompt for {state}"


class TestStateTransitionCoverage:
    """Test 100% coverage of all state transitions."""

    @pytest.mark.parametrize(
        "from_state,to_state",
        [
            # INIT transitions
            (CallState.INIT, CallState.GREET),
            (CallState.INIT, CallState.ERROR),
            # GREET transitions
            (CallState.GREET, CallState.LANGUAGE_SELECT),
            (CallState.GREET, CallState.ERROR),
            # LANGUAGE_SELECT transitions
            (CallState.LANGUAGE_SELECT, CallState.CLASSIFY_CUSTOMER_TYPE),
            (CallState.LANGUAGE_SELECT, CallState.GREET),
            (CallState.LANGUAGE_SELECT, CallState.ERROR),
            # CLASSIFY_CUSTOMER_TYPE transitions
            (CallState.CLASSIFY_CUSTOMER_TYPE, CallState.INTENT_DISCOVERY),
            (CallState.CLASSIFY_CUSTOMER_TYPE, CallState.LANGUAGE_SELECT),
            (CallState.CLASSIFY_CUSTOMER_TYPE, CallState.ERROR),
            # INTENT_DISCOVERY transitions
            (CallState.INTENT_DISCOVERY, CallState.INFO_COLLECTION),
            (CallState.INTENT_DISCOVERY, CallState.CONFIRMATION),
            (CallState.INTENT_DISCOVERY, CallState.TRANSFER_OR_WRAPUP),
            (CallState.INTENT_DISCOVERY, CallState.CLASSIFY_CUSTOMER_TYPE),
            (CallState.INTENT_DISCOVERY, CallState.ERROR),
            # INFO_COLLECTION transitions
            (CallState.INFO_COLLECTION, CallState.CONFIRMATION),
            (CallState.INFO_COLLECTION, CallState.INTENT_DISCOVERY),
            (CallState.INFO_COLLECTION, CallState.ERROR),
            # CONFIRMATION transitions
            (CallState.CONFIRMATION, CallState.CREATE_CALLBACK_TASK),
            (CallState.CONFIRMATION, CallState.TRANSFER_OR_WRAPUP),
            (CallState.CONFIRMATION, CallState.INFO_COLLECTION),
            (CallState.CONFIRMATION, CallState.ERROR),
            # CREATE_CALLBACK_TASK transitions
            (CallState.CREATE_CALLBACK_TASK, CallState.TRANSFER_OR_WRAPUP),
            (CallState.CREATE_CALLBACK_TASK, CallState.END),
            (CallState.CREATE_CALLBACK_TASK, CallState.ERROR),
            # TRANSFER_OR_WRAPUP transitions
            (CallState.TRANSFER_OR_WRAPUP, CallState.END),
            (CallState.TRANSFER_OR_WRAPUP, CallState.ERROR),
            # ERROR transitions
            (CallState.ERROR, CallState.TRANSFER_OR_WRAPUP),
            (CallState.ERROR, CallState.END),
            # TIMEOUT transitions
            (CallState.TIMEOUT, CallState.END),
            (CallState.TIMEOUT, CallState.ERROR),
        ],
    )
    def test_valid_transition(self, from_state: CallState, to_state: CallState) -> None:
        """Test each valid state transition."""
        sm = StateMachine(call_id="test", initial_state=from_state)
        assert sm.can_transition_to(to_state), f"Should allow {from_state} -> {to_state}"
        sm.transition_to(to_state)
        assert sm.current_state == to_state

    def test_end_state_has_no_transitions(self) -> None:
        """Test END state is terminal."""
        sm = StateMachine(call_id="test", initial_state=CallState.END)
        assert len(sm.get_valid_transitions()) == 0
        assert sm.is_terminal()


class TestInvalidTransitions:
    """Tests for invalid state transitions."""

    @pytest.mark.parametrize(
        "from_state,to_state",
        [
            # Cannot skip from INIT to most states
            (CallState.INIT, CallState.END),
            (CallState.INIT, CallState.CONFIRMATION),
            (CallState.INIT, CallState.INTENT_DISCOVERY),
            # Cannot go backwards inappropriately
            (CallState.END, CallState.INIT),
            (CallState.END, CallState.GREET),
            # Cannot skip major states
            (CallState.GREET, CallState.CONFIRMATION),
            (CallState.GREET, CallState.CREATE_CALLBACK_TASK),
        ],
    )
    def test_invalid_transition_raises(
        self, from_state: CallState, to_state: CallState
    ) -> None:
        """Test invalid transitions raise error."""
        sm = StateMachine(call_id="test", initial_state=from_state)
        assert not sm.can_transition_to(to_state)
        with pytest.raises(InvalidTransitionError):
            sm.transition_to(to_state)


class TestCompleteCallFlow:
    """Test complete call flows from start to end."""

    def test_happy_path_with_callback(self) -> None:
        """Test successful call flow ending with callback task."""
        sm = StateMachine(call_id="test-flow")

        # Full happy path
        states = [
            CallState.GREET,
            CallState.LANGUAGE_SELECT,
            CallState.CLASSIFY_CUSTOMER_TYPE,
            CallState.INTENT_DISCOVERY,
            CallState.INFO_COLLECTION,
            CallState.CONFIRMATION,
            CallState.CREATE_CALLBACK_TASK,
            CallState.END,
        ]

        for state in states:
            sm.transition_to(state)
            assert sm.current_state == state

        assert sm.is_terminal()
        assert len(sm.history) == 8

    def test_flow_with_transfer(self) -> None:
        """Test call flow ending with transfer."""
        sm = StateMachine(call_id="test-transfer")

        sm.transition_to(CallState.GREET)
        sm.transition_to(CallState.LANGUAGE_SELECT)
        sm.transition_to(CallState.CLASSIFY_CUSTOMER_TYPE)
        sm.transition_to(CallState.INTENT_DISCOVERY)
        sm.transition_to(CallState.TRANSFER_OR_WRAPUP)  # Direct to transfer
        sm.transition_to(CallState.END)

        assert sm.is_terminal()

    def test_flow_with_error_recovery(self) -> None:
        """Test call flow with error and recovery."""
        sm = StateMachine(call_id="test-error")

        sm.transition_to(CallState.GREET)
        sm.transition_to(CallState.ERROR)  # Something went wrong
        sm.transition_to(CallState.TRANSFER_OR_WRAPUP)  # Transfer to human
        sm.transition_to(CallState.END)

        assert sm.is_terminal()
        # Check error was recorded in history
        assert any(t[1] == CallState.ERROR for t in sm.history)
