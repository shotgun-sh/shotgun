"""Unit tests for the compact CLI command."""

from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart

from shotgun.agents.config.models import (
    KeyProvider,
    ModelConfig,
    ModelName,
    ProviderType,
)
from shotgun.agents.conversation import ConversationHistory, ConversationManager
from shotgun.cli.compact import compact_conversation, format_markdown


@pytest.fixture
def mock_conversation_history():
    """Create a mock conversation history with messages."""
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Test prompt 1")]),
        ModelResponse(parts=[TextPart(content="Test response 1")]),
        ModelRequest(parts=[UserPromptPart(content="Test prompt 2")]),
        ModelResponse(parts=[TextPart(content="Test response 2")]),
    ]

    history = ConversationHistory()
    history.set_agent_messages(messages)
    return history


@pytest.mark.asyncio
async def test_compact_conversation_success(tmp_path, mock_conversation_history):
    """Test successful conversation compaction."""
    # Create a temp conversation file
    conversation_file = tmp_path / ".shotgun-sh" / "conversation.json"
    conversation_file.parent.mkdir(parents=True)

    # Save mock conversation
    manager = ConversationManager(conversation_file)
    await manager.save(mock_conversation_history)

    # Mock the compaction to return fewer messages
    compacted_messages = [
        ModelRequest(parts=[UserPromptPart(content="Compacted summary")]),
        ModelResponse(parts=[TextPart(content="Summary response")]),
    ]

    # Create a proper ModelConfig for the test
    model_config = ModelConfig(
        name=ModelName.CLAUDE_SONNET_4_5,
        provider=ProviderType.ANTHROPIC,
        key_provider=KeyProvider.BYOK,
        max_input_tokens=200000,
        max_output_tokens=8000,
        api_key="test-api-key",
    )

    with (
        patch("shotgun.cli.compact.Path.home", return_value=tmp_path),
        patch("shotgun.cli.compact.get_provider_model", return_value=model_config),
        patch(
            "shotgun.cli.compact.token_limit_compactor",
            new_callable=AsyncMock,
            return_value=compacted_messages,
        ),
        patch(
            "shotgun.cli.compact.estimate_tokens_from_messages",
            new_callable=AsyncMock,
            side_effect=[1000, 500],  # Original and compacted token counts
        ),
    ):
        result = await compact_conversation()

        assert result["success"] is True
        assert result["before"]["messages"] == 4
        assert result["after"]["messages"] == 2
        assert result["before"]["estimated_tokens"] == 1000
        assert result["after"]["estimated_tokens"] == 500
        assert result["reduction"]["messages_percent"] == 50.0
        assert result["reduction"]["tokens_percent"] == 50.0

        # Verify the conversation was saved
        loaded = await manager.load()
        assert loaded is not None
        assert len(loaded.get_agent_messages()) == 2


@pytest.mark.asyncio
async def test_compact_conversation_no_file(tmp_path):
    """Test compaction when conversation file doesn't exist."""
    with patch("shotgun.cli.compact.Path.home", return_value=tmp_path):
        with pytest.raises(FileNotFoundError, match="Conversation file not found"):
            await compact_conversation()


@pytest.mark.asyncio
async def test_compact_conversation_empty_history(tmp_path):
    """Test compaction with empty conversation history."""
    conversation_file = tmp_path / ".shotgun-sh" / "conversation.json"
    conversation_file.parent.mkdir(parents=True)

    # Create empty conversation
    history = ConversationHistory()
    manager = ConversationManager(conversation_file)
    await manager.save(history)

    with patch("shotgun.cli.compact.Path.home", return_value=tmp_path):
        with pytest.raises(ValueError, match="No agent messages found"):
            await compact_conversation()


@pytest.mark.asyncio
async def test_compact_conversation_no_reduction(tmp_path, mock_conversation_history):
    """Test compaction when no reduction occurs."""
    conversation_file = tmp_path / ".shotgun-sh" / "conversation.json"
    conversation_file.parent.mkdir(parents=True)

    manager = ConversationManager(conversation_file)
    await manager.save(mock_conversation_history)

    # Mock compaction to return same messages (no compaction needed)
    original_messages = mock_conversation_history.get_agent_messages()

    # Create a proper ModelConfig for the test
    model_config = ModelConfig(
        name=ModelName.CLAUDE_SONNET_4_5,
        provider=ProviderType.ANTHROPIC,
        key_provider=KeyProvider.BYOK,
        max_input_tokens=200000,
        max_output_tokens=8000,
        api_key="test-api-key",
    )

    with (
        patch("shotgun.cli.compact.Path.home", return_value=tmp_path),
        patch("shotgun.cli.compact.get_provider_model", return_value=model_config),
        patch(
            "shotgun.cli.compact.token_limit_compactor",
            new_callable=AsyncMock,
            return_value=original_messages,
        ),
        patch(
            "shotgun.cli.compact.estimate_tokens_from_messages",
            new_callable=AsyncMock,
            return_value=1000,
        ),
    ):
        result = await compact_conversation()

        assert result["success"] is True
        assert result["before"]["messages"] == result["after"]["messages"]
        assert result["reduction"]["messages_percent"] == 0.0
        assert result["reduction"]["tokens_percent"] == 0.0


def test_format_markdown():
    """Test markdown formatting of compaction results."""
    result = {
        "success": True,
        "before": {
            "messages": 100,
            "estimated_tokens": 5000,
        },
        "after": {
            "messages": 50,
            "estimated_tokens": 2500,
        },
        "reduction": {
            "messages_percent": 50.0,
            "tokens_percent": 50.0,
        },
    }

    markdown = format_markdown(result)

    assert "# Conversation Compacted ✓" in markdown
    assert "100" in markdown
    assert "5,000" in markdown
    assert "50" in markdown
    assert "2,500" in markdown
    assert "50.0%" in markdown


def test_format_markdown_with_commas():
    """Test markdown formatting handles large numbers with comma separators."""
    result = {
        "success": True,
        "before": {
            "messages": 1000,
            "estimated_tokens": 50000,
        },
        "after": {
            "messages": 500,
            "estimated_tokens": 25000,
        },
        "reduction": {
            "messages_percent": 50.0,
            "tokens_percent": 50.0,
        },
    }

    markdown = format_markdown(result)

    # Check that numbers are formatted with commas
    assert "1,000" in markdown
    assert "50,000" in markdown
    assert "25,000" in markdown
