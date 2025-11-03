"""Event definitions for TUI."""

from shotgun.tui.events.chat_events import (
    AgentModeChangedEvent,
    ContextAnalysisCompletedEvent,
    ConversationClearedEvent,
    ConversationRestoredEvent,
    ErrorOccurredEvent,
    OperationCancelledEvent,
    ProcessingStateChangedEvent,
    QAModeChangedEvent,
    StateChangedEvent,
)

__all__ = [
    "StateChangedEvent",
    "ProcessingStateChangedEvent",
    "ContextAnalysisCompletedEvent",
    "AgentModeChangedEvent",
    "QAModeChangedEvent",
    "ConversationRestoredEvent",
    "ConversationClearedEvent",
    "OperationCancelledEvent",
    "ErrorOccurredEvent",
]
