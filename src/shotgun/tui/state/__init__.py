"""State management utilities for TUI."""

from .chat_state import ChatState, ConversationState, IndexingState, UIState
from .processing_state import ProcessingStateManager
from .state_manager import (
    AddQAAnswerMutation,
    ChatStateManager,
    SetAgentModeMutation,
    SetIndexingJobMutation,
    SetPartialMessageMutation,
    SetProcessingMutation,
    SetQAModeMutation,
    StateMutation,
    UpdateIndexingProgressMutation,
    UpdateMessagesMutation,
)

__all__ = [
    # Legacy processing state (Phase 1)
    "ProcessingStateManager",
    # Phase 2 state models
    "ChatState",
    "UIState",
    "ConversationState",
    "IndexingState",
    # State manager
    "ChatStateManager",
    "StateMutation",
    # Mutations
    "SetProcessingMutation",
    "SetQAModeMutation",
    "AddQAAnswerMutation",
    "SetAgentModeMutation",
    "UpdateMessagesMutation",
    "SetPartialMessageMutation",
    "SetIndexingJobMutation",
    "UpdateIndexingProgressMutation",
]
