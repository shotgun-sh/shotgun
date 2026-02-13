"""Web search tools for Pydantic AI agents.

Provides web search capabilities for multiple LLM providers:
- OpenAI: Uses Responses API with web_search tool
- Anthropic: Uses Messages API with web_search_20250305 tool
- Gemini: Uses grounding with Google Search via Pydantic AI
- OpenAI-compatible: Uses Responses API via custom endpoint (e.g., LiteLLM proxy)

For BYOK users, Gemini Flash web search is preferred when a Google API key is available,
as it provides the most reliable grounded search results. Falls back to other providers
if Google is not configured.
"""

from collections.abc import Awaitable, Callable

from shotgun.agents.config.manager import get_config_manager
from shotgun.agents.config.models import ProviderType
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
    """Get the best available web search tool.

    For Shotgun Account users, always uses Gemini web search.
    For BYOK users, prefers Gemini Flash web search when a Google API key is available.
    Falls back to other available providers if Google is not configured.

    Returns:
        List containing the preferred web search tool, or empty if none available
    """
    logger.debug("Checking available web search tools")

    # Priority 0: Check for OpenAI-compatible mode
    if settings.openai_compat.base_url and settings.openai_compat.api_key:
        logger.info("Using OpenAI-compatible web search (openai_compat mode enabled)")
        return [openai_compatible_web_search_tool]

    config_manager = get_config_manager()
    config = await config_manager.load(force_reload=False)

    # Priority 1: Shotgun Account always uses Gemini web search
    if config.shotgun.api_key:
        logger.info("Using Gemini web search (Shotgun Account)")
        return [gemini_web_search_tool]

    # Priority 2: For BYOK users, prefer Gemini web search when available
    # Gemini Flash grounded search is the most reliable web search option
    if await is_provider_available(ProviderType.GOOGLE):
        logger.info("Using Gemini web search (preferred for BYOK)")
        return [gemini_web_search_tool]

    # Fall back to other available providers
    for provider in ProviderType:
        if provider in (ProviderType.OPENAI_COMPATIBLE, ProviderType.GOOGLE):
            # OPENAI_COMPATIBLE handled above, GOOGLE already checked
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
