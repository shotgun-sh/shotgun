"""Unit tests for file content deduplication module."""

# type: ignore

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from shotgun.agents.conversation.history.file_content_deduplication import (
    _create_codebase_placeholder,
    _create_shotgun_placeholder,
    _extract_file_path,
    deduplicate_file_content,
)


class TestExtractFilePath:
    """Tests for _extract_file_path function."""

    def test_extracts_file_path_from_standard_output(self):
        """Test extraction from standard file_read output format."""
        content = """**File**: `src/main.py`
**Size**: 1234 bytes

**Content**:
```python
def main():
    print("Hello, World!")
```"""
        result = _extract_file_path(content)
        assert result == "src/main.py"

    def test_extracts_file_path_with_encoding(self):
        """Test extraction from file read output with encoding line."""
        content = """**File**: `data/config.json`
**Size**: 500 bytes
**Encoding**: utf-8

**Content**:
```json
{"key": "value"}
```"""
        result = _extract_file_path(content)
        assert result == "data/config.json"

    def test_extracts_file_path_without_extension(self):
        """Test extraction from file without extension."""
        content = """**File**: `README`
**Size**: 100 bytes

**Content**:
```
Plain text content here
```"""
        result = _extract_file_path(content)
        assert result == "README"

    def test_returns_none_for_invalid_format(self):
        """Test that invalid format returns None."""
        content = "This is not a valid file read output"
        result = _extract_file_path(content)
        assert result is None

    def test_returns_none_for_error_message(self):
        """Test that error messages are not parsed."""
        content = "**Error reading file `missing.py`**: File not found"
        result = _extract_file_path(content)
        assert result is None


class TestCreatePlaceholders:
    """Tests for placeholder creation functions."""

    def test_create_codebase_placeholder(self):
        """Test codebase placeholder creation."""
        placeholder = _create_codebase_placeholder("src/app.py", 5000, "python")

        assert "src/app.py" in placeholder
        assert "5000 bytes" in placeholder
        assert "python" in placeholder
        assert "retrieve_code" in placeholder

    def test_create_shotgun_placeholder(self):
        """Test .shotgun/ placeholder creation."""
        placeholder = _create_shotgun_placeholder("research.md")

        assert ".shotgun/research.md" in placeholder
        assert "persisted" in placeholder


