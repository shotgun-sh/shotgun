"""Test ui_message_history pruning in AgentManager."""

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from shotgun.agents.agent_manager import AgentManager
from shotgun.agents.conversation.history.constants import MAX_UI_HINT_MESSAGES
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
    """No pruning occurs when hint count is at or below MAX_UI_HINT_MESSAGES."""
    for i in range(MAX_UI_HINT_MESSAGES):
        agent_manager.ui_message_history.append(_make_hint(f"hint-{i}"))
    agent_manager.ui_message_history.append(_make_model_request())

    original_len = len(agent_manager.ui_message_history)
    agent_manager._prune_ui_message_history()
    assert len(agent_manager.ui_message_history) == original_len


def test_pruning_removes_oldest_hints(agent_manager):
    """Oldest HintMessages are removed when over the limit."""
    total_hints = MAX_UI_HINT_MESSAGES + 20
    for i in range(total_hints):
        agent_manager.ui_message_history.append(_make_hint(f"hint-{i}"))

    agent_manager._prune_ui_message_history()

    remaining_hints = [
        msg for msg in agent_manager.ui_message_history if isinstance(msg, HintMessage)
    ]
    assert len(remaining_hints) == MAX_UI_HINT_MESSAGES
    # The kept hints should be the most recent ones
    assert remaining_hints[0].message == f"hint-{20}"
    assert remaining_hints[-1].message == f"hint-{total_hints - 1}"


def test_pruning_preserves_all_model_messages(agent_manager):
    """All ModelMessage entries are preserved during pruning."""
    for i in range(MAX_UI_HINT_MESSAGES + 30):
        agent_manager.ui_message_history.append(_make_hint(f"hint-{i}"))
        if i % 5 == 0:
            agent_manager.ui_message_history.append(_make_model_request(f"req-{i}"))
            agent_manager.ui_message_history.append(_make_model_response(f"resp-{i}"))

    model_msgs_before = [
        msg
        for msg in agent_manager.ui_message_history
        if isinstance(msg, (ModelRequest, ModelResponse))
    ]

    agent_manager._prune_ui_message_history()

    model_msgs_after = [
        msg
        for msg in agent_manager.ui_message_history
        if isinstance(msg, (ModelRequest, ModelResponse))
    ]
    assert len(model_msgs_after) == len(model_msgs_before)
    assert model_msgs_after == model_msgs_before


def test_pruning_preserves_most_recent_hints(agent_manager):
    """The most recent MAX_UI_HINT_MESSAGES hints are kept."""
    total_hints = MAX_UI_HINT_MESSAGES + 10
    for i in range(total_hints):
        agent_manager.ui_message_history.append(_make_hint(f"hint-{i}"))

    agent_manager._prune_ui_message_history()

    remaining = [
        msg for msg in agent_manager.ui_message_history if isinstance(msg, HintMessage)
    ]
    expected_start = total_hints - MAX_UI_HINT_MESSAGES
    for idx, msg in enumerate(remaining):
        assert msg.message == f"hint-{expected_start + idx}"


def test_pruning_handles_mixed_ordering(agent_manager):
    """Correctly handles interleaved hints, welcomes, and model messages."""
    agent_manager.ui_message_history.append(_make_welcome())
    for i in range(MAX_UI_HINT_MESSAGES + 5):
        agent_manager.ui_message_history.append(_make_model_request(f"req-{i}"))
        agent_manager.ui_message_history.append(_make_hint(f"hint-{i}"))
        agent_manager.ui_message_history.append(_make_model_response(f"resp-{i}"))

    agent_manager._prune_ui_message_history()

    hint_welcome_count = sum(
        1
        for msg in agent_manager.ui_message_history
        if isinstance(msg, (HintMessage, WelcomeMessage))
    )
    assert hint_welcome_count == MAX_UI_HINT_MESSAGES


def test_welcome_messages_count_toward_limit(agent_manager):
    """WelcomeMessage objects are counted and pruned alongside HintMessages."""
    for _ in range(5):
        agent_manager.ui_message_history.append(_make_welcome())
    for i in range(MAX_UI_HINT_MESSAGES):
        agent_manager.ui_message_history.append(_make_hint(f"hint-{i}"))

    agent_manager._prune_ui_message_history()

    hint_welcome_count = sum(
        1
        for msg in agent_manager.ui_message_history
        if isinstance(msg, (HintMessage, WelcomeMessage))
    )
    assert hint_welcome_count == MAX_UI_HINT_MESSAGES
    # The oldest messages (the welcome messages) should be removed
    welcome_count = sum(
        1 for msg in agent_manager.ui_message_history if isinstance(msg, WelcomeMessage)
    )
    assert welcome_count == 0
