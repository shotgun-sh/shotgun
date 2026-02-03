"""Services for TUI business logic."""

from shotgun.tui.services.conversation_service import ConversationService
from shotgun.tui.services.lm_studio import (
    LMStudioModel,
    LMStudioStatus,
    get_lm_studio_status,
    has_lm_studio_models_available,
)
from shotgun.tui.services.ollama import (
    OllamaCapability,
    OllamaModel,
    OllamaStatus,
    get_ollama_status,
    has_ollama_models_available,
)

__all__ = [
    "ConversationService",
    "LMStudioModel",
    "LMStudioStatus",
    "get_lm_studio_status",
    "has_lm_studio_models_available",
    "OllamaCapability",
    "OllamaModel",
    "OllamaStatus",
    "get_ollama_status",
    "has_ollama_models_available",
]
