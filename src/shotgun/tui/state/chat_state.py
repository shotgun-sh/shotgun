"""Centralized state management for ChatScreen.

This module provides Pydantic models that represent the complete state
of the chat interface, eliminating state duplication and providing a
single source of truth.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field
from pydantic_ai.messages import ModelMessage
from textual.worker import Worker

from shotgun.agents.conversation_history import HintMessage
from shotgun.agents.models import AgentType

if TYPE_CHECKING:
    from pathlib import Path


class UIState(BaseModel):
    """State for UI-specific concerns (processing, Q&A mode, input)."""

    # Processing state
    is_processing: bool = False
    processing_operation: str | None = None
    current_worker: Worker | None = Field(default=None, exclude=True)

    # Q&A mode for clarifying questions
    qa_mode: bool = False
    qa_questions: list[str] = Field(default_factory=list)
    qa_current_index: int = 0
    qa_answers: list[str] = Field(default_factory=list)

    # Partial response during streaming
    partial_message: ModelMessage | None = None

    # Input state
    current_input: str = ""

    model_config = {"arbitrary_types_allowed": True}


class ConversationState(BaseModel):
    """State for conversation and message history."""

    # Message history for UI display
    messages: list[ModelMessage | HintMessage] = Field(default_factory=list)

    # Current agent mode
    current_agent: AgentType = AgentType.RESEARCH

    # Last update timestamp
    updated_at: datetime = Field(default_factory=datetime.now)


class IndexingState(BaseModel):
    """State for codebase indexing operations."""

    # Current indexing job - using Any to avoid circular import
    # Actual type is CodebaseIndexSelection from tui.screens.chat
    job: Any = None

    # Progress tracking
    progress_current: int = 0
    progress_total: int = 0
    progress_message: str = ""


class ChatState(BaseModel):
    """Complete state for ChatScreen.

    This model serves as the single source of truth for all chat-related state.
    Changes to this state should emit events to update the UI.

    Benefits:
    - Single source of truth
    - Easy to serialize for persistence/debugging
    - Eliminates state duplication
    - Can add undo/redo easily
    - Time-travel debugging potential
    """

    ui: UIState = Field(default_factory=UIState)
    conversation: ConversationState = Field(default_factory=ConversationState)
    indexing: IndexingState = Field(default_factory=IndexingState)

    # Version for schema evolution
    version: int = 1

    def model_copy(self, **kwargs: Any) -> "ChatState":
        """Create a deep copy of the state."""
        return super().model_copy(deep=True, **kwargs)
