"""Anthropic web search tool implementation."""

import anthropic
from opentelemetry import trace

from shotgun.agents.config import get_provider_model
from shotgun.agents.config.models import ProviderType
from shotgun.logging_config import get_logger

logger = get_logger(__name__)


def anthropic_web_search_tool(query: str) -> str:
    """Perform a web search using Anthropic's Claude API with streaming.

    This tool uses Anthropic's web search capabilities to find current information
    about the given query. Results are streamed for faster response times.

    Args:
        query: The search query

    Returns:
        Search results as a formatted string
    """
    logger.debug("🔧 Invoking Anthropic web_search_tool with query: %s", query)

    span = trace.get_current_span()
    span.set_attribute("input.value", f"**Query:** {query}\n")

    logger.debug("📡 Executing Anthropic web search with streaming prompt: %s", query)

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

    # Use the Messages API with web search tool and streaming
    try:
        result_text = ""

        with client.messages.stream(
            model="claude-3-5-sonnet-latest",
            max_tokens=8192,  # Maximum for Claude 3.5 Sonnet
            messages=[{"role": "user", "content": f"Search for: {query}"}],
            tools=[
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                }
            ],
            tool_choice={"type": "tool", "name": "web_search"},
        ) as stream:
            logger.debug("🌊 Started streaming Anthropic web search response")

            for event in stream:
                if event.type == "content_block_delta":
                    if hasattr(event.delta, "text"):
                        result_text += event.delta.text
                elif event.type == "message_start":
                    logger.debug("🚀 Streaming started")
                elif event.type == "message_stop":
                    logger.debug("✅ Streaming completed")

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


def main() -> None:
    """Main function for testing the Anthropic web search tool."""
    import logging
    import os
    import sys

    # Set up basic console logging for testing
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        stream=sys.stdout,
    )

    if len(sys.argv) < 2:
        print(
            "Usage: python -m shotgun.agents.tools.web_search.anthropic <search_query>"
        )
        print(
            "Example: python -m shotgun.agents.tools.web_search.anthropic 'latest Python updates'"
        )
        sys.exit(1)

    # Join all arguments as the search query
    query = " ".join(sys.argv[1:])

    print("🔍 Testing Anthropic Web Search with streaming")
    print(f"📝 Query: {query}")
    print("=" * 60)

    # Check if API key is available
    if not (
        os.getenv("ANTHROPIC_API_KEY")
        or (
            callable(get_provider_model)
            and get_provider_model(ProviderType.ANTHROPIC).api_key
        )
    ):
        print("❌ Error: ANTHROPIC_API_KEY environment variable not set")
        print("   Please set it with: export ANTHROPIC_API_KEY=your_key_here")
        sys.exit(1)

    try:
        result = anthropic_web_search_tool(query)
        print(f"✅ Search completed! Result length: {len(result)} characters")
        print("=" * 60)
        print("📄 RESULTS:")
        print("=" * 60)
        print(result)
    except KeyboardInterrupt:
        print("\n⏹️  Search interrupted by user")
    except Exception as e:
        print(f"❌ Error during search: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
