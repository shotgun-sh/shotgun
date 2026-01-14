"""Tests for tool formatting utilities."""

import pytest
from pydantic_ai.messages import ToolCallPart

from shotgun.agents.tools.registry import (
    _TOOL_DISPLAY_REGISTRY,
    ToolDisplayConfig,
)
from shotgun.tui.screens.chat_screen.history.formatters import ToolFormatter


@pytest.fixture
def cleanup_registry():
    """Clean up test tools from registry after each test."""
    test_tools = []
    yield test_tools
    for tool_name in test_tools:
        _TOOL_DISPLAY_REGISTRY.pop(tool_name, None)


def test_format_tool_call_part_with_secondary_key_arg(cleanup_registry):
    """Test that secondary_key_arg is displayed alongside primary key arg."""
    # Register a test tool with secondary_key_arg
    _TOOL_DISPLAY_REGISTRY["test_replace_section"] = ToolDisplayConfig(
        display_text="Replacing section",
        key_arg="filename",
        secondary_key_arg="section_heading",
    )
    cleanup_registry.append("test_replace_section")

    # Create a mock tool call part
    part = ToolCallPart(
        tool_name="test_replace_section",
        args={"filename": "spec.md", "section_heading": "## Requirements"},
        tool_call_id="test-123",
    )

    result = ToolFormatter.format_tool_call_part(part)

    assert result == "Replacing section: spec.md → ## Requirements"


def test_format_tool_call_part_without_secondary_key_arg(cleanup_registry):
    """Test backward compatibility - tools without secondary_key_arg work as before."""
    # Register a test tool without secondary_key_arg
    _TOOL_DISPLAY_REGISTRY["test_read_file"] = ToolDisplayConfig(
        display_text="Reading file",
        key_arg="filename",
    )
    cleanup_registry.append("test_read_file")

    part = ToolCallPart(
        tool_name="test_read_file",
        args={"filename": "test.py"},
        tool_call_id="test-456",
    )

    result = ToolFormatter.format_tool_call_part(part)

    assert result == "Reading file: test.py"


def test_format_tool_call_part_secondary_key_arg_missing_value(cleanup_registry):
    """Test that missing secondary_key_arg value falls back to just primary."""
    _TOOL_DISPLAY_REGISTRY["test_partial_section"] = ToolDisplayConfig(
        display_text="Replacing section",
        key_arg="filename",
        secondary_key_arg="section_heading",
    )
    cleanup_registry.append("test_partial_section")

    # secondary_key_arg value is missing from args
    part = ToolCallPart(
        tool_name="test_partial_section",
        args={"filename": "spec.md"},
        tool_call_id="test-789",
    )

    result = ToolFormatter.format_tool_call_part(part)

    # Should fall back to just showing filename
    assert result == "Replacing section: spec.md"


def test_format_tool_call_part_truncates_long_secondary_value(cleanup_registry):
    """Test that long secondary_key_arg values are truncated."""
    _TOOL_DISPLAY_REGISTRY["test_long_section"] = ToolDisplayConfig(
        display_text="Replacing section",
        key_arg="filename",
        secondary_key_arg="section_heading",
    )
    cleanup_registry.append("test_long_section")

    long_heading = "## " + "A" * 150  # Very long heading

    part = ToolCallPart(
        tool_name="test_long_section",
        args={"filename": "spec.md", "section_heading": long_heading},
        tool_call_id="test-abc",
    )

    result = ToolFormatter.format_tool_call_part(part)

    # Should be truncated to 100 chars with ...
    assert "..." in result
    assert len(result.split(" → ")[1]) <= 100


def test_format_tool_call_part_hidden_tool(cleanup_registry):
    """Test that hidden tools return empty string."""
    _TOOL_DISPLAY_REGISTRY["test_hidden"] = ToolDisplayConfig(
        display_text="Hidden tool",
        key_arg="data",
        hide=True,
    )
    cleanup_registry.append("test_hidden")

    part = ToolCallPart(
        tool_name="test_hidden",
        args={"data": "test"},
        tool_call_id="test-hidden",
    )

    result = ToolFormatter.format_tool_call_part(part)

    assert result == ""


def test_truncate():
    """Test the truncate method."""
    # Short text - no truncation
    assert ToolFormatter.truncate("short") == "short"

    # Exactly max_length - no truncation
    text_100 = "a" * 100
    assert ToolFormatter.truncate(text_100) == text_100

    # Over max_length - truncated with ellipsis
    text_150 = "a" * 150
    result = ToolFormatter.truncate(text_150)
    assert len(result) == 100
    assert result.endswith("...")


def test_parse_args_dict():
    """Test parse_args with dict input."""
    args = {"key": "value"}
    assert ToolFormatter.parse_args(args) == {"key": "value"}


def test_parse_args_json_string():
    """Test parse_args with JSON string input."""
    args = '{"key": "value"}'
    assert ToolFormatter.parse_args(args) == {"key": "value"}


def test_parse_args_empty():
    """Test parse_args with empty/None input."""
    assert ToolFormatter.parse_args(None) == {}
    assert ToolFormatter.parse_args("") == {}
    assert ToolFormatter.parse_args("  ") == {}


def test_parse_args_invalid_json():
    """Test parse_args with invalid JSON string."""
    assert ToolFormatter.parse_args("not valid json") == {}
