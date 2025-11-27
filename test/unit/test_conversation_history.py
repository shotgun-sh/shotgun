"""Unit tests for conversation history persistence."""

import json
from datetime import datetime

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from shotgun.agents.conversation import (
    ConversationHistory,
    ConversationManager,
    ConversationState,
    filter_orphaned_tool_responses,
)
from shotgun.tui.screens.chat_screen.hint_message import HintMessage


def test_conversation_history_creation():
    """Test ConversationHistory model creation."""
    history = ConversationHistory()
    assert history.version == 1
    assert history.agent_history == []
    assert history.ui_history == []
    assert history.last_agent_model == "research"
    assert isinstance(history.updated_at, datetime)


def test_conversation_history_with_agent_messages():
    """Test ConversationHistory with agent messages."""
    # Create some model messages
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(parts=[TextPart(content="Hi there!")]),
    ]

    history = ConversationHistory(
        last_agent_model="plan",
    )
    history.set_agent_messages(messages)

    assert len(history.agent_history) == 2
    assert history.last_agent_model == "plan"


def test_agent_messages_serialization():
    """Test serialization and deserialization of agent messages."""
    # Create some model messages
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Test prompt")]),
        ModelResponse(parts=[TextPart(content="Test response")]),
    ]

    history = ConversationHistory()
    history.set_agent_messages(messages)

    # Check that messages were serialized
    assert len(history.agent_history) == 2
    assert isinstance(history.agent_history[0], dict)

    # Check deserialization
    retrieved_messages = history.get_agent_messages()
    assert len(retrieved_messages) == 2
    assert isinstance(retrieved_messages[0], ModelRequest)
    assert isinstance(retrieved_messages[1], ModelResponse)


def test_conversation_history_json_serialization():
    """Test ConversationHistory JSON serialization."""
    history = ConversationHistory(
        last_agent_model="tasks",
    )

    # Add agent messages
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Test")]),
    ]
    history.set_agent_messages(messages)

    # Serialize to JSON
    json_data = history.model_dump(mode="json")

    # Verify structure
    assert json_data["version"] == 1
    assert json_data["last_agent_model"] == "tasks"
    assert len(json_data["agent_history"]) == 1
    assert "ui_history" in json_data

    # Verify it can be serialized to JSON string
    json_str = json.dumps(json_data)
    assert isinstance(json_str, str)


@pytest.mark.asyncio
async def test_conversation_manager_save_load(tmp_path):
    """Test ConversationManager save and load functionality."""
    # Create a manager with custom path
    conv_path = tmp_path / "test_conversation.json"
    manager = ConversationManager(conversation_path=conv_path)

    # Create and save a conversation
    history = ConversationHistory(
        last_agent_model="research",
    )

    # Add some agent messages
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Test message")]),
    ]
    history.set_agent_messages(messages)
    hint_messages = [HintMessage(message="Remember to add docs")]
    history.set_ui_messages(messages + hint_messages)

    await manager.save(history)

    # Verify file was created
    assert conv_path.exists()

    # Load the conversation
    loaded_history = await manager.load()
    assert loaded_history is not None
    assert len(loaded_history.agent_history) == 1
    assert loaded_history.last_agent_model == "research"

    # Verify we can get the messages back
    loaded_messages = loaded_history.get_agent_messages()
    assert len(loaded_messages) == 1
    assert isinstance(loaded_messages[0], ModelRequest)

    loaded_ui_messages = loaded_history.get_ui_messages()
    assert len(loaded_ui_messages) == 2
    assert isinstance(loaded_ui_messages[0], ModelRequest)
    assert isinstance(loaded_ui_messages[1], HintMessage)


@pytest.mark.asyncio
async def test_conversation_manager_nonexistent_file(tmp_path):
    """Test ConversationManager with nonexistent file."""
    conv_path = tmp_path / "nonexistent.json"
    manager = ConversationManager(conversation_path=conv_path)

    # Should return None for nonexistent file
    loaded = await manager.load()
    assert loaded is None

    # Check exists method
    assert not await manager.exists()


@pytest.mark.asyncio
async def test_conversation_manager_clear(tmp_path):
    """Test ConversationManager clear functionality."""
    conv_path = tmp_path / "test_conversation.json"
    manager = ConversationManager(conversation_path=conv_path)

    # Save a conversation
    history = ConversationHistory()
    await manager.save(history)
    assert conv_path.exists()

    # Clear the conversation
    await manager.clear()
    assert not conv_path.exists()


@pytest.mark.asyncio
async def test_conversation_manager_corrupt_file(tmp_path):
    """Test ConversationManager with corrupt JSON file."""
    conv_path = tmp_path / "corrupt.json"

    # Create a corrupt JSON file
    with open(conv_path, "w") as f:
        f.write("{invalid json}")

    manager = ConversationManager(conversation_path=conv_path)

    # Should return None for corrupt file
    loaded = await manager.load()
    assert loaded is None


def test_conversation_history_version_compatibility():
    """Test that conversation history maintains version compatibility."""
    # Create history with specific version
    history = ConversationHistory(version=1)
    assert history.version == 1

    # Serialize and deserialize
    json_data = history.model_dump(mode="json")
    loaded_history = ConversationHistory.model_validate(json_data)

    assert loaded_history.version == 1


