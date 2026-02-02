"""Services for TUI business logic."""

from shotgun.tui.services.conversation_service import ConversationService
from shotgun.tui.services.ollama import (
    OllamaCapability,
    OllamaModel,
    OllamaStatus,
    get_ollama_status,
)

__all__ = [
    "ConversationService",
    "OllamaCapability",
    "OllamaModel",
    "OllamaStatus",
    "get_ollama_status",
]
