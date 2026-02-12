"""Unit tests for IncompleteToolCallError exception."""

from shotgun.exceptions import IncompleteToolCallError, UserActionableError


def test_incomplete_tool_call_error_inherits_from_user_actionable():
    """IncompleteToolCallError should inherit from UserActionableError."""
    error = IncompleteToolCallError()
    assert isinstance(error, UserActionableError)
    assert isinstance(error, Exception)


def test_incomplete_tool_call_error_without_tool_name():
    """IncompleteToolCallError should work without a tool name."""
    error = IncompleteToolCallError()
    assert error.tool_name is None
    assert "incomplete arguments" in str(error).lower()


def test_incomplete_tool_call_error_with_tool_name():
    """IncompleteToolCallError should include tool name when provided."""
    error = IncompleteToolCallError(tool_name="web_search")
    assert error.tool_name == "web_search"
    assert "web_search" in str(error)


def test_incomplete_tool_call_error_markdown_with_tool_name():
    """to_markdown should include tool name when provided."""
    error = IncompleteToolCallError(tool_name="file_read")
    md = error.to_markdown()
    assert "file_read" in md
    assert "truncated" in md.lower()
    assert "Try again" in md


def test_incomplete_tool_call_error_markdown_without_tool_name():
    """to_markdown should work without tool name."""
    error = IncompleteToolCallError()
    md = error.to_markdown()
    assert "tool call" in md.lower()
    assert "truncated" in md.lower()


def test_incomplete_tool_call_error_plain_text_with_tool_name():
    """to_plain_text should include tool name when provided."""
    error = IncompleteToolCallError(tool_name="web_search")
    text = error.to_plain_text()
    assert "web_search" in text
    assert "truncated" in text.lower()


def test_incomplete_tool_call_error_plain_text_without_tool_name():
    """to_plain_text should work without tool name."""
    error = IncompleteToolCallError()
    text = error.to_plain_text()
    assert "tool call" in text.lower()
