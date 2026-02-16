"""Tests for conversation filter functions."""

from datetime import datetime, timezone

from pydantic_ai import BinaryContent
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from shotgun.agents.conversation.filters import (
    _create_file_reference,
    _extract_file_path,
    _filter_content_parts,
    filter_binary_content,
    filter_incomplete_messages,
    filter_orphaned_tool_responses,
    is_tool_call_complete,
)


def test_extract_file_path_valid():
    """Test extracting file path from a valid marker string."""
    result = _extract_file_path("\n\n--- File: /path/to/file.pdf ---")
    assert result == "/path/to/file.pdf"


def test_extract_file_path_with_spaces():
    """Test extracting file path with spaces in the path."""
    result = _extract_file_path("\n\n--- File: /path/to/my file.pdf ---")
    assert result == "/path/to/my file.pdf"


def test_extract_file_path_no_leading_newlines():
    """Test extracting file path without leading newlines."""
    result = _extract_file_path("--- File: /path/to/file.pdf ---")
    assert result == "/path/to/file.pdf"


def test_extract_file_path_invalid():
    """Test that invalid strings return None."""
    assert _extract_file_path("Hello world") is None
    assert _extract_file_path("File: /path/to/file.pdf") is None
    assert _extract_file_path("--- File ---") is None


def test_create_file_reference():
    """Test creating a file reference dict from BinaryContent."""
    binary = BinaryContent(data=b"test data", media_type="application/pdf")
    result = _create_file_reference(binary, "/path/to/file.pdf")

    assert result["kind"] == "file_reference"
    assert result["file_path"] == "/path/to/file.pdf"
    assert result["media_type"] == "application/pdf"
    assert result["size_bytes"] == 9


def test_create_file_reference_unknown_path():
    """Test creating a file reference with unknown path."""
    binary = BinaryContent(data=b"test", media_type="image/png")
    result = _create_file_reference(binary, None)

    assert result["file_path"] == "<unknown>"


def test_filter_content_parts_single_file():
    """Test filtering content parts with a single file."""
    binary = BinaryContent(data=b"PDF content", media_type="application/pdf")
    content = [
        "Please analyze this file:",
        "\n\n--- File: /docs/report.pdf ---",
        binary,
    ]

    result = _filter_content_parts(content)

    assert len(result) == 3
    assert result[0] == "Please analyze this file:"
    assert result[1] == "\n\n--- File: /docs/report.pdf ---"
    assert isinstance(result[2], dict)
    assert result[2]["kind"] == "file_reference"
    assert result[2]["file_path"] == "/docs/report.pdf"
    assert result[2]["media_type"] == "application/pdf"
    assert result[2]["size_bytes"] == 11


def test_filter_content_parts_multiple_files():
    """Test filtering content parts with multiple files."""
    pdf = BinaryContent(data=b"PDF", media_type="application/pdf")
    image = BinaryContent(data=b"IMAGE DATA", media_type="image/png")
    content = [
        "Here are the files:",
        "\n\n--- File: /docs/report.pdf ---",
        pdf,
        "\n\n--- File: /images/chart.png ---",
        image,
    ]

    result = _filter_content_parts(content)

    assert len(result) == 5
    assert result[2]["file_path"] == "/docs/report.pdf"
    assert result[4]["file_path"] == "/images/chart.png"


def test_filter_content_parts_no_binary():
    """Test filtering content parts with no binary content."""
    content = ["Hello", "World"]
    result = _filter_content_parts(content)
    assert result == ["Hello", "World"]


def test_filter_content_parts_binary_without_marker():
    """Test filtering binary content without a preceding file marker."""
    binary = BinaryContent(data=b"data", media_type="image/jpeg")
    content = ["Some text", binary]

    result = _filter_content_parts(content)

    assert len(result) == 2
    assert result[1]["file_path"] == "<unknown>"


def test_filter_binary_content_empty_list():
    """Test filtering an empty message list."""
    result = filter_binary_content([])
    assert result == []


def test_filter_binary_content_no_binary():
    """Test filtering messages without binary content."""
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(parts=[TextPart(content="Hi there!")]),
    ]

    result = filter_binary_content(messages)

    assert len(result) == 2
    assert result[0] == messages[0]
    assert result[1] == messages[1]


def test_filter_binary_content_with_binary():
    """Test filtering messages with binary content."""
    binary = BinaryContent(data=b"PDF data here", media_type="application/pdf")
    timestamp = datetime.now(timezone.utc)
    messages = [
        ModelRequest(
            parts=[
                UserPromptPart(
                    content=[
                        "Please read this file:",
                        "\n\n--- File: /test.pdf ---",
                        binary,
                    ],
                    timestamp=timestamp,
                )
            ]
        ),
        ModelResponse(parts=[TextPart(content="I've read the file.")]),
    ]

    result = filter_binary_content(messages)

    assert len(result) == 2
    # Check the first message was modified
    request = result[0]
    assert isinstance(request, ModelRequest)
    user_part = request.parts[0]
    assert isinstance(user_part, UserPromptPart)
    assert isinstance(user_part.content, list)
    assert len(user_part.content) == 3
    # The binary content should be replaced with a dict
    file_ref = user_part.content[2]
    assert isinstance(file_ref, dict)
    assert file_ref["kind"] == "file_reference"
    assert file_ref["file_path"] == "/test.pdf"
    assert file_ref["size_bytes"] == 13
    # Timestamp should be preserved
    assert user_part.timestamp == timestamp


def test_filter_binary_content_preserves_model_response():
    """Test that ModelResponse messages pass through unchanged."""
    response = ModelResponse(parts=[TextPart(content="Response text")])
    result = filter_binary_content([response])

    assert len(result) == 1
    assert result[0] is response


