"""Service for managing conversation persistence and restoration.

This service extracts conversation save/load/restore logic from ChatScreen,
making it testable and reusable.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import aiofiles.os

from shotgun.agents.conversation_history import ConversationHistory, ConversationState
from shotgun.agents.conversation_manager import ConversationManager
from shotgun.agents.models import AgentType

if TYPE_CHECKING:
    from shotgun.agents.agent_manager import AgentManager
    from shotgun.agents.usage_manager import SessionUsageManager

logger = logging.getLogger(__name__)


class ConversationService:
    """Handles conversation persistence and restoration.

    This service provides:
    - Save current conversation to disk
    - Load conversation from disk
    - Restore conversation state to agent manager
    - Handle corrupted conversations gracefully
    """

    def __init__(
        self,
        conversation_manager: ConversationManager | None = None,
        conversation_path: Path | None = None,
    ):
        """Initialize the conversation service.

        Args:
            conversation_manager: Optional conversation manager. If not provided,
                                creates a default one.
            conversation_path: Optional custom path for conversation storage.
        """
        if conversation_manager:
            self.conversation_manager = conversation_manager
        elif conversation_path:
            self.conversation_manager = ConversationManager(conversation_path)
        else:
            self.conversation_manager = ConversationManager()

    async def save_conversation(self, agent_manager: "AgentManager") -> bool:
        """Save the current conversation to persistent storage.

        Args:
            agent_manager: The agent manager containing conversation state.

        Returns:
            True if save was successful, False otherwise.
        """
        try:
            # Get conversation state from agent manager
            state = agent_manager.get_conversation_state()

            # Create conversation history object
            conversation = ConversationHistory(
                last_agent_model=state.agent_type,
            )
            conversation.set_agent_messages(state.agent_messages)
            conversation.set_ui_messages(state.ui_messages)

            # Save to file (now async)
            await self.conversation_manager.save(conversation)
            logger.debug("Conversation saved successfully")
            return True
        except Exception as e:
            logger.exception(f"Failed to save conversation: {e}")
            return False

    async def load_conversation(self) -> ConversationHistory | None:
        """Load conversation from persistent storage.

        Returns:
            The loaded conversation history, or None if no conversation exists
            or if loading failed.
        """
        try:
            conversation = await self.conversation_manager.load()
            if conversation is None:
                logger.debug("No conversation file found")
                return None

            logger.debug("Conversation loaded successfully")
            return conversation
        except Exception as e:
            logger.exception(f"Failed to load conversation: {e}")
            return None

    async def check_for_corrupted_conversation(self) -> bool:
        """Check if a conversation backup exists (indicating corruption).

        Returns:
            True if a backup exists (conversation was corrupted), False otherwise.
        """
        backup_path = self.conversation_manager.conversation_path.with_suffix(
            ".json.backup"
        )
        return await aiofiles.os.path.exists(str(backup_path))

    async def restore_conversation(
        self,
        agent_manager: "AgentManager",
        usage_manager: "SessionUsageManager | None" = None,
    ) -> tuple[bool, str | None, AgentType | None]:
        """Restore conversation state from disk.

        Args:
            agent_manager: The agent manager to restore state to.
            usage_manager: Optional usage manager to restore usage state.

        Returns:
            Tuple of (success, error_message, restored_agent_type)
            - success: True if restoration succeeded
            - error_message: Error message if restoration failed, None otherwise
            - restored_agent_type: The agent type from restored conversation
        """
        conversation = await self.load_conversation()

        if conversation is None:
            # Check for corruption
            if await self.check_for_corrupted_conversation():
                return (
                    False,
                    "⚠️ Previous session was corrupted and has been backed up. Starting fresh conversation.",
                    None,
                )
            return True, None, None  # No conversation to restore is not an error

        try:
            # Restore agent state
            agent_messages = conversation.get_agent_messages()
            ui_messages = conversation.get_ui_messages()

            # Create ConversationState for restoration
            state = ConversationState(
                agent_messages=agent_messages,
                ui_messages=ui_messages,
                agent_type=conversation.last_agent_model,
            )

            agent_manager.restore_conversation_state(state)

            # Restore usage state if manager provided
            if usage_manager:
                await usage_manager.restore_usage_state()

            restored_type = AgentType(conversation.last_agent_model)
            logger.info(f"Conversation restored successfully (mode: {restored_type})")
            return True, None, restored_type

        except Exception as e:
            logger.exception(f"Failed to restore conversation state: {e}")
            return (
                False,
                "⚠️ Could not restore previous session. Starting fresh conversation.",
                None,
            )

    async def clear_conversation(self) -> bool:
        """Clear the saved conversation file.

        Returns:
            True if clearing succeeded, False otherwise.
        """
        try:
            conversation_path = self.conversation_manager.conversation_path
            if await aiofiles.os.path.exists(str(conversation_path)):
                await aiofiles.os.unlink(str(conversation_path))
                logger.info("Conversation file cleared")
            return True
        except Exception as e:
            logger.exception(f"Failed to clear conversation: {e}")
            return False
