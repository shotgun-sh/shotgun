"""Manager for handling conversation persistence operations."""

import json
from pathlib import Path

from shotgun.logging_config import get_logger
from shotgun.utils import get_shotgun_home

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

    def save(self, conversation: ConversationHistory) -> None:
        """Save conversation history to file.

        Args:
            conversation: ConversationHistory to save
        """
        # Ensure directory exists
        self.conversation_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Update timestamp
            from datetime import datetime

            conversation.updated_at = datetime.now()

            # Serialize to JSON using Pydantic's model_dump
            data = conversation.model_dump(mode="json")

            with open(self.conversation_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.debug("Conversation saved to %s", self.conversation_path)

        except Exception as e:
            logger.error(
                "Failed to save conversation to %s: %s", self.conversation_path, e
            )
            # Don't raise - we don't want to interrupt the user's session

    def load(self) -> ConversationHistory | None:
        """Load conversation history from file.

        Returns:
            ConversationHistory if file exists and is valid, None otherwise
        """
        if not self.conversation_path.exists():
            logger.debug("No conversation history found at %s", self.conversation_path)
            return None

        try:
            with open(self.conversation_path, encoding="utf-8") as f:
                data = json.load(f)

            conversation = ConversationHistory.model_validate(data)
            logger.debug(
                "Conversation loaded from %s with %d agent messages",
                self.conversation_path,
                len(conversation.agent_history),
            )
            return conversation

        except Exception as e:
            logger.error(
                "Failed to load conversation from %s: %s", self.conversation_path, e
            )
            return None

    def clear(self) -> None:
        """Delete the conversation history file."""
        if self.conversation_path.exists():
            try:
                self.conversation_path.unlink()
                logger.debug(
                    "Conversation history cleared at %s", self.conversation_path
                )
            except Exception as e:
                logger.error(
                    "Failed to clear conversation at %s: %s", self.conversation_path, e
                )

    def exists(self) -> bool:
        """Check if a conversation history file exists.

        Returns:
            True if conversation file exists, False otherwise
        """
        return self.conversation_path.exists()
