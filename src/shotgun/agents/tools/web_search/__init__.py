"""Web search tools for Pydantic AI agents.

Provides web search capabilities for multiple LLM providers:
- OpenAI: Uses Responses API with web_search tool
- Anthropic: Uses Messages API with web_search_20250305 tool
- Gemini: Uses grounding with Google Search
"""

from collections.abc import Callable

from shotgun.agents.config.models import ProviderType
from shotgun.logging_config import get_logger

from .anthropic import anthropic_web_search_tool
from .gemini import gemini_web_search_tool
from .openai import openai_web_search_tool
from .utils import is_provider_available

logger = get_logger(__name__)

# Type alias for web search tools
WebSearchTool = Callable[[str], str]


def get_available_web_search_tools() -> list[WebSearchTool]:
    """Get list of available web search tools based on configured API keys.

    Returns:
        List of web search tool functions that have API keys configured
    """
    tools: list[WebSearchTool] = []

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
