"""Anthropic web search tool implementation."""

from opentelemetry import trace
from pydantic_ai.messages import ModelMessage, ModelRequest, TextPart
from pydantic_ai.settings import ModelSettings

from shotgun.agents.config import get_provider_model
from shotgun.agents.config.constants import MEDIUM_TEXT_8K_TOKENS
from shotgun.agents.config.models import ProviderType
from shotgun.agents.llm import shotgun_model_request
from shotgun.agents.tools.registry import ToolCategory, register_tool
from shotgun.logging_config import get_logger
from shotgun.prompts import PromptLoader
from shotgun.utils.datetime_utils import get_datetime_context

logger = get_logger(__name__)

# Global prompt loader instance
prompt_loader = PromptLoader()


@register_tool(
    category=ToolCategory.WEB_RESEARCH,
    display_text="Searching web",
    key_arg="query",
)
async def anthropic_web_search_tool(query: str) -> str:
    """Perform a web search using Anthropic's Claude API.

    This tool uses Anthropic's web search capabilities to find current information
    about the given query. Works with both Shotgun API keys (via LiteLLM proxy)
    and direct Anthropic API keys (BYOK).

    Args:
        query: The search query

    Returns:
        Search results as a formatted string
    """
    logger.debug("🔧 Invoking Anthropic web_search_tool with query: %s", query)

    span = trace.get_current_span()
    span.set_attribute("input.value", f"**Query:** {query}\n")

    logger.debug("📡 Executing Anthropic web search with prompt: %s", query)

    # Get model configuration (supports both Shotgun and BYOK)
    try:
        model_config = await get_provider_model(ProviderType.ANTHROPIC)
    except ValueError as e:
        error_msg = f"Anthropic API key not configured: {str(e)}"
        logger.error("❌ %s", error_msg)
        span.set_attribute("output.value", f"**Error:**\n {error_msg}\n")
        return error_msg

    # Get datetime context for the search prompt
    dt_context = get_datetime_context()

    # Render search prompt from template
    search_prompt = prompt_loader.render(
        "tools/web_search.j2",
        query=query,
        current_datetime=dt_context.datetime_formatted,
        timezone_name=dt_context.timezone_name,
        utc_offset=dt_context.utc_offset,
    )

    # Build the request messages
    messages: list[ModelMessage] = [ModelRequest.user_text_prompt(search_prompt)]

    # Use the Messages API with web search tool
    try:
        response = await shotgun_model_request(
            model_config=model_config,
            messages=messages,
            model_settings=ModelSettings(
                max_tokens=MEDIUM_TEXT_8K_TOKENS,
                # Enable Anthropic web search tool
                extra_body={
                    "tools": [
                        {
                            "type": "web_search_20250305",
                            "name": "web_search",
                        }
                    ],
                    "tool_choice": {"type": "tool", "name": "web_search"},
                },
            ),
        )

        # Extract text from response
        result_text = "No content returned from search"
        if response.parts:
            for part in response.parts:
                if isinstance(part, TextPart):
                    result_text = part.content
                    break

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


async def main() -> None:
    """Main function for testing the Anthropic web search tool."""
    import sys

    from shotgun.logging_config import setup_logger

    # Use project's logging configuration instead of basicConfig
    setup_logger(__name__)

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

    print("🔍 Testing Anthropic Web Search")
    print(f"📝 Query: {query}")
    print("=" * 60)

    # Check if API key is available
    try:
        if callable(get_provider_model):
            model_config = await get_provider_model(ProviderType.ANTHROPIC)
            if not model_config.api_key:
                raise ValueError("No API key configured")
    except (ValueError, Exception):
        print("❌ Error: Anthropic API key not configured")
        print("   Please set it in your config file")
        sys.exit(1)

    try:
        result = await anthropic_web_search_tool(query)
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
    import asyncio

    asyncio.run(main())
