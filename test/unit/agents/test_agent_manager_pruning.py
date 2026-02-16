"""Test ui_message_history pruning in AgentManager."""

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from shotgun.agents.agent_manager import AgentManager
from shotgun.agents.conversation.history.constants import MAX_UI_HISTORY_MESSAGES
from shotgun.tui.screens.chat_screen.hint_message import HintMessage
from shotgun.tui.screens.chat_screen.welcome_message import WelcomeMessage


@pytest.fixture
def agent_manager():
    """Create a minimal AgentManager with only the fields needed for pruning."""
    manager = AgentManager.__new__(AgentManager)
    manager.ui_message_history = []
    manager.message_history = []
    manager._sub_agent_messages = []
    manager._stream_state = None
    return manager


def _make_hint(text: str = "hint") -> HintMessage:
    return HintMessage(message=text)


def _make_welcome() -> WelcomeMessage:
    return WelcomeMessage()


def _make_model_request(text: str = "hello") -> ModelRequest:
    return ModelRequest(parts=[UserPromptPart(content=text)])


def _make_model_response(text: str = "response") -> ModelResponse:
    return ModelResponse(parts=[TextPart(content=text)])


def test_no_pruning_when_under_limit(agent_manager):
    """No pruning occurs when message count is at or below MAX_UI_HISTORY_MESSAGES."""
    for i in range(MAX_UI_HISTORY_MESSAGES):
        agent_manager.ui_message_history.append(_make_hint(f"hint-{i}"))

    original_len = len(agent_manager.ui_message_history)
    agent_manager._prune_ui_message_history()
    assert len(agent_manager.ui_message_history) == original_len


def test_pruning_keeps_last_n_messages(agent_manager):
    """Only the last MAX_UI_HISTORY_MESSAGES items are kept."""
    total = MAX_UI_HISTORY_MESSAGES + 20
    for i in range(total):
        agent_manager.ui_message_history.append(_make_model_request(f"msg-{i}"))

    agent_manager._prune_ui_message_history()

    assert len(agent_manager.ui_message_history) == MAX_UI_HISTORY_MESSAGES
    # The kept messages should be the most recent ones
    first_kept = agent_manager.ui_message_history[0]
    assert isinstance(first_kept, ModelRequest)
    assert first_kept.parts[0].content == f"msg-{20}"


def test_pruning_handles_mixed_types(agent_manager):
    """Pruning keeps last N regardless of message type."""
    for i in range(MAX_UI_HISTORY_MESSAGES + 10):
        agent_manager.ui_message_history.append(_make_model_request(f"req-{i}"))
        agent_manager.ui_message_history.append(_make_hint(f"hint-{i}"))
        agent_manager.ui_message_history.append(_make_model_response(f"resp-{i}"))

    agent_manager._prune_ui_message_history()

    assert len(agent_manager.ui_message_history) == MAX_UI_HISTORY_MESSAGES


def test_pruning_preserves_order(agent_manager):
    """After pruning the remaining messages are in original order."""
    items = []
    for i in range(MAX_UI_HISTORY_MESSAGES + 5):
        req = _make_model_request(f"req-{i}")
        resp = _make_model_response(f"resp-{i}")
        items.extend([req, resp])
        agent_manager.ui_message_history.extend([req, resp])

    agent_manager._prune_ui_message_history()

    expected = items[-MAX_UI_HISTORY_MESSAGES:]
    assert agent_manager.ui_message_history == expected


def test_welcome_and_hints_pruned_same_as_model_messages(agent_manager):
    """Welcome and hint messages are pruned the same as model messages."""
    agent_manager.ui_message_history.append(_make_welcome())
    for i in range(MAX_UI_HISTORY_MESSAGES + 5):
        agent_manager.ui_message_history.append(_make_hint(f"hint-{i}"))

    agent_manager._prune_ui_message_history()

    assert len(agent_manager.ui_message_history) == MAX_UI_HISTORY_MESSAGES
    # Welcome message (oldest) should have been dropped
    welcome_count = sum(
        1 for msg in agent_manager.ui_message_history if isinstance(msg, WelcomeMessage)
    )
    assert welcome_count == 0