def test_filter_binary_content_string_content_unchanged():
    """Test that string content in UserPromptPart passes through unchanged."""
    messages = [ModelRequest(parts=[UserPromptPart(content="Just a string")])]

    result = filter_binary_content(messages)

    assert len(result) == 1
    request = result[0]
    assert isinstance(request, ModelRequest)
    assert request.parts[0].content == "Just a string"


def test_filter_binary_content_multiple_requests():
    """Test filtering multiple requests with binary content."""
    binary1 = BinaryContent(data=b"First", media_type="application/pdf")
    binary2 = BinaryContent(data=b"Second", media_type="image/png")

    messages = [
        ModelRequest(
            parts=[
                UserPromptPart(
                    content=[
                        "\n\n--- File: /first.pdf ---",
                        binary1,
                    ]
                )
            ]
        ),
        ModelResponse(parts=[TextPart(content="Got it")]),
        ModelRequest(
            parts=[
                UserPromptPart(
                    content=[
                        "\n\n--- File: /second.png ---",
                        binary2,
                    ]
                )
            ]
        ),
    ]

    result = filter_binary_content(messages)

    assert len(result) == 3
    # First request
    req1 = result[0]
    assert isinstance(req1, ModelRequest)
    content1 = req1.parts[0].content
    assert content1[1]["file_path"] == "/first.pdf"
    # Third message (second request)
    req2 = result[2]
    assert isinstance(req2, ModelRequest)
    content2 = req2.parts[0].content
    assert content2[1]["file_path"] == "/second.png"


# --- Tests for is_tool_call_complete ---


def test_is_tool_call_complete_with_none_args():
    """Tool call with None args is considered complete."""
    tc = ToolCallPart(tool_name="test", args=None, tool_call_id="tc1")
    assert is_tool_call_complete(tc) is True


def test_is_tool_call_complete_with_dict_args():
    """Tool call with dict args is considered complete."""
    tc = ToolCallPart(tool_name="test", args={"key": "value"}, tool_call_id="tc1")
    assert is_tool_call_complete(tc) is True


def test_is_tool_call_complete_with_valid_json_string():
    """Tool call with valid JSON string args is considered complete."""
    tc = ToolCallPart(tool_name="test", args='{"key": "value"}', tool_call_id="tc1")
    assert is_tool_call_complete(tc) is True


def test_is_tool_call_complete_with_truncated_json():
    """Tool call with truncated JSON string is considered incomplete."""
    tc = ToolCallPart(tool_name="test", args='{"key": "val', tool_call_id="tc1")
    assert is_tool_call_complete(tc) is False


def test_is_tool_call_complete_with_empty_string():
    """Tool call with empty string args is considered incomplete."""
    tc = ToolCallPart(tool_name="test", args="", tool_call_id="tc1")
    assert is_tool_call_complete(tc) is False


# --- Tests for filter_incomplete_messages ---


def test_filter_incomplete_messages_removes_incomplete():
    """Messages with incomplete tool calls should be filtered out."""
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="web_search",
                    args='{"query": "test',  # truncated
                    tool_call_id="tc1",
                ),
            ]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="web_search",
                    content="result",
                    tool_call_id="tc1",
                )
            ]
        ),
    ]

    result = filter_incomplete_messages(messages)

    # The ModelResponse with incomplete tool call should be removed
    assert len(result) == 2
    assert isinstance(result[0], ModelRequest)
    assert isinstance(result[1], ModelRequest)


def test_filter_incomplete_messages_keeps_complete():
    """Messages with complete tool calls should be kept."""
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="web_search",
                    args='{"query": "test"}',
                    tool_call_id="tc1",
                ),
            ]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="web_search",
                    content="result",
                    tool_call_id="tc1",
                )
            ]
        ),
    ]

    result = filter_incomplete_messages(messages)

    assert len(result) == 3


def test_filter_incomplete_messages_empty_list():
    """Empty message list should return empty."""
    assert filter_incomplete_messages([]) == []


# --- Tests for filter_orphaned_tool_responses ---


def test_filter_orphaned_tool_responses_removes_orphans():
    """Tool returns without matching tool calls should be removed."""
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        # No ModelResponse with tool call for tc1
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="web_search",
                    content="result",
                    tool_call_id="orphan_tc1",
                )
            ]
        ),
    ]

    result = filter_orphaned_tool_responses(messages)

    # The orphaned ToolReturnPart's ModelRequest should be removed (no parts left)
    assert len(result) == 1
    assert isinstance(result[0], ModelRequest)


def test_filter_orphaned_tool_responses_keeps_matched():
    """Tool returns with matching tool calls should be kept."""
    messages = [
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="web_search",
                    args='{"query": "test"}',
                    tool_call_id="tc1",
                ),
            ]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="web_search",
                    content="result",
                    tool_call_id="tc1",
                )
            ]
        ),
    ]

    result = filter_orphaned_tool_responses(messages)

    assert len(result) == 2


def test_filter_incomplete_then_orphaned_cleans_history():
    """Applying both filters should produce a clean history.

    When an incomplete tool call is removed, its corresponding tool return
    becomes orphaned and should also be removed.
    """
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="web_search",
                    args='{"query": "test',  # truncated JSON
                    tool_call_id="tc1",
                ),
            ]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="web_search",
                    content="result",
                    tool_call_id="tc1",
                )
            ]
        ),
    ]

    # Apply both filters in sequence (same order as agent_manager.py)
    result = filter_incomplete_messages(messages)
    result = filter_orphaned_tool_responses(result)

    # Only the original user prompt should remain
    assert len(result) == 1
    assert isinstance(result[0], ModelRequest)
