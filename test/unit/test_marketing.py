"""Unit tests for MarketingManager."""

from datetime import datetime, timezone

import pytest

from shotgun.agents.config.models import MarketingConfig, MarketingMessageRecord
from shotgun.agents.models import FileOperation, FileOperationType
from shotgun.utils.marketing import (
    GITHUB_STAR_MESSAGE_ID,
    SPEC_FILES,
    MarketingManager,
)


def test_should_show_github_star_message_not_shown_yet():
    """Test that message should be shown when not shown yet and spec file written."""
    marketing_config = MarketingConfig(messages={})
    file_operations = [
        FileOperation(
            file_path="/path/to/research.md",
            operation=FileOperationType.CREATED,
        )
    ]

    result = MarketingManager.should_show_github_star_message(
        marketing_config, file_operations
    )

    assert result is True


def test_should_show_github_star_message_already_shown():
    """Test that message should not be shown when already shown."""
    marketing_config = MarketingConfig(
        messages={
            GITHUB_STAR_MESSAGE_ID: MarketingMessageRecord(
                shown_at=datetime.now(timezone.utc)
            )
        }
    )
    file_operations = [
        FileOperation(
            file_path="/path/to/research.md",
            operation=FileOperationType.CREATED,
        )
    ]

    result = MarketingManager.should_show_github_star_message(
        marketing_config, file_operations
    )

    assert result is False


def test_should_show_github_star_message_no_spec_files():
    """Test that message should not be shown when no spec files written."""
    marketing_config = MarketingConfig(messages={})
    file_operations = [
        FileOperation(
            file_path="/path/to/random_file.txt",
            operation=FileOperationType.CREATED,
        )
    ]

    result = MarketingManager.should_show_github_star_message(
        marketing_config, file_operations
    )

    assert result is False


def test_should_show_github_star_message_empty_operations():
    """Test that message should not be shown when no file operations."""
    marketing_config = MarketingConfig(messages={})
    file_operations = []

    result = MarketingManager.should_show_github_star_message(
        marketing_config, file_operations
    )

    assert result is False


@pytest.mark.parametrize("spec_file", SPEC_FILES)
def test_should_show_github_star_message_all_spec_files(spec_file):
    """Test that all spec files trigger the message."""
    marketing_config = MarketingConfig(messages={})
    file_operations = [
        FileOperation(
            file_path=f"/path/to/{spec_file}",
            operation=FileOperationType.CREATED,
        )
    ]

    result = MarketingManager.should_show_github_star_message(
        marketing_config, file_operations
    )

    assert result is True


def test_should_show_github_star_message_mixed_files():
    """Test that message shows when spec file is mixed with other files."""
    marketing_config = MarketingConfig(messages={})
    file_operations = [
        FileOperation(
            file_path="/path/to/random.txt",
            operation=FileOperationType.CREATED,
        ),
        FileOperation(
            file_path="/path/to/spec.md",
            operation=FileOperationType.CREATED,
        ),
        FileOperation(
            file_path="/path/to/specification.md",
            operation=FileOperationType.UPDATED,
        ),
    ]

    result = MarketingManager.should_show_github_star_message(
        marketing_config, file_operations
    )

    assert result is True


def test_mark_message_shown():
    """Test marking a message as shown."""
    marketing_config = MarketingConfig(messages={})

    result = MarketingManager.mark_message_shown(
        marketing_config, GITHUB_STAR_MESSAGE_ID
    )

    assert GITHUB_STAR_MESSAGE_ID in result.messages
    assert isinstance(result.messages[GITHUB_STAR_MESSAGE_ID].shown_at, datetime)


def test_mark_message_shown_custom_id():
    """Test marking a custom message ID as shown."""
    marketing_config = MarketingConfig(messages={})
    custom_id = "custom_message_v1"

    result = MarketingManager.mark_message_shown(marketing_config, custom_id)

    assert custom_id in result.messages
    assert isinstance(result.messages[custom_id].shown_at, datetime)


def test_mark_message_shown_preserves_existing():
    """Test that marking a message as shown preserves existing messages."""
    existing_time = datetime.now(timezone.utc)
    marketing_config = MarketingConfig(
        messages={"existing_msg": MarketingMessageRecord(shown_at=existing_time)}
    )

    result = MarketingManager.mark_message_shown(
        marketing_config, GITHUB_STAR_MESSAGE_ID
    )

    assert "existing_msg" in result.messages
    assert result.messages["existing_msg"].shown_at == existing_time
    assert GITHUB_STAR_MESSAGE_ID in result.messages


def test_get_github_star_message():
    """Test getting the GitHub star message text."""
    message = MarketingManager.get_github_star_message()

    assert isinstance(message, str)
    assert "GitHub" in message
    assert "github.com/shotgun-sh/shotgun" in message
    assert "⭐" in message
