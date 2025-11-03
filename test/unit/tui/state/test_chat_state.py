"""Tests for ChatState models."""

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart

from shotgun.agents.models import AgentType
from shotgun.tui.state import ChatState, ConversationState, IndexingState, UIState


def test_ui_state_initialization():
    """Test that UIState initializes with correct defaults."""
    ui_state = UIState()

    assert ui_state.is_processing is False
    assert ui_state.processing_operation is None
    assert ui_state.current_worker is None
    assert ui_state.qa_mode is False
    assert ui_state.qa_questions == []
    assert ui_state.qa_current_index == 0
    assert ui_state.qa_answers == []
    assert ui_state.partial_message is None
    assert ui_state.current_input == ""


def test_conversation_state_initialization():
    """Test that ConversationState initializes with correct defaults."""
    conv_state = ConversationState()

    assert conv_state.messages == []
    assert conv_state.current_agent == AgentType.RESEARCH
    assert conv_state.updated_at is not None


def test_indexing_state_initialization():
    """Test that IndexingState initializes with correct defaults."""
    indexing_state = IndexingState()

    assert indexing_state.job is None
    assert indexing_state.progress_current == 0
    assert indexing_state.progress_total == 0
    assert indexing_state.progress_message == ""


def test_chat_state_initialization():
    """Test that ChatState initializes with all sub-states."""
    chat_state = ChatState()

    assert isinstance(chat_state.ui, UIState)
    assert isinstance(chat_state.conversation, ConversationState)
    assert isinstance(chat_state.indexing, IndexingState)
    assert chat_state.version == 1


def test_chat_state_with_custom_substates():
    """Test creating ChatState with custom sub-states."""
    ui = UIState(is_processing=True, processing_operation="Thinking...")
    conv = ConversationState(current_agent=AgentType.TASKS)
    indexing = IndexingState(progress_current=5, progress_total=10)

    chat_state = ChatState(ui=ui, conversation=conv, indexing=indexing)

    assert chat_state.ui.is_processing is True
    assert chat_state.ui.processing_operation == "Thinking..."
    assert chat_state.conversation.current_agent == AgentType.TASKS
    assert chat_state.indexing.progress_current == 5


def test_chat_state_model_copy():
    """Test that model_copy creates a deep copy."""
    original = ChatState()
    original.ui.is_processing = True
    original.conversation.messages.append(
        ModelRequest(parts=[UserPromptPart(content="test")])
    )

    copy = original.model_copy()

    # Verify it's a deep copy
    copy.ui.is_processing = False
    copy.conversation.messages.clear()

    assert original.ui.is_processing is True
    assert len(original.conversation.messages) == 1
    assert copy.ui.is_processing is False
    assert len(copy.conversation.messages) == 0


def test_ui_state_with_qa_mode():
    """Test UIState with Q&A mode active."""
    ui_state = UIState(
        qa_mode=True,
        qa_questions=["Question 1?", "Question 2?"],
        qa_current_index=1,
        qa_answers=["Answer 1"],
    )

    assert ui_state.qa_mode is True
    assert len(ui_state.qa_questions) == 2
    assert ui_state.qa_current_index == 1
    assert len(ui_state.qa_answers) == 1


def test_conversation_state_with_messages():
    """Test ConversationState with actual messages."""
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(parts=[TextPart(content="Hi there!")]),
    ]

    conv_state = ConversationState(messages=messages, current_agent=AgentType.PLAN)

    assert len(conv_state.messages) == 2
    assert conv_state.current_agent == AgentType.PLAN
