# mypy: disable-error-code="attr-defined"
"""Standardized event catalog for ChatScreen.

This module defines all events used in the chat interface, providing:
- Clear event naming conventions
- Type-safe event data
- Documentation for when to use each event
- Consistent patterns across the codebase

Event Design Principles:
1. Events represent "what happened" (past tense)
2. Events contain all data needed by handlers
3. Events are immutable (use Textual Message)
4. Event names follow pattern: [Subject][Action]Event

Command/Query Separation:
- Events (messages): Notify that something happened
- Direct calls: Query for data or issue commands
"""

from textual.message import Message

from shotgun.agents.context_analyzer.models import ContextAnalysis
from shotgun.agents.models import AgentType


class StateChangedEvent(Message):
    """Emitted when ChatState changes.

    Use this event to notify widgets that the overall state has changed.
    Widgets can then query the StateManager for the new state.

    This is a general event - prefer more specific events when available.
    """

    def __init__(self, change_type: str) -> None:
        """Initialize the event.

        Args:
            change_type: Description of what changed (e.g., "processing_started",
                        "mode_changed", "messages_updated").
        """
        super().__init__()
        self.change_type = change_type


class ProcessingStateChangedEvent(Message):
    """Emitted when processing state changes (start/stop).

    Use this event to update UI elements that show processing status
    (spinner, status bar, etc.).

    When to use:
    - Starting/stopping agent execution
    - Starting/stopping compaction
    - Starting/stopping any long-running operation
    """

    def __init__(self, is_processing: bool, operation: str | None = None) -> None:
        """Initialize the event.

        Args:
            is_processing: Whether processing is active.
            operation: Description of the operation (e.g., "Thinking...",
                      "Compacting conversation...").
        """
        super().__init__()
        self.is_processing = is_processing
        self.operation = operation


class ContextAnalysisCompletedEvent(Message):
    """Emitted when context analysis finishes.

    Use this event to update the context indicator widget with fresh data.

    When to use:
    - After message history updates
    - After compaction
    - After model changes
    """

    def __init__(self, analysis: ContextAnalysis | None, model_name: str) -> None:
        """Initialize the event.

        Args:
            analysis: The context analysis result (None if analysis failed).
            model_name: The model name used for analysis.
        """
        super().__init__()
        self.analysis = analysis
        self.model_name = model_name


class AgentModeChangedEvent(Message):
    """Emitted when the agent mode changes.

    Use this event to update UI elements that reflect current mode
    (mode indicator, prompt placeholder, etc.).

    When to use:
    - User switches modes
    - Mode restored from saved conversation
    """

    def __init__(self, old_mode: AgentType, new_mode: AgentType) -> None:
        """Initialize the event.

        Args:
            old_mode: The previous agent mode.
            new_mode: The new agent mode.
        """
        super().__init__()
        self.old_mode = old_mode
        self.new_mode = new_mode


class QAModeChangedEvent(Message):
    """Emitted when Q&A mode is entered or exited.

    Q&A mode is a special state where the user answers clarifying questions
    from the agent.

    When to use:
    - Entering Q&A mode (agent has questions)
    - Exiting Q&A mode (all questions answered or cancelled)
    """

    def __init__(
        self,
        qa_active: bool,
        questions: list[str] | None = None,
        current_index: int = 0,
    ) -> None:
        """Initialize the event.

        Args:
            qa_active: Whether Q&A mode is active.
            questions: The questions to answer (if entering Q&A mode).
            current_index: Current question index.
        """
        super().__init__()
        self.qa_active = qa_active
        self.questions = questions or []
        self.current_index = current_index


class ConversationRestoredEvent(Message):
    """Emitted when conversation is restored from disk.

    Use this event to update UI after conversation restoration.

    When to use:
    - Successfully restored conversation on startup (--continue flag)
    - User manually loads a conversation
    """

    def __init__(self, agent_type: AgentType, message_count: int) -> None:
        """Initialize the event.

        Args:
            agent_type: The restored agent type.
            message_count: Number of messages restored.
        """
        super().__init__()
        self.agent_type = agent_type
        self.message_count = message_count


class ConversationClearedEvent(Message):
    """Emitted when conversation is cleared.

    Use this event to reset UI state when conversation is cleared.

    When to use:
    - User runs /clear command
    - Conversation is compacted (partial clear)
    """

    def __init__(self, full_clear: bool = True) -> None:
        """Initialize the event.

        Args:
            full_clear: True for /clear command, False for compaction.
        """
        super().__init__()
        self.full_clear = full_clear


class OperationCancelledEvent(Message):
    """Emitted when a long-running operation is cancelled.

    Use this event to clean up after user cancels an operation (ESC key).

    When to use:
    - User presses ESC during agent execution
    - User presses ESC during indexing
    - User presses ESC during compaction
    """

    def __init__(self, operation: str) -> None:
        """Initialize the event.

        Args:
            operation: Description of cancelled operation.
        """
        super().__init__()
        self.operation = operation


class ErrorOccurredEvent(Message):
    """Emitted when an error occurs.

    Use this event to show error messages to the user.

    When to use:
    - Agent execution fails
    - File operations fail
    - Network errors
    """

    def __init__(self, error: Exception, operation: str, user_message: str) -> None:
        """Initialize the event.

        Args:
            error: The exception that occurred.
            operation: What operation was being performed.
            user_message: User-friendly error message to display.
        """
        super().__init__()
        self.error = error
        self.operation = operation
        self.user_message = user_message


# Event Usage Guidelines:
#
# 1. When to use events vs direct calls:
#    - Events: Notify that something happened (past tense)
#      Example: ProcessingStateChangedEvent, ContextAnalysisCompletedEvent
#
#    - Direct calls: Query for data or issue commands (present/imperative)
#      Example: agent_manager.run(), state_manager.get_state()
#
# 2. Event naming convention:
#    - [Subject][Action]Event (e.g., ProcessingStateChangedEvent)
#    - Use past tense for actions (Changed, Completed, Cancelled)
#    - Be specific (avoid generic names like "UpdateEvent")
#
# 3. Event data:
#    - Include all data handlers need (avoid forcing handlers to query)
#    - Use type hints for all fields
#    - Document what each field means
#
# 4. Event handlers:
#    - Use @on() decorator for type safety
#    - Keep handlers simple (delegate to services/coordinators)
#    - Don't modify state directly in handlers (use StateManager mutations)
#
# Example usage in ChatScreen:
#
#   # Post an event
#   self.post_message(ProcessingStateChangedEvent(True, "Thinking..."))
#
#   # Handle an event
#   @on(ProcessingStateChangedEvent)
#   def handle_processing_state_changed(self, event: ProcessingStateChangedEvent):
#       self.widget_coordinator.update_for_processing_state(
#           event.is_processing,
#           event.operation
#       )
