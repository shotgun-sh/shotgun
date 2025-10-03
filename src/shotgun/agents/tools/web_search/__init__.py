"""Web search tools for Pydantic AI agents.

Provides web search capabilities for multiple LLM providers:
- OpenAI: Uses Responses API with web_search tool (BYOK only)
- Anthropic: Uses Messages API with web_search_20250305 tool (BYOK only)
- Gemini: Uses grounding with Google Search via Pydantic AI (works with Shotgun Account)
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


def get_available_web_search_tools() -> list[WebSearchTool]:
    """Get list of available web search tools based on configured API keys.

    When using Shotgun Account (via LiteLLM proxy):
        Only Gemini web search is available (others use provider-specific APIs)

    When using BYOK (individual provider keys):
        All provider tools are available based on their respective keys

    Returns:
        List of web search tool functions that have API keys configured
    """
    tools: list[WebSearchTool] = []

    # Check if using Shotgun Account
    config_manager = get_config_manager()
    config = config_manager.load()
    has_shotgun_key = config.shotgun.api_key is not None

    if has_shotgun_key:
        # Shotgun Account mode: Only Gemini supports web search via LiteLLM
        if is_provider_available(ProviderType.GOOGLE):
            logger.info("🔑 Shotgun Account detected - using Gemini web search only")
            logger.debug("   OpenAI and Anthropic web search require direct API keys")
            tools.append(gemini_web_search_tool)
        else:
            logger.warning(
                "⚠️ Shotgun Account configured but no Gemini key - "
                "web search unavailable"
            )
    else:
        # BYOK mode: Load all available tools based on individual provider keys
        logger.debug("🔑 BYOK mode - checking all provider web search tools")

        if is_provider_available(ProviderType.OPENAI):
            logger.debug("✅ OpenAI web search tool available")
            tools.append(openai_web_search_tool)

        if is_provider_available(ProviderType.ANTHROPIC):
            logger.debug("✅ Anthropic web search tool available")
            tools.append(anthropic_web_search_tool)

        if is_provider_available(ProviderType.GOOGLE):
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
