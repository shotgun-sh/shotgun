"""Web search tools for Pydantic AI agents.

Provides web search capabilities for multiple LLM providers:
- OpenAI: Uses Responses API with web_search tool (BYOK only)
- Anthropic: Uses Messages API with web_search_20250305 tool (BYOK only)
- Gemini: Uses grounding with Google Search via Pydantic AI (Shotgun Account and BYOK)

Shotgun Account: Only Gemini web search is available
BYOK: All tools work with direct provider API keys
"""

from collections.abc import Awaitable, Callable

from shotgun.agents.config import get_config_manager
from shotgun.agents.config.models import ProviderType
from shotgun.logging_config import get_logger

from .anthropic import anthropic_web_search_tool
from .gemini import gemini_web_search_tool
from .openai import openai_web_search_tool
from .utils import is_provider_available

logger = get_logger(__name__)

# Type alias for web search tools (all now async)
WebSearchTool = Callable[[str], Awaitable[str]]


async def get_available_web_search_tools() -> list[WebSearchTool]:
    """Get list of available web search tools based on configured API keys.

    Works with both Shotgun Account (via LiteLLM proxy) and BYOK (individual provider keys).

    Available tools:
    - Gemini: Available for both Shotgun Account and BYOK
    - Anthropic: BYOK only (uses Messages API with web search)
    - OpenAI: BYOK only (uses Responses API not compatible with LiteLLM proxy)

    Returns:
        List of web search tool functions that have API keys configured
    """
    tools: list[WebSearchTool] = []

    # Check if using Shotgun Account
    config_manager = get_config_manager()
    config = await config_manager.load()
    has_shotgun_key = config.shotgun.api_key is not None

    if has_shotgun_key:
        logger.debug("🔑 Shotgun Account - only Gemini web search available")

        # Gemini: Only search tool available for Shotgun Account
        if await is_provider_available(ProviderType.GOOGLE):
            logger.debug("✅ Gemini web search tool available")
            tools.append(gemini_web_search_tool)

        # Anthropic: Not available for Shotgun Account (Gemini-only for Shotgun)
        if await is_provider_available(ProviderType.ANTHROPIC):
            logger.debug(
                "⚠️  Anthropic web search requires BYOK (Shotgun Account uses Gemini only)"
            )

        # OpenAI: Not available for Shotgun Account (Responses API incompatible with proxy)
        if await is_provider_available(ProviderType.OPENAI):
            logger.debug(
                "⚠️  OpenAI web search requires BYOK (Responses API not supported via proxy)"
            )
    else:
        # BYOK mode: Load all available tools based on individual provider keys
        logger.debug("🔑 BYOK mode - checking all provider web search tools")

        if await is_provider_available(ProviderType.OPENAI):
            logger.debug("✅ OpenAI web search tool available")
            tools.append(openai_web_search_tool)

        if await is_provider_available(ProviderType.ANTHROPIC):
            logger.debug("✅ Anthropic web search tool available")
            tools.append(anthropic_web_search_tool)

        if await is_provider_available(ProviderType.GOOGLE):
            logger.debug("✅ Gemini web search tool available")
            tools.append(gemini_web_search_tool)

    if not tools:
        logger.warning("⚠️ No web search tools available - no API keys configured")
    else:
        logger.info("🔍 %d web search tool(s) available", len(tools))

    return tools


__all__ = [
    "openai_web_search_tool",
    "anthropic_web_search_tool",
    "gemini_web_search_tool",
    "get_available_web_search_tools",
    "is_provider_available",
    "WebSearchTool",
]
