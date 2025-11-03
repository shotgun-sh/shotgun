"""Unit tests for the clear CLI command."""

from pathlib import Path
from unittest.mock import patch

from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart
from typer.testing import CliRunner

from shotgun.agents.conversation_history import ConversationHistory
from shotgun.agents.conversation_manager import ConversationManager
from shotgun.cli.clear import app

runner = CliRunner()


def test_clear_conversation_success(tmp_path):
    """Test successfully clearing conversation."""
    # Create a conversation file
    conversation_file = tmp_path / ".shotgun-sh" / "conversation.json"
    conversation_file.parent.mkdir(parents=True)

    # Create and save a conversation
    history = ConversationHistory()
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Test prompt")]),
        ModelResponse(parts=[TextPart(content="Test response")]),
    ]
    history.set_agent_messages(messages)

    manager = ConversationManager(conversation_file)
    manager.save(history)

    # Verify file exists
    assert conversation_file.exists()

    # Run clear command
    with patch("shotgun.cli.clear.Path.home", return_value=tmp_path):
        result = runner.invoke(app)

    assert result.exit_code == 0
    assert "✓" in result.stdout
    assert "Conversation cleared successfully" in result.stdout

    # Verify file was deleted
    assert not conversation_file.exists()


def test_clear_conversation_no_file(tmp_path):
    """Test clearing when no conversation file exists."""
    # Ensure the file doesn't exist
    conversation_file = tmp_path / ".shotgun-sh" / "conversation.json"
    assert not conversation_file.exists()

    # Run clear command
    with patch("shotgun.cli.clear.Path.home", return_value=tmp_path):
        result = runner.invoke(app)

    assert result.exit_code == 0
    assert "No conversation file found" in result.stdout
    assert "Nothing to clear" in result.stdout


def test_clear_conversation_file_error(tmp_path):
    """Test error handling when file deletion fails."""
    conversation_file = tmp_path / ".shotgun-sh" / "conversation.json"
    conversation_file.parent.mkdir(parents=True)

    # Create the file
    history = ConversationHistory()
    manager = ConversationManager(conversation_file)
    manager.save(history)

    # Mock ConversationManager.clear() to raise an error
    with (
        patch("shotgun.cli.clear.Path.home", return_value=tmp_path),
        patch.object(
            ConversationManager,
            "clear",
            side_effect=PermissionError("Access denied"),
        ),
    ):
        result = runner.invoke(app)

    assert result.exit_code == 1
    assert "Error:" in result.stdout
    assert "Failed to clear conversation" in result.stdout


def test_clear_preserves_other_files(tmp_path):
    """Test that clear only removes conversation.json and not other files."""
    shotgun_dir = tmp_path / ".shotgun-sh"
    shotgun_dir.mkdir(parents=True)

    # Create various files
    conversation_file = shotgun_dir / "conversation.json"
    config_file = shotgun_dir / "config.json"
    usage_file = shotgun_dir / "usage.json"
    logs_dir = shotgun_dir / "logs"
    logs_dir.mkdir()

    # Create conversation
    history = ConversationHistory()
    manager = ConversationManager(conversation_file)
    manager.save(history)

    # Create other files
    config_file.write_text('{"key": "value"}')
    usage_file.write_text('{"usage": 100}')
    (logs_dir / "app.log").write_text("log content")

    # Verify all files exist
    assert conversation_file.exists()
    assert config_file.exists()
    assert usage_file.exists()
    assert (logs_dir / "app.log").exists()

    # Run clear command
    with patch("shotgun.cli.clear.Path.home", return_value=tmp_path):
        result = runner.invoke(app)

    assert result.exit_code == 0

    # Verify only conversation.json was deleted
    assert not conversation_file.exists()
    assert config_file.exists()
    assert usage_file.exists()
    assert (logs_dir / "app.log").exists()
