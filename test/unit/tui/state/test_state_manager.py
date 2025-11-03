"""Tests for ChatStateManager and mutations."""

import pytest
from pydantic_ai.messages import ModelRequest, UserPromptPart

from shotgun.agents.models import AgentType
from shotgun.tui.state import (
    AddQAAnswerMutation,
    ChatState,
    ChatStateManager,
    SetAgentModeMutation,
    SetPartialMessageMutation,
    SetProcessingMutation,
    SetQAModeMutation,
    UpdateIndexingProgressMutation,
    UpdateMessagesMutation,
)


def test_state_manager_initialization():
    """Test that StateManager initializes with default state."""
    manager = ChatStateManager()

    assert manager.state is not None
    assert isinstance(manager.state, ChatState)
    assert manager.state.ui.is_processing is False


def test_state_manager_with_initial_state():
    """Test StateManager with custom initial state."""
    initial = ChatState()
    initial.ui.is_processing = True

    manager = ChatStateManager(initial_state=initial)

    assert manager.state.ui.is_processing is True


def test_set_processing_mutation():
    """Test SetProcessingMutation updates processing state."""
    manager = ChatStateManager()

    mutation = SetProcessingMutation(True, "Thinking...")
    manager.update(mutation)

    assert manager.state.ui.is_processing is True
    assert manager.state.ui.processing_operation == "Thinking..."


def test_set_processing_mutation_stop():
    """Test SetProcessingMutation can stop processing."""
    manager = ChatStateManager()
    manager.update(SetProcessingMutation(True, "Working..."))

    mutation = SetProcessingMutation(False)
    manager.update(mutation)

    assert manager.state.ui.is_processing is False
    assert manager.state.ui.processing_operation is None


def test_set_qa_mode_mutation_enter():
    """Test SetQAModeMutation enters Q&A mode."""
    manager = ChatStateManager()

    questions = ["Question 1?", "Question 2?"]
    mutation = SetQAModeMutation(True, questions=questions)
    manager.update(mutation)

    assert manager.state.ui.qa_mode is True
    assert manager.state.ui.qa_questions == questions
    assert manager.state.ui.qa_current_index == 0
    assert manager.state.ui.qa_answers == []


def test_set_qa_mode_mutation_exit():
    """Test SetQAModeMutation exits Q&A mode and clears state."""
    manager = ChatStateManager()
    # Enter Q&A mode first
    manager.update(SetQAModeMutation(True, questions=["Q1?", "Q2?"]))
    manager.update(AddQAAnswerMutation("Answer 1"))

    # Exit Q&A mode
    mutation = SetQAModeMutation(False)
    manager.update(mutation)

    assert manager.state.ui.qa_mode is False
    assert manager.state.ui.qa_questions == []
    assert manager.state.ui.qa_current_index == 0
    assert manager.state.ui.qa_answers == []


def test_add_qa_answer_mutation():
    """Test AddQAAnswerMutation adds answer and increments index."""
    manager = ChatStateManager()
    manager.update(SetQAModeMutation(True, questions=["Q1?", "Q2?"]))

    mutation = AddQAAnswerMutation("My answer")
    manager.update(mutation)

    assert len(manager.state.ui.qa_answers) == 1
    assert manager.state.ui.qa_answers[0] == "My answer"
    assert manager.state.ui.qa_current_index == 1


def test_set_agent_mode_mutation():
    """Test SetAgentModeMutation changes agent type."""
    manager = ChatStateManager()

    mutation = SetAgentModeMutation(AgentType.TASKS)
    manager.update(mutation)

    assert manager.state.conversation.current_agent == AgentType.TASKS


def test_update_messages_mutation():
    """Test UpdateMessagesMutation updates message history."""
    manager = ChatStateManager()

    messages = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
    ]
    mutation = UpdateMessagesMutation(messages)
    manager.update(mutation)

    assert len(manager.state.conversation.messages) == 1
    assert manager.state.conversation.messages[0] == messages[0]


