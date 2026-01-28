"""Web search tools for Pydantic AI agents.

Provides web search capabilities for multiple LLM providers:
- OpenAI: Uses Responses API with web_search tool
- Anthropic: Uses Messages API with web_search_20250305 tool
- Gemini: Uses grounding with Google Search via Pydantic AI
- OpenAI-compatible: Uses Responses API via custom endpoint (e.g., LiteLLM proxy)

Web search uses the provider matching the user's selected model for consistency.
"""

from collections.abc import Awaitable, Callable

from shotgun.agents.config.manager import get_config_manager
from shotgun.agents.config.models import MODEL_SPECS, ProviderType
from shotgun.logging_config import get_logger
from shotgun.settings import settings

from .anthropic import anthropic_web_search_tool
from .gemini import gemini_web_search_tool
from .openai import openai_web_search_tool
from .openai_compatible import openai_compatible_web_search_tool
from .utils import is_provider_available

logger = get_logger(__name__)

# Type alias for web search tools (all now async)
WebSearchTool = Callable[[str], Awaitable[str]]

# Map providers to their web search tools
_PROVIDER_WEB_SEARCH_TOOLS: dict[ProviderType, WebSearchTool] = {
    ProviderType.OPENAI: openai_web_search_tool,
    ProviderType.ANTHROPIC: anthropic_web_search_tool,
    ProviderType.GOOGLE: gemini_web_search_tool,
    ProviderType.OPENAI_COMPATIBLE: openai_compatible_web_search_tool,
}


async def get_available_web_search_tools() -> list[WebSearchTool]:
    """Get web search tool matching the user's selected provider.

    Prefers the web search tool from the same provider as the user's selected model.
    Falls back to other available providers if the preferred one isn't available.

    Returns:
        List containing the preferred web search tool, or empty if none available
    """
    logger.debug("Checking available web search tools")

    # Priority 0: Check for OpenAI-compatible mode
    if settings.openai_compat.base_url and settings.openai_compat.api_key:
        logger.info("Using OpenAI-compatible web search (openai_compat mode enabled)")
        return [openai_compatible_web_search_tool]

    # Get user's selected model to determine preferred provider
    config_manager = get_config_manager()
    config = await config_manager.load(force_reload=False)

    preferred_provider: ProviderType | None = None
    if config.selected_model and config.selected_model in MODEL_SPECS:
        preferred_provider = MODEL_SPECS[config.selected_model].provider
        logger.debug(
            "User selected model %s, preferring %s web search",
            config.selected_model.value,
            preferred_provider.value,
        )

    # Try preferred provider first
    if preferred_provider and await is_provider_available(preferred_provider):
        tool = _PROVIDER_WEB_SEARCH_TOOLS[preferred_provider]
        logger.info(
            "Using %s web search (matches selected model)", preferred_provider.value
        )
        return [tool]

    # Fall back to any available provider
    for provider in ProviderType:
        if provider == ProviderType.OPENAI_COMPATIBLE:
            # Skip OPENAI_COMPATIBLE in fallback - it's handled above
            continue
        if await is_provider_available(provider):
            tool = _PROVIDER_WEB_SEARCH_TOOLS[provider]
            logger.info("Using %s web search (fallback)", provider.value)
            return [tool]

    logger.warning("No web search tools available - no API keys configured")
    return []


__all__ = [
    "openai_web_search_tool",
    "anthropic_web_search_tool",
    "gemini_web_search_tool",
    "openai_compatible_web_search_tool",
    "get_available_web_search_tools",
    "is_provider_available",
    "WebSearchTool",
]
