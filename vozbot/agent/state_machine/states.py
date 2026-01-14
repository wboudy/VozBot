"""Call state machine - manages call flow states and transitions.

Implements the state machine for VozBot calls, following the flow:
INIT -> GREET -> LANGUAGE_SELECT -> CLASSIFY_CUSTOMER_TYPE -> INTENT_DISCOVERY ->
INFO_COLLECTION -> CONFIRMATION -> CREATE_CALLBACK_TASK -> TRANSFER_OR_WRAPUP -> END

Each state has defined valid transitions, entry actions, timeouts, and bilingual prompts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine


class CallState(str, Enum):
    """States for the call state machine.

    States follow the call flow from initial pickup to end.
    """

    INIT = "init"
    GREET = "greet"
    LANGUAGE_SELECT = "language_select"
    CLASSIFY_CUSTOMER_TYPE = "classify_customer_type"
    INTENT_DISCOVERY = "intent_discovery"
    INFO_COLLECTION = "info_collection"
    CONFIRMATION = "confirmation"
    CREATE_CALLBACK_TASK = "create_callback_task"
    TRANSFER_OR_WRAPUP = "transfer_or_wrapup"
    END = "end"
    # Error/terminal states
    ERROR = "error"
    TIMEOUT = "timeout"


# Type alias for entry action coroutines
EntryAction = Callable[[Any], Coroutine[Any, Any, None]]


@dataclass
class StateConfig:
    """Configuration for a state in the state machine.

    Attributes:
        state: The state this config is for.
        valid_transitions: States that can be transitioned to from this state.
        timeout_seconds: How long before timing out in this state.
        timeout_target: State to transition to on timeout.
        entry_action: Optional async function called when entering state.
        prompts: Bilingual prompts for this state (en, es).
    """

    state: CallState
    valid_transitions: list[CallState]
    timeout_seconds: float = 30.0
    timeout_target: CallState = CallState.ERROR
    entry_action: EntryAction | None = None
    prompts: dict[str, str] = field(default_factory=dict)


# Bilingual prompts for each state
STATE_PROMPTS: dict[CallState, dict[str, str]] = {
    CallState.INIT: {
        "en": "",  # No prompt - system initialization
        "es": "",
    },
    CallState.GREET: {
        "en": "Hello! Thank you for calling. I'm an AI assistant and I'll help connect you with the right person.",
        "es": "Hola! Gracias por llamar. Soy un asistente de inteligencia artificial y le ayudare a conectarse con la persona adecuada.",
    },
    CallState.LANGUAGE_SELECT: {
        "en": "Would you like to continue in English or Spanish? Para espanol, diga 'espanol'.",
        "es": "Desea continuar en espanol o ingles? For English, say 'English'.",
    },
    CallState.CLASSIFY_CUSTOMER_TYPE: {
        "en": "Are you an existing customer, or is this your first time calling us?",
        "es": "Es usted un cliente existente, o es la primera vez que nos llama?",
    },
    CallState.INTENT_DISCOVERY: {
        "en": "How can I help you today? Please tell me what you're calling about.",
        "es": "Como puedo ayudarle hoy? Por favor digame el motivo de su llamada.",
    },
    CallState.INFO_COLLECTION: {
        "en": "I'd like to collect some information so we can assist you better.",
        "es": "Me gustaria recopilar alguna informacion para poder asistirle mejor.",
    },
    CallState.CONFIRMATION: {
        "en": "Let me confirm the information I have. Is this correct?",
        "es": "Permitame confirmar la informacion que tengo. Es correcto?",
    },
    CallState.CREATE_CALLBACK_TASK: {
        "en": "I'm creating a callback request. Someone will call you back shortly.",
        "es": "Estoy creando una solicitud de devolucion de llamada. Alguien le llamara pronto.",
    },
    CallState.TRANSFER_OR_WRAPUP: {
        "en": "I'm transferring you now. Please hold.",
        "es": "Le estoy transfiriendo ahora. Por favor espere.",
    },
    CallState.END: {
        "en": "Thank you for calling. Have a great day!",
        "es": "Gracias por llamar. Que tenga un buen dia!",
    },
    CallState.ERROR: {
        "en": "I apologize, but I encountered an issue. Let me connect you with someone who can help.",
        "es": "Disculpe, pero encontre un problema. Permitame conectarle con alguien que pueda ayudarle.",
    },
    CallState.TIMEOUT: {
        "en": "I haven't heard from you. If you need more time, please let me know.",
        "es": "No le he escuchado. Si necesita mas tiempo, por favor hagamelo saber.",
    },
}

# State machine transition definitions
STATE_CONFIGS: dict[CallState, StateConfig] = {
    CallState.INIT: StateConfig(
        state=CallState.INIT,
        valid_transitions=[CallState.GREET, CallState.ERROR],
        timeout_seconds=5.0,
        timeout_target=CallState.GREET,
        prompts=STATE_PROMPTS[CallState.INIT],
    ),
    CallState.GREET: StateConfig(
        state=CallState.GREET,
        valid_transitions=[CallState.LANGUAGE_SELECT, CallState.ERROR],
        timeout_seconds=10.0,
        timeout_target=CallState.LANGUAGE_SELECT,
        prompts=STATE_PROMPTS[CallState.GREET],
    ),
    CallState.LANGUAGE_SELECT: StateConfig(
        state=CallState.LANGUAGE_SELECT,
        valid_transitions=[CallState.CLASSIFY_CUSTOMER_TYPE, CallState.GREET, CallState.ERROR],
        timeout_seconds=15.0,
        timeout_target=CallState.CLASSIFY_CUSTOMER_TYPE,  # Default to English on timeout
        prompts=STATE_PROMPTS[CallState.LANGUAGE_SELECT],
    ),
    CallState.CLASSIFY_CUSTOMER_TYPE: StateConfig(
        state=CallState.CLASSIFY_CUSTOMER_TYPE,
        valid_transitions=[CallState.INTENT_DISCOVERY, CallState.LANGUAGE_SELECT, CallState.ERROR],
        timeout_seconds=20.0,
        timeout_target=CallState.INTENT_DISCOVERY,
        prompts=STATE_PROMPTS[CallState.CLASSIFY_CUSTOMER_TYPE],
    ),
    CallState.INTENT_DISCOVERY: StateConfig(
        state=CallState.INTENT_DISCOVERY,
        valid_transitions=[
            CallState.INFO_COLLECTION,
            CallState.CONFIRMATION,
            CallState.TRANSFER_OR_WRAPUP,
            CallState.CLASSIFY_CUSTOMER_TYPE,
            CallState.ERROR,
        ],
        timeout_seconds=60.0,
        timeout_target=CallState.TIMEOUT,
        prompts=STATE_PROMPTS[CallState.INTENT_DISCOVERY],
    ),
    CallState.INFO_COLLECTION: StateConfig(
        state=CallState.INFO_COLLECTION,
        valid_transitions=[
            CallState.CONFIRMATION,
            CallState.INTENT_DISCOVERY,
            CallState.ERROR,
        ],
        timeout_seconds=60.0,
        timeout_target=CallState.TIMEOUT,
        prompts=STATE_PROMPTS[CallState.INFO_COLLECTION],
    ),
    CallState.CONFIRMATION: StateConfig(
        state=CallState.CONFIRMATION,
        valid_transitions=[
            CallState.CREATE_CALLBACK_TASK,
            CallState.TRANSFER_OR_WRAPUP,
            CallState.INFO_COLLECTION,
            CallState.ERROR,
        ],
        timeout_seconds=30.0,
        timeout_target=CallState.CREATE_CALLBACK_TASK,
        prompts=STATE_PROMPTS[CallState.CONFIRMATION],
    ),
    CallState.CREATE_CALLBACK_TASK: StateConfig(
        state=CallState.CREATE_CALLBACK_TASK,
        valid_transitions=[CallState.TRANSFER_OR_WRAPUP, CallState.END, CallState.ERROR],
        timeout_seconds=10.0,
        timeout_target=CallState.END,
        prompts=STATE_PROMPTS[CallState.CREATE_CALLBACK_TASK],
    ),
    CallState.TRANSFER_OR_WRAPUP: StateConfig(
        state=CallState.TRANSFER_OR_WRAPUP,
        valid_transitions=[CallState.END, CallState.ERROR],
        timeout_seconds=30.0,
        timeout_target=CallState.END,
        prompts=STATE_PROMPTS[CallState.TRANSFER_OR_WRAPUP],
    ),
    CallState.END: StateConfig(
        state=CallState.END,
        valid_transitions=[],  # Terminal state
        timeout_seconds=0.0,
        prompts=STATE_PROMPTS[CallState.END],
    ),
    CallState.ERROR: StateConfig(
        state=CallState.ERROR,
        valid_transitions=[CallState.TRANSFER_OR_WRAPUP, CallState.END],
        timeout_seconds=10.0,
        timeout_target=CallState.END,
        prompts=STATE_PROMPTS[CallState.ERROR],
    ),
    CallState.TIMEOUT: StateConfig(
        state=CallState.TIMEOUT,
        valid_transitions=[CallState.END, CallState.ERROR],
        timeout_seconds=10.0,
        timeout_target=CallState.END,
        prompts=STATE_PROMPTS[CallState.TIMEOUT],
    ),
}


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, from_state: CallState, to_state: CallState) -> None:
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"Invalid transition from {from_state.value} to {to_state.value}"
        )


class StateMachine:
    """Manages call state transitions and enforces valid flows.

    The state machine starts in INIT state and progresses through
    the call flow. It enforces that only valid transitions are made
    and persists state for call session tracking.

    Attributes:
        current_state: The current state of the call.
        call_id: The ID of the call this state machine is managing.
        language: The language selected for the call (en/es).
        history: List of (from_state, to_state) transitions.
    """

    def __init__(self, call_id: str, initial_state: CallState = CallState.INIT) -> None:
        """Initialize the state machine.

        Args:
            call_id: The ID of the call to manage.
            initial_state: Starting state (default INIT).
        """
        self._current_state = initial_state
        self._call_id = call_id
        self._language: str = "en"  # Default to English
        self._history: list[tuple[CallState, CallState]] = []
        self._context: dict[str, Any] = {}

    @property
    def current_state(self) -> CallState:
        """Get the current state."""
        return self._current_state

    @property
    def call_id(self) -> str:
        """Get the call ID."""
        return self._call_id

    @property
    def language(self) -> str:
        """Get the selected language."""
        return self._language

    @language.setter
    def language(self, value: str) -> None:
        """Set the language (en or es)."""
        if value not in ("en", "es"):
            raise ValueError(f"Invalid language: {value}. Must be 'en' or 'es'.")
        self._language = value

    @property
    def history(self) -> list[tuple[CallState, CallState]]:
        """Get the transition history."""
        return self._history.copy()

    @property
    def context(self) -> dict[str, Any]:
        """Get the context dict for storing state-specific data."""
        return self._context

    def can_transition_to(self, target_state: CallState) -> bool:
        """Check if a transition to the target state is valid.

        Args:
            target_state: The state to check.

        Returns:
            True if the transition is valid, False otherwise.
        """
        config = STATE_CONFIGS.get(self._current_state)
        if config is None:
            return False
        return target_state in config.valid_transitions

    def get_valid_transitions(self) -> list[CallState]:
        """Get list of valid states to transition to.

        Returns:
            List of valid target states from current state.
        """
        config = STATE_CONFIGS.get(self._current_state)
        if config is None:
            return []
        return config.valid_transitions.copy()

    def transition_to(self, target_state: CallState) -> None:
        """Transition to a new state.

        Args:
            target_state: The state to transition to.

        Raises:
            InvalidTransitionError: If the transition is not valid.
        """
        if not self.can_transition_to(target_state):
            raise InvalidTransitionError(self._current_state, target_state)

        self._history.append((self._current_state, target_state))
        self._current_state = target_state

    def get_current_prompt(self) -> str:
        """Get the prompt for the current state in the selected language.

        Returns:
            The prompt string for the current state.
        """
        config = STATE_CONFIGS.get(self._current_state)
        if config is None or not config.prompts:
            return ""
        return config.prompts.get(self._language, config.prompts.get("en", ""))

    def get_timeout(self) -> float:
        """Get the timeout for the current state.

        Returns:
            Timeout in seconds.
        """
        config = STATE_CONFIGS.get(self._current_state)
        if config is None:
            return 30.0
        return config.timeout_seconds

    def handle_timeout(self) -> CallState:
        """Handle a timeout in the current state.

        Transitions to the timeout target state if defined.

        Returns:
            The new state after handling timeout.
        """
        config = STATE_CONFIGS.get(self._current_state)
        if config is None:
            self.transition_to(CallState.ERROR)
            return CallState.ERROR

        target = config.timeout_target
        # Force transition even if not strictly valid (timeout is special)
        self._history.append((self._current_state, target))
        self._current_state = target
        return target

    def is_terminal(self) -> bool:
        """Check if the current state is terminal (no valid transitions).

        Returns:
            True if no more transitions are possible.
        """
        return len(self.get_valid_transitions()) == 0

    def reset(self) -> None:
        """Reset the state machine to INIT state."""
        self._current_state = CallState.INIT
        self._history.clear()
        self._context.clear()
        self._language = "en"

    def to_dict(self) -> dict[str, Any]:
        """Serialize state machine to dict for persistence.

        Returns:
            Dict representation of state machine.
        """
        return {
            "call_id": self._call_id,
            "current_state": self._current_state.value,
            "language": self._language,
            "history": [(f.value, t.value) for f, t in self._history],
            "context": self._context,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StateMachine:
        """Deserialize state machine from dict.

        Args:
            data: Dict representation of state machine.

        Returns:
            Restored StateMachine instance.
        """
        sm = cls(
            call_id=data["call_id"],
            initial_state=CallState(data["current_state"]),
        )
        sm._language = data.get("language", "en")
        sm._history = [
            (CallState(f), CallState(t)) for f, t in data.get("history", [])
        ]
        sm._context = data.get("context", {})
        return sm
