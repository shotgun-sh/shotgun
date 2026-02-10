"""Tests for ChatHistory widget."""

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart

from shotgun.tui.screens.chat_screen.history.agent_response import AgentResponseWidget
from shotgun.tui.screens.chat_screen.history.chat_history import ChatHistory
from shotgun.tui.screens.chat_screen.history.partial_response import (
    PartialResponseWidget,
)


class MockWidget:
    """Mock widget that tracks removal state."""

    def __init__(self):
        self.removed = False

    def remove(self):
        self.removed = True


class MockPartialResponseWidget(PartialResponseWidget):
    """Mock PartialResponseWidget that tracks removal state."""

    def __init__(self):
        self.removed = False

    def remove(self):
        self.removed = True


class MockVerticalTail:
    """Mock VerticalTail container for testing widget mounting/removal."""

    def __init__(self, children: list):
        self.children = children
        self.mounted: list = []

    def mount(self, widget, before=None):
        self.mounted.append(widget)

    def scroll_end(self, animate=False):
        pass


@pytest.fixture
def chat_history():
    """Create a fresh ChatHistory instance for each test."""
    return ChatHistory()


def test_update_messages_removes_widgets_when_cleared(chat_history):
    """Test that clearing messages removes existing widgets from the UI.

    This tests the fix for issue #355 where clearing conversation didn't
    clear the UI - the message widgets remained visible even though the
    message list was empty.
    """
    # Simulate some initial messages
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(parts=[TextPart(content="Hi there!")]),
    ]
    chat_history.items = messages
    chat_history._rendered_count = 2

    # Simulate vertical_tail with mock children (2 message widgets + PartialResponseWidget)
    mock_vertical_tail = MockVerticalTail(
        children=[
            MockWidget(),  # UserQuestionWidget
            MockWidget(),  # AgentResponseWidget
            MockPartialResponseWidget(),  # PartialResponseWidget
        ]
    )
    chat_history.vertical_tail = mock_vertical_tail

    # Clear messages
    chat_history.update_messages([])

    # Verify that message widgets were removed but PartialResponseWidget was kept
    assert mock_vertical_tail.children[0].removed is True
    assert mock_vertical_tail.children[1].removed is True
    assert mock_vertical_tail.children[2].removed is False

    # Verify rendered count was reset
    assert chat_history._rendered_count == 0


def test_update_messages_removes_widgets_when_reduced(chat_history):
    """Test that reducing messages removes excess widgets.

    When messages are compacted or filtered, the old widgets should be
    removed so new ones can be mounted correctly.
    """
    # Simulate 3 messages initially rendered
    chat_history.items = [
        ModelRequest(parts=[UserPromptPart(content="Msg 1")]),
        ModelResponse(parts=[TextPart(content="Response 1")]),
        ModelRequest(parts=[UserPromptPart(content="Msg 2")]),
    ]
    chat_history._rendered_count = 3

    mock_vertical_tail = MockVerticalTail(
        children=[
            MockWidget(),
            MockWidget(),
            MockWidget(),
            MockPartialResponseWidget(),
        ]
    )
    chat_history.vertical_tail = mock_vertical_tail

    # Reduce to 1 message
    new_messages = [
        ModelRequest(parts=[UserPromptPart(content="Msg 1")]),
    ]
    chat_history.update_messages(new_messages)

    # Verify all message widgets were removed (they will be re-mounted)
    assert mock_vertical_tail.children[0].removed is True
    assert mock_vertical_tail.children[1].removed is True
    assert mock_vertical_tail.children[2].removed is True
    assert mock_vertical_tail.children[3].removed is False  # PartialResponseWidget kept

    # Rendered count should be reset to 0, then incremented as new messages mount
    # Since the filtered count is 1, one message will be mounted
    assert chat_history._rendered_count == 1


def test_update_messages_appends_new_messages(chat_history):
    """Test that appending new messages works correctly without removing existing."""
    # Start with 1 message rendered
    chat_history.items = [
        ModelRequest(parts=[UserPromptPart(content="Msg 1")]),
    ]
    chat_history._rendered_count = 1

    mock_vertical_tail = MockVerticalTail(
        children=[
            MockWidget(),  # Existing message
            MockPartialResponseWidget(),
        ]
    )
    chat_history.vertical_tail = mock_vertical_tail

    # Add a new message (2 total now)
    new_messages = [
        ModelRequest(parts=[UserPromptPart(content="Msg 1")]),
        ModelResponse(parts=[TextPart(content="Response 1")]),
    ]
    chat_history.update_messages(new_messages)

    # Existing widget should NOT be removed
    assert mock_vertical_tail.children[0].removed is False

    # New message should be mounted
    assert len(mock_vertical_tail.mounted) == 1
    assert isinstance(mock_vertical_tail.mounted[0], AgentResponseWidget)

    # Rendered count should be updated
    assert chat_history._rendered_count == 2


def test_update_messages_sub_agent_response_renders_with_prefix(chat_history):
    """Sub-agent responses marked with _shotgun_is_sub_agent should render with is_sub_agent=True."""
    chat_history._rendered_count = 0

    mock_vertical_tail = MockVerticalTail(children=[MockPartialResponseWidget()])
    chat_history.vertical_tail = mock_vertical_tail

    # Create a sub-agent response with the marker
    sub_agent_resp = ModelResponse(parts=[TextPart(content="Sub-agent findings")])
    sub_agent_resp._shotgun_is_sub_agent = True  # type: ignore[attr-defined]

    chat_history.update_messages([sub_agent_resp])

    # Widget should be mounted
    assert len(mock_vertical_tail.mounted) == 1
    widget = mock_vertical_tail.mounted[0]
    assert isinstance(widget, AgentResponseWidget)
    assert widget.is_sub_agent is True


def test_update_messages_regular_response_no_sub_agent_prefix(chat_history):
    """Regular responses without marker should render with is_sub_agent=False."""
    chat_history._rendered_count = 0

    mock_vertical_tail = MockVerticalTail(children=[MockPartialResponseWidget()])
    chat_history.vertical_tail = mock_vertical_tail

    regular_resp = ModelResponse(parts=[TextPart(content="Regular response")])
    chat_history.update_messages([regular_resp])

    assert len(mock_vertical_tail.mounted) == 1
    widget = mock_vertical_tail.mounted[0]
    assert isinstance(widget, AgentResponseWidget)
    assert widget.is_sub_agent is False