def test_set_partial_message_mutation():
    """Test SetPartialMessageMutation sets and clears partial message."""
    manager = ChatStateManager()

    message = ModelRequest(parts=[UserPromptPart(content="Partial...")])
    mutation = SetPartialMessageMutation(message)
    manager.update(mutation)

    assert manager.state.ui.partial_message == message

    # Clear partial message
    manager.update(SetPartialMessageMutation(None))
    assert manager.state.ui.partial_message is None


def test_update_indexing_progress_mutation():
    """Test UpdateIndexingProgressMutation updates progress."""
    manager = ChatStateManager()

    mutation = UpdateIndexingProgressMutation(5, 10, "Processing files...")
    manager.update(mutation)

    assert manager.state.indexing.progress_current == 5
    assert manager.state.indexing.progress_total == 10
    assert manager.state.indexing.progress_message == "Processing files..."


def test_state_manager_subscription():
    """Test that subscribers are notified of state changes."""
    manager = ChatStateManager()
    notifications = []

    def callback(old_state, new_state):
        notifications.append((old_state, new_state))

    manager.subscribe(callback)
    manager.update(SetProcessingMutation(True, "Working..."))

    assert len(notifications) == 1
    old, new = notifications[0]
    assert old.ui.is_processing is False
    assert new.ui.is_processing is True


def test_state_manager_multiple_subscribers():
    """Test that multiple subscribers all receive notifications."""
    manager = ChatStateManager()
    calls1 = []
    calls2 = []

    def callback1(old, new):
        calls1.append((old, new))

    def callback2(old, new):
        calls2.append((old, new))

    manager.subscribe(callback1)
    manager.subscribe(callback2)
    manager.update(SetProcessingMutation(True))

    assert len(calls1) == 1
    assert len(calls2) == 1


def test_state_manager_unsubscribe():
    """Test that unsubscribed callbacks are not called."""
    manager = ChatStateManager()
    calls = []

    def callback(old, new):
        calls.append((old, new))

    manager.subscribe(callback)
    manager.update(SetProcessingMutation(True))
    assert len(calls) == 1

    manager.unsubscribe(callback)
    manager.update(SetProcessingMutation(False))
    assert len(calls) == 1  # Should still be 1


def test_mutation_descriptions():
    """Test that all mutations provide useful descriptions."""
    mutations = [
        (SetProcessingMutation(True, "Test"), "Processing started (Test)"),
        (SetProcessingMutation(False), "Processing stopped"),
        (SetQAModeMutation(True, ["Q1?", "Q2?"]), "Entered Q&A mode with 2 questions"),
        (SetQAModeMutation(False), "Exited Q&A mode"),
        (AddQAAnswerMutation("test answer"), "Added Q&A answer (total: 11 chars)"),
        (SetAgentModeMutation(AgentType.TASKS), "Changed agent mode to tasks"),
        (UpdateMessagesMutation([]), "Updated messages (count: 0)"),
        (SetPartialMessageMutation(None), "Cleared partial message"),
        (UpdateIndexingProgressMutation(5, 10), "Indexing progress: 5/10"),
    ]

    for mutation, expected_desc in mutations:
        assert mutation.description() == expected_desc


def test_state_manager_get_state_returns_copy():
    """Test that get_state returns a copy, not the original."""
    manager = ChatStateManager()
    manager.update(SetProcessingMutation(True))

    state_copy = manager.get_state()
    state_copy.ui.is_processing = False

    # Original should not be modified
    assert manager.state.ui.is_processing is True


def test_state_immutability_through_mutations():
    """Test that mutations don't modify the old state."""
    manager = ChatStateManager()
    old_states = []

    def track_old_state(old, new):
        old_states.append(old.model_copy())

    manager.subscribe(track_old_state)

    manager.update(SetProcessingMutation(True))
    manager.update(SetAgentModeMutation(AgentType.TASKS))

    # Verify old states are immutable
    assert old_states[0].ui.is_processing is False
    assert old_states[0].conversation.current_agent == AgentType.RESEARCH
    assert old_states[1].ui.is_processing is True
    assert old_states[1].conversation.current_agent == AgentType.RESEARCH
