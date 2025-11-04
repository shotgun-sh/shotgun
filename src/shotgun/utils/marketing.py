"""Marketing message management for Shotgun CLI."""

from datetime import datetime, timezone
from pathlib import Path

from shotgun.agents.config.models import MarketingConfig, MarketingMessageRecord
from shotgun.agents.models import FileOperation

# Marketing message IDs
GITHUB_STAR_MESSAGE_ID = "github_star_v1"

# Spec files that trigger the GitHub star message
SPEC_FILES = {"research.md", "specification.md", "plan.md", "tasks.md"}


class MarketingManager:
    """Manages marketing messages shown to users."""

    @staticmethod
    def should_show_github_star_message(
        marketing_config: MarketingConfig, file_operations: list[FileOperation]
    ) -> bool:
        """
        Check if the GitHub star message should be shown.

        Args:
            marketing_config: Current marketing configuration
            file_operations: List of file operations from the current agent run

        Returns:
            True if message should be shown, False otherwise
        """
        # Check if message has already been shown
        if GITHUB_STAR_MESSAGE_ID in marketing_config.messages:
            return False

        # Check if any spec file was written
        for operation in file_operations:
            # operation.file_path is a string, so we convert to Path to get the filename
            file_name = Path(operation.file_path).name
            if file_name in SPEC_FILES:
                return True

        return False

    @staticmethod
    def mark_message_shown(
        marketing_config: MarketingConfig, message_id: str
    ) -> MarketingConfig:
        """
        Mark a marketing message as shown.

        Args:
            marketing_config: Current marketing configuration
            message_id: ID of the message to mark as shown

        Returns:
            Updated marketing configuration
        """
        # Create a new record with current timestamp
        record = MarketingMessageRecord(shown_at=datetime.now(timezone.utc))

        # Update the messages dict
        marketing_config.messages[message_id] = record

        return marketing_config

    @staticmethod
    def get_github_star_message() -> str:
        """Get the GitHub star marketing message text."""
        return "⭐ Enjoying Shotgun? Star us on GitHub: https://github.com/shotgun-sh/shotgun"