def test_empty_agent_messages():
    """Test handling of empty agent messages."""
    history = ConversationHistory()

    # Get empty agent messages
    messages = history.get_agent_messages()
    assert messages == []

    # Set empty list
    history.set_agent_messages([])
    assert history.agent_history == []

    messages = history.get_agent_messages()
    assert messages == []


def test_conversation_state_creation():
    """Test ConversationState model creation."""
    # Create some model messages
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Test prompt")]),
        ModelResponse(parts=[TextPart(content="Test response")]),
    ]

    # Create ConversationState
    state = ConversationState(
        agent_messages=messages,
        agent_type="research",
    )

    assert len(state.agent_messages) == 2
    assert state.agent_type == "research"
    assert isinstance(state.agent_messages[0], ModelRequest)
    assert isinstance(state.agent_messages[1], ModelResponse)
    assert state.ui_messages == []


def test_conversation_history_ui_messages_with_hints():
    """UI messages should round-trip with hint messages preserved."""

    messages = [
        ModelRequest(parts=[UserPromptPart(content="Prompt")]),
        ModelResponse(parts=[TextPart(content="Answer")]),
        HintMessage(message="Useful tip"),
    ]

    history = ConversationHistory()
    history.set_ui_messages(messages)

    stored = history.ui_history
    assert len(stored) == 3
    assert stored[-1]["message_type"] == "hint"

    retrieved = history.get_ui_messages()
    assert len(retrieved) == 3
    assert isinstance(retrieved[0], ModelRequest)
    assert isinstance(retrieved[1], ModelResponse)
    assert isinstance(retrieved[2], HintMessage)


def test_filter_orphaned_tool_responses_removes_orphans():
    """Test that orphaned tool responses are filtered out."""
    # Create messages with orphaned tool response (no matching tool call)
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Read a file")]),
        # Note: No ModelResponse with ToolCallPart for "orphan-id"
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="file_read",
                    content="file contents",
                    tool_call_id="orphan-id",
                )
            ]
        ),
    ]

    filtered = filter_orphaned_tool_responses(messages)

    # The orphaned tool response should be removed entirely
    # since ModelRequest only had the ToolReturnPart
    assert len(filtered) == 1
    assert isinstance(filtered[0], ModelRequest)
    assert isinstance(filtered[0].parts[0], UserPromptPart)


def test_filter_orphaned_tool_responses_preserves_valid_pairs():
    """Test that valid tool call/response pairs are preserved."""
    tool_call_id = "valid-id-123"

    messages = [
        ModelRequest(parts=[UserPromptPart(content="Read a file")]),
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="file_read",
                    args={"path": "/test.txt"},
                    tool_call_id=tool_call_id,
                )
            ]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="file_read",
                    content="file contents",
                    tool_call_id=tool_call_id,
                )
            ]
        ),
    ]

    filtered = filter_orphaned_tool_responses(messages)

    # All messages should be preserved
    assert len(filtered) == 3
    assert isinstance(filtered[2], ModelRequest)
    assert isinstance(filtered[2].parts[0], ToolReturnPart)


def test_filter_orphaned_tool_responses_mixed_scenario():
    """Test filtering with mix of valid and orphaned tool responses."""
    valid_id = "valid-id"
    orphan_id = "orphan-id"

    messages = [
        ModelRequest(parts=[UserPromptPart(content="Do things")]),
        # Valid tool call
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="valid_tool",
                    args={},
                    tool_call_id=valid_id,
                )
            ]
        ),
        # Request with both valid and orphaned tool responses
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="valid_tool",
                    content="valid result",
                    tool_call_id=valid_id,
                ),
                ToolReturnPart(
                    tool_name="orphan_tool",
                    content="orphan result",
                    tool_call_id=orphan_id,
                ),
            ]
        ),
    ]

    filtered = filter_orphaned_tool_responses(messages)

    # All 3 messages should exist, but last one should only have valid tool return
    assert len(filtered) == 3
    last_request = filtered[2]
    assert isinstance(last_request, ModelRequest)
    assert len(last_request.parts) == 1
    tool_return = last_request.parts[0]
    assert isinstance(tool_return, ToolReturnPart)
    assert tool_return.tool_call_id == valid_id


def test_filter_orphaned_tool_responses_preserves_other_parts():
    """Test that non-tool parts in ModelRequest are preserved."""
    orphan_id = "orphan-id"

    messages = [
        ModelRequest(
            parts=[
                UserPromptPart(content="User message"),
                ToolReturnPart(
                    tool_name="orphan_tool",
                    content="orphan result",
                    tool_call_id=orphan_id,
                ),
            ]
        ),
    ]

    filtered = filter_orphaned_tool_responses(messages)

    # Message should still exist with just the UserPromptPart
    assert len(filtered) == 1
    assert isinstance(filtered[0], ModelRequest)
    assert len(filtered[0].parts) == 1
    assert isinstance(filtered[0].parts[0], UserPromptPart)


def test_filter_orphaned_tool_responses_empty_list():
    """Test filtering with empty message list."""
    filtered = filter_orphaned_tool_responses([])
    assert filtered == []


def test_filter_orphaned_tool_responses_no_tool_messages():
    """Test filtering when there are no tool-related messages."""
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(parts=[TextPart(content="Hi there!")]),
    ]

    filtered = filter_orphaned_tool_responses(messages)

    # All messages should be unchanged
    assert len(filtered) == 2
    assert filtered == messages