class TestDeduplicateFileContent:
    """Tests for deduplicate_file_content function."""

    def test_empty_messages_returns_empty(self):
        """Test that empty messages returns empty result."""
        result, tokens_saved = deduplicate_file_content([])
        assert result == []
        assert tokens_saved == 0

    def test_messages_without_file_reads_unchanged(self):
        """Test that messages without file reads are unchanged."""
        messages = [
            ModelRequest(parts=[UserPromptPart(content="Hello")]),
            ModelResponse(parts=[TextPart(content="Hi there!")]),
        ]

        result, tokens_saved = deduplicate_file_content(messages)

        assert len(result) == 2
        assert tokens_saved == 0

    def test_deduplicates_codebase_file_read(self):
        """Test deduplication of codebase file_read tool returns."""
        large_content = "x" * 1000  # Large enough content
        file_read_content = f"""**File**: `src/large_file.py`
**Size**: 10000 bytes

**Content**:
```python
{large_content}
```"""

        messages = [
            ModelRequest(parts=[UserPromptPart(content="Read the file")]),
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="file_read",
                        args={"file_path": "src/large_file.py"},
                        tool_call_id="call_1",
                    )
                ]
            ),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="file_read",
                        tool_call_id="call_1",
                        content=file_read_content,
                    )
                ]
            ),
            ModelResponse(parts=[TextPart(content="I've read the file.")]),
            ModelRequest(parts=[UserPromptPart(content="Thanks")]),
        ]

        # Use retention_window=1 so only last message is retained
        result, tokens_saved = deduplicate_file_content(messages, retention_window=1)

        assert len(result) == 5
        assert tokens_saved > 0

        # Find the tool return and check it was replaced
        tool_return = result[2].parts[0]
        assert isinstance(tool_return, ToolReturnPart)
        assert "Removed for compaction" in tool_return.content
        assert "src/large_file.py" in tool_return.content
        assert large_content not in tool_return.content

    def test_deduplicates_shotgun_file_read(self):
        """Test deduplication of .shotgun/ read_file tool returns."""
        large_content = "# Research Notes\n" + ("Lorem ipsum " * 200)

        messages = [
            ModelRequest(parts=[UserPromptPart(content="Read research")]),
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="read_file",
                        args={"filename": "research.md"},
                        tool_call_id="call_2",
                    )
                ]
            ),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="read_file",
                        tool_call_id="call_2",
                        content=large_content,
                    )
                ]
            ),
            ModelResponse(parts=[TextPart(content="Here's a summary.")]),
            ModelRequest(parts=[UserPromptPart(content="OK")]),
        ]

        result, tokens_saved = deduplicate_file_content(messages, retention_window=1)

        assert len(result) == 5
        assert tokens_saved > 0

        # Find the tool return and check it was replaced
        tool_return = result[2].parts[0]
        assert isinstance(tool_return, ToolReturnPart)
        assert "Removed for compaction" in tool_return.content
        assert ".shotgun/" in tool_return.content
        assert "Lorem ipsum" not in tool_return.content

    def test_retention_window_preserves_recent_messages(self):
        """Test that retention window keeps recent file content intact."""
        large_content = "x" * 1000
        file_read_content = f"""**File**: `recent.py`
**Size**: 1000 bytes

**Content**:
```python
{large_content}
```"""

        messages = [
            ModelRequest(parts=[UserPromptPart(content="Read the file")]),
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="file_read",
                        args={"file_path": "recent.py"},
                        tool_call_id="call_3",
                    )
                ]
            ),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="file_read",
                        tool_call_id="call_3",
                        content=file_read_content,
                    )
                ]
            ),
        ]

        # All 3 messages are in retention window
        result, tokens_saved = deduplicate_file_content(messages, retention_window=3)

        # No tokens should be saved since all messages are in retention window
        assert tokens_saved == 0

        # Content should be preserved
        tool_return = result[2].parts[0]
        assert large_content in tool_return.content

    def test_skips_small_content(self):
        """Test that small file content is not deduplicated."""
        small_content = """**File**: `tiny.py`
**Size**: 50 bytes

**Content**:
```python
x = 1
```"""

        messages = [
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="file_read",
                        tool_call_id="call_4",
                        content=small_content,
                    )
                ]
            ),
            ModelRequest(parts=[UserPromptPart(content="Later message")]),
            ModelRequest(parts=[UserPromptPart(content="Last message")]),
        ]

        result, tokens_saved = deduplicate_file_content(messages, retention_window=1)

        # Small content should not be deduplicated
        assert tokens_saved == 0

    def test_preserves_tool_return_metadata(self):
        """Test that tool return metadata is preserved after deduplication."""
        from datetime import datetime, timezone

        large_content = "y" * 1000
        file_read_content = f"""**File**: `test.py`
**Size**: 5000 bytes

**Content**:
```python
{large_content}
```"""

        timestamp = datetime.now(timezone.utc)
        messages = [
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="file_read",
                        tool_call_id="original_call_id",
                        content=file_read_content,
                        timestamp=timestamp,
                    )
                ]
            ),
            ModelRequest(parts=[UserPromptPart(content="End")]),
        ]

        result, _ = deduplicate_file_content(messages, retention_window=1)

        tool_return = result[0].parts[0]
        assert isinstance(tool_return, ToolReturnPart)
        assert tool_return.tool_call_id == "original_call_id"
        assert tool_return.tool_name == "file_read"
        assert tool_return.timestamp == timestamp

    def test_does_not_modify_original_messages(self):
        """Test that original messages are not modified."""
        large_content = "z" * 1000
        file_read_content = f"""**File**: `immutable.py`
**Size**: 1000 bytes

**Content**:
```python
{large_content}
```"""

        original_messages = [
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="file_read",
                        tool_call_id="call_5",
                        content=file_read_content,
                    )
                ]
            ),
            ModelRequest(parts=[UserPromptPart(content="End")]),
        ]

        # Store original content
        original_content = original_messages[0].parts[0].content

        result, _ = deduplicate_file_content(original_messages, retention_window=1)

        # Original should be unchanged
        assert original_messages[0].parts[0].content == original_content
        # Result should be different
        assert result[0].parts[0].content != original_content

    def test_handles_multiple_tool_returns_in_same_message(self):
        """Test handling multiple tool returns in a single message."""
        large_content1 = "a" * 1000
        large_content2 = "b" * 1000

        file_read_content1 = f"""**File**: `file1.py`
**Size**: 1000 bytes

**Content**:
```python
{large_content1}
```"""

        file_read_content2 = f"""**File**: `file2.py`
**Size**: 1000 bytes

**Content**:
```python
{large_content2}
```"""

        messages = [
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="file_read",
                        tool_call_id="call_a",
                        content=file_read_content1,
                    ),
                    ToolReturnPart(
                        tool_name="file_read",
                        tool_call_id="call_b",
                        content=file_read_content2,
                    ),
                ]
            ),
            ModelRequest(parts=[UserPromptPart(content="End")]),
        ]

        result, tokens_saved = deduplicate_file_content(messages, retention_window=1)

        # Both should be deduplicated
        assert tokens_saved > 0
        assert "Removed for compaction" in result[0].parts[0].content
        assert "Removed for compaction" in result[0].parts[1].content
        assert "file1.py" in result[0].parts[0].content
        assert "file2.py" in result[0].parts[1].content
