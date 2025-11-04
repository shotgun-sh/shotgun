"""Manager for handling conversation persistence operations."""

import asyncio
import json
from pathlib import Path

import aiofiles
import aiofiles.os

from shotgun.logging_config import get_logger
from shotgun.utils import get_shotgun_home
from shotgun.utils.file_system_utils import async_copy_file

from .conversation_history import ConversationHistory

logger = get_logger(__name__)


class ConversationManager:
    """Handles saving and loading conversation history."""

    def __init__(self, conversation_path: Path | None = None):
        """Initialize ConversationManager.

        Args:
            conversation_path: Path to conversation file.
                              If None, uses default ~/.shotgun-sh/conversation.json
        """
        if conversation_path is None:
            self.conversation_path = get_shotgun_home() / "conversation.json"
        else:
            self.conversation_path = conversation_path

    async def save(self, conversation: ConversationHistory) -> None:
        """Save conversation history to file.

        Args:
            conversation: ConversationHistory to save
        """
        # Ensure directory exists
        await aiofiles.os.makedirs(self.conversation_path.parent, exist_ok=True)

        try:
            # Update timestamp
            from datetime import datetime

            conversation.updated_at = datetime.now()

            # Serialize to JSON in background thread to avoid blocking event loop
            # This is crucial for large conversations (5k+ tokens)
            data = await asyncio.to_thread(conversation.model_dump, mode="json")
            json_content = await asyncio.to_thread(
                json.dumps, data, indent=2, ensure_ascii=False
            )

            async with aiofiles.open(
                self.conversation_path, "w", encoding="utf-8"
            ) as f:
                await f.write(json_content)

            logger.debug("Conversation saved to %s", self.conversation_path)

        except Exception as e:
            logger.error(
                "Failed to save conversation to %s: %s", self.conversation_path, e
            )
            # Don't raise - we don't want to interrupt the user's session

    async def load(self) -> ConversationHistory | None:
        """Load conversation history from file.

        Returns:
            ConversationHistory if file exists and is valid, None otherwise
        """
        if not await aiofiles.os.path.exists(self.conversation_path):
            logger.debug("No conversation history found at %s", self.conversation_path)
            return None

        try:
            async with aiofiles.open(self.conversation_path, encoding="utf-8") as f:
                content = await f.read()
                # Deserialize JSON in background thread to avoid blocking
                data = await asyncio.to_thread(json.loads, content)

            # Validate model in background thread for large conversations
            conversation = await asyncio.to_thread(
                ConversationHistory.model_validate, data
            )
            logger.debug(
                "Conversation loaded from %s with %d agent messages",
                self.conversation_path,
                len(conversation.agent_history),
            )
            return conversation

        except (json.JSONDecodeError, ValueError) as e:
            # Handle corrupted JSON or validation errors
            logger.error(
                "Corrupted conversation file at %s: %s. Creating backup and starting fresh.",
                self.conversation_path,
                e,
            )

            # Create a backup of the corrupted file for debugging
            backup_path = self.conversation_path.with_suffix(".json.backup")
            try:
                await async_copy_file(self.conversation_path, backup_path)
                logger.info("Backed up corrupted conversation to %s", backup_path)
            except Exception as backup_error:  # pragma: no cover
                logger.warning("Failed to backup corrupted file: %s", backup_error)

            return None

        except Exception as e:  # pragma: no cover
            # Catch-all for unexpected errors
            logger.error(
                "Unexpected error loading conversation from %s: %s",
                self.conversation_path,
                e,
            )
            return None

    async def clear(self) -> None:
        """Delete the conversation history file."""
        if await aiofiles.os.path.exists(self.conversation_path):
            try:
                # Use asyncio.to_thread for unlink operation
                await asyncio.to_thread(self.conversation_path.unlink)
                logger.debug(
                    "Conversation history cleared at %s", self.conversation_path
                )
            except Exception as e:
                logger.error(
                    "Failed to clear conversation at %s: %s", self.conversation_path, e
                )

    async def exists(self) -> bool:
        """Check if a conversation history file exists.

        Returns:
            True if conversation file exists, False otherwise
        """
        return await aiofiles.os.path.exists(str(self.conversation_path))
