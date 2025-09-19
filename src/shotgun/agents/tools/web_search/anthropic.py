"""Anthropic web search tool implementation."""

import anthropic
from opentelemetry import trace

from shotgun.agents.config import get_provider_model
from shotgun.agents.config.models import ProviderType
from shotgun.logging_config import get_logger

logger = get_logger(__name__)


def anthropic_web_search_tool(query: str) -> str:
    """Perform a web search using Anthropic's Claude API.

    This tool uses Anthropic's web search capabilities to find current information
    about the given query.

    Args:
        query: The search query

    Returns:
        Search results as a formatted string
    """
    logger.debug("🔧 Invoking Anthropic web_search_tool with query: %s", query)

    span = trace.get_current_span()
    span.set_attribute("input.value", f"**Query:** {query}\n")

    logger.debug("📡 Executing Anthropic web search with prompt: %s", query)

    # Get API key from centralized configuration
    try:
        model_config = get_provider_model(ProviderType.ANTHROPIC)
        api_key = model_config.api_key
    except ValueError as e:
        error_msg = f"Anthropic API key not configured: {str(e)}"
        logger.error("❌ %s", error_msg)
        span.set_attribute("output.value", f"**Error:**\n {error_msg}\n")
        return error_msg

    client = anthropic.Anthropic(api_key=api_key)

    # Use the Messages API with web search tool
    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-latest",
            max_tokens=8192,  # Increased from 4096 for more comprehensive results
            messages=[{"role": "user", "content": f"Search for: {query}"}],
            tools=[
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                }
            ],
            tool_choice={"type": "tool", "name": "web_search"},
        )

        # Extract the search results from the response
        result_text = ""
        if hasattr(response, "content") and response.content:
            for content in response.content:
                if hasattr(content, "text"):
                    result_text += content.text
                elif hasattr(content, "tool_use") and content.tool_use:
                    # Handle tool use response
                    result_text += f"Search performed for: {query}\n"

        if not result_text:
            result_text = "No content returned from search"

        logger.debug("📄 Anthropic web search result: %d characters", len(result_text))
        logger.debug(
            "🔍 Result preview: %s...",
            result_text[:100] if result_text else "No result",
        )

        span.set_attribute("output.value", f"**Results:**\n {result_text}\n")

        return result_text
    except Exception as e:
        error_msg = f"Error performing Anthropic web search: {str(e)}"
        logger.error("❌ Anthropic web search failed: %s", str(e))
        logger.debug("💥 Full error details: %s", error_msg)
        span.set_attribute("output.value", f"**Error:**\n {error_msg}\n")
        return error_msg
