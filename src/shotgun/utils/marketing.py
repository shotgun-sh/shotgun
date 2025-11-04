"""Marketing message management for Shotgun CLI."""

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from shotgun.agents.config.models import MarketingConfig, MarketingMessageRecord
from shotgun.agents.models import FileOperation

if TYPE_CHECKING:
    from shotgun.agents.config.manager import ConfigManager

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

    @staticmethod
    async def check_and_display_messages(
        config_manager: "ConfigManager",
        file_operations: list[FileOperation],
        display_callback: Callable[[str], None],
    ) -> None:
        """
        Check if any marketing messages should be shown and display them.

        This is the main entry point for marketing message handling. It checks
        all configured messages, displays them if appropriate, and updates the
        config to mark them as shown.

        Args:
            config_manager: Config manager to load/save configuration
            file_operations: List of file operations from the current agent run
            display_callback: Callback function to display messages to the user
        """
        config = await config_manager.load()

        # Check GitHub star message
        if MarketingManager.should_show_github_star_message(
            config.marketing, file_operations
        ):
            # Display the message
            message = MarketingManager.get_github_star_message()
            display_callback(message)

            # Mark as shown and save
            MarketingManager.mark_message_shown(
                config.marketing, GITHUB_STAR_MESSAGE_ID
            )
            await config_manager.save(config)
