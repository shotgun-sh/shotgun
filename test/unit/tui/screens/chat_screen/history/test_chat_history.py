"""Tests for ChatHistory widget."""

from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart

from shotgun.tui.screens.chat_screen.history.agent_response import AgentResponseWidget
from shotgun.tui.screens.chat_screen.history.chat_history import ChatHistory
from shotgun.tui.screens.chat_screen.history.partial_response import (
    PartialResponseWidget,
)


def test_update_messages_removes_widgets_when_cleared():
    """Test that clearing messages removes existing widgets from the UI.

    This tests the fix for issue #355 where clearing conversation didn't
    clear the UI - the message widgets remained visible even though the
    message list was empty.
    """
    chat_history = ChatHistory()

    # Simulate some initial messages
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(parts=[TextPart(content="Hi there!")]),
    ]
    chat_history.items = messages
    chat_history._rendered_count = 2

    # Simulate vertical_tail with mock children (2 message widgets + PartialResponseWidget)
    class MockWidget:
        def __init__(self, is_partial=False):
            self.is_partial = is_partial
            self.removed = False

        def remove(self):
            self.removed = True

    class MockPartialResponseWidget(PartialResponseWidget):
        def __init__(self):
            self.removed = False

        def remove(self):
            self.removed = True

    class MockVerticalTail:
        def __init__(self):
            self.children = [
                MockWidget(),  # UserQuestionWidget
                MockWidget(),  # AgentResponseWidget
                MockPartialResponseWidget(),  # PartialResponseWidget
            ]

        def mount(self, widget, before=None):
            pass

        def scroll_end(self, animate=False):
            pass

    mock_vertical_tail = MockVerticalTail()
    chat_history.vertical_tail = mock_vertical_tail

    # Clear messages
    chat_history.update_messages([])

    # Verify that message widgets were removed but PartialResponseWidget was kept
    assert mock_vertical_tail.children[0].removed is True
    assert mock_vertical_tail.children[1].removed is True
    assert mock_vertical_tail.children[2].removed is False

    # Verify rendered count was reset
    assert chat_history._rendered_count == 0


def test_update_messages_removes_widgets_when_reduced():
    """Test that reducing messages removes excess widgets.

    When messages are compacted or filtered, the old widgets should be
    removed so new ones can be mounted correctly.
    """
    chat_history = ChatHistory()

    # Simulate 3 messages initially rendered
    chat_history.items = [
        ModelRequest(parts=[UserPromptPart(content="Msg 1")]),
        ModelResponse(parts=[TextPart(content="Response 1")]),
        ModelRequest(parts=[UserPromptPart(content="Msg 2")]),
    ]
    chat_history._rendered_count = 3

    class MockWidget:
        def __init__(self):
            self.removed = False

        def remove(self):
            self.removed = True

    class MockPartialResponseWidget(PartialResponseWidget):
        def __init__(self):
            self.removed = False

        def remove(self):
            self.removed = True

    class MockVerticalTail:
        def __init__(self):
            self.children = [
                MockWidget(),
                MockWidget(),
                MockWidget(),
                MockPartialResponseWidget(),
            ]

        def mount(self, widget, before=None):
            pass

        def scroll_end(self, animate=False):
            pass

    mock_vertical_tail = MockVerticalTail()
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


def test_update_messages_appends_new_messages():
    """Test that appending new messages works correctly without removing existing."""
    chat_history = ChatHistory()

    # Start with 1 message rendered
    chat_history.items = [
        ModelRequest(parts=[UserPromptPart(content="Msg 1")]),
    ]
    chat_history._rendered_count = 1

    class MockWidget:
        def __init__(self):
            self.removed = False

        def remove(self):
            self.removed = True

    class MockPartialResponseWidget(PartialResponseWidget):
        def __init__(self):
            self.removed = False

        def remove(self):
            self.removed = True

    class MockVerticalTail:
        def __init__(self):
            self.children = [
                MockWidget(),  # Existing message
                MockPartialResponseWidget(),
            ]
            self.mounted = []

        def mount(self, widget, before=None):
            self.mounted.append(widget)

        def scroll_end(self, animate=False):
            pass

    mock_vertical_tail = MockVerticalTail()
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
