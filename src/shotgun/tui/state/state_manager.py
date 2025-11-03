"""State management with mutation tracking and subscriber notifications.

This module implements a state manager that:
1. Maintains the single source of truth (ChatState)
2. Applies mutations to the state
3. Notifies subscribers when state changes
4. Provides logging for debugging
"""

import logging
from collections.abc import Callable
from typing import Protocol

from shotgun.tui.state.chat_state import ChatState

logger = logging.getLogger(__name__)


class StateMutation(Protocol):
    """Protocol for state mutations.

    Mutations are pure functions that take old state and return new state.
    They should not have side effects.
    """

    def apply(self, state: ChatState) -> ChatState:
        """Apply the mutation to the state and return new state."""
        ...

    def description(self) -> str:
        """Return a human-readable description of this mutation."""
        ...


class SetProcessingMutation:
    """Mutation to update processing state."""

    def __init__(self, is_processing: bool, operation: str | None = None):
        self.is_processing = is_processing
        self.operation = operation

    def apply(self, state: ChatState) -> ChatState:
        new_state = state.model_copy()
        new_state.ui.is_processing = self.is_processing
        new_state.ui.processing_operation = self.operation
        return new_state

    def description(self) -> str:
        status = "started" if self.is_processing else "stopped"
        op = f" ({self.operation})" if self.operation else ""
        return f"Processing {status}{op}"


class SetQAModeMutation:
    """Mutation to enter/exit Q&A mode."""

    def __init__(
        self,
        qa_mode: bool,
        questions: list[str] | None = None,
        current_index: int = 0,
    ):
        self.qa_mode = qa_mode
        self.questions = questions or []
        self.current_index = current_index

    def apply(self, state: ChatState) -> ChatState:
        new_state = state.model_copy()
        new_state.ui.qa_mode = self.qa_mode
        if self.qa_mode:
            new_state.ui.qa_questions = self.questions
            new_state.ui.qa_current_index = self.current_index
            new_state.ui.qa_answers = []
        else:
            # Clear Q&A state when exiting
            new_state.ui.qa_questions = []
            new_state.ui.qa_current_index = 0
            new_state.ui.qa_answers = []
        return new_state

    def description(self) -> str:
        if self.qa_mode:
            return f"Entered Q&A mode with {len(self.questions)} questions"
        return "Exited Q&A mode"


class AddQAAnswerMutation:
    """Mutation to add an answer to the Q&A session."""

    def __init__(self, answer: str):
        self.answer = answer

    def apply(self, state: ChatState) -> ChatState:
        new_state = state.model_copy()
        new_state.ui.qa_answers.append(self.answer)
        new_state.ui.qa_current_index += 1
        return new_state

    def description(self) -> str:
        return f"Added Q&A answer (total: {len(self.answer)} chars)"


class SetAgentModeMutation:
    """Mutation to change the current agent mode."""

    def __init__(self, agent_type: "AgentType"):
        self.agent_type = agent_type

    def apply(self, state: ChatState) -> ChatState:
        new_state = state.model_copy()
        new_state.conversation.current_agent = self.agent_type
        return new_state

    def description(self) -> str:
        return f"Changed agent mode to {self.agent_type.value}"


class UpdateMessagesMutation:
    """Mutation to update the message history."""

    def __init__(self, messages: list):
        self.messages = messages

    def apply(self, state: ChatState) -> ChatState:
        new_state = state.model_copy()
        new_state.conversation.messages = self.messages.copy()
        return new_state

    def description(self) -> str:
        return f"Updated messages (count: {len(self.messages)})"


class SetPartialMessageMutation:
    """Mutation to set/clear the partial message during streaming."""

    def __init__(self, message):
        self.message = message

    def apply(self, state: ChatState) -> ChatState:
        new_state = state.model_copy()
        new_state.ui.partial_message = self.message
        return new_state

    def description(self) -> str:
        if self.message:
            return "Set partial message"
        return "Cleared partial message"


class SetIndexingJobMutation:
    """Mutation to set the current indexing job."""

    def __init__(self, job):
        self.job = job

    def apply(self, state: ChatState) -> ChatState:
        new_state = state.model_copy()
        new_state.indexing.job = self.job
        return new_state

    def description(self) -> str:
        if self.job:
            return f"Started indexing job: {self.job}"
        return "Cleared indexing job"


class UpdateIndexingProgressMutation:
    """Mutation to update indexing progress."""

    def __init__(self, current: int, total: int, message: str = ""):
        self.current = current
        self.total = total
        self.message = message

    def apply(self, state: ChatState) -> ChatState:
        new_state = state.model_copy()
        new_state.indexing.progress_current = self.current
        new_state.indexing.progress_total = self.total
        new_state.indexing.progress_message = self.message
        return new_state

    def description(self) -> str:
        return f"Indexing progress: {self.current}/{self.total}"


StateChangeCallback = Callable[[ChatState, ChatState], None]


class ChatStateManager:
    """Manages chat state with mutation tracking and notifications.

    This class provides:
    - Single source of truth for chat state
    - Mutation-based updates (pure functions)
    - Subscriber notifications on state changes
    - Logging for debugging

    Example:
        manager = ChatStateManager()

        # Subscribe to state changes
        def on_state_change(old, new):
            print(f"State changed!")

        manager.subscribe(on_state_change)

        # Update state
        manager.update(SetProcessingMutation(True, "Thinking..."))
    """

    def __init__(self, initial_state: ChatState | None = None):
        """Initialize the state manager.

        Args:
            initial_state: Optional initial state. If not provided, uses default ChatState.
        """
        self.state = initial_state or ChatState()
        self._subscribers: list[StateChangeCallback] = []
        logger.debug("ChatStateManager initialized")

    def update(self, mutation: StateMutation) -> None:
        """Apply a mutation to the state and notify subscribers.

        Args:
            mutation: The mutation to apply.
        """
        old_state = self.state
        new_state = mutation.apply(old_state)

        logger.debug(f"State mutation: {mutation.description()}")

        self.state = new_state
        self._notify_subscribers(old_state, new_state)

    def subscribe(self, callback: StateChangeCallback) -> None:
        """Subscribe to state changes.

        Args:
            callback: Function called with (old_state, new_state) when state changes.
        """
        self._subscribers.append(callback)
        logger.debug(f"Subscriber added (total: {len(self._subscribers)})")

    def unsubscribe(self, callback: StateChangeCallback) -> None:
        """Unsubscribe from state changes.

        Args:
            callback: The callback to remove.
        """
        if callback in self._subscribers:
            self._subscribers.remove(callback)
            logger.debug(f"Subscriber removed (total: {len(self._subscribers)})")

    def _notify_subscribers(self, old_state: ChatState, new_state: ChatState) -> None:
        """Notify all subscribers of state change.

        Args:
            old_state: The previous state.
            new_state: The new state.
        """
        for callback in self._subscribers:
            try:
                callback(old_state, new_state)
            except Exception as e:
                logger.exception(f"Error in state change callback: {e}")

    def get_state(self) -> ChatState:
        """Get the current state.

        Returns:
            A copy of the current state.
        """
        return self.state.model_copy()
