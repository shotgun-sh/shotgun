"""OpenAI web search tool implementation."""

from openai import AsyncOpenAI
from opentelemetry import trace

from shotgun.agents.config import get_provider_model
from shotgun.agents.config.models import ProviderType
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
async def openai_web_search_tool(query: str) -> str:
    """Perform a web search and return results.

    This tool uses OpenAI's web search capabilities to find current information
    about the given query.

    Args:
        query: The search query

    Returns:
        Search results as a formatted string
    """
    logger.debug("🔧 Invoking OpenAI web_search_tool with query: %s", query)

    span = trace.get_current_span()
    span.set_attribute("input.value", f"**Query:** {query}\n")

    try:
        logger.debug("📡 Executing OpenAI web search with prompt: %s", query)

        # Get API key from centralized configuration
        try:
            model_config = await get_provider_model(ProviderType.OPENAI)
            api_key = model_config.api_key
        except ValueError as e:
            error_msg = f"OpenAI API key not configured: {str(e)}"
            logger.error("❌ %s", error_msg)
            span.set_attribute("output.value", f"**Error:**\n {error_msg}\n")
            return error_msg

        # Get datetime context for the search prompt
        dt_context = get_datetime_context()

        # Render search prompt from template
        prompt = prompt_loader.render(
            "tools/web_search.j2",
            query=query,
            current_datetime=dt_context.datetime_formatted,
            timezone_name=dt_context.timezone_name,
            utc_offset=dt_context.utc_offset,
        )

        client = AsyncOpenAI(api_key=api_key)
        response = await client.responses.create(  # type: ignore[call-overload]
            model="gpt-5-mini",
            input=[
                {"role": "user", "content": [{"type": "input_text", "text": prompt}]}
            ],
            text={
                "format": {"type": "text"},
                "verbosity": "high",
            },  # Increased from medium
            reasoning={"effort": "medium", "summary": "auto"},
            tools=[
                {
                    "type": "web_search",
                    "user_location": {"type": "approximate"},
                    "search_context_size": "high",  # Increased from low for more context
                }
            ],
            store=False,
            include=[
                "reasoning.encrypted_content",
                "web_search_call.action.sources",  # pyright: ignore[reportArgumentType]
            ],
        )

        result_text = response.output_text or "No content returned"

        logger.debug("📄 Web search result: %d characters", len(result_text))
        logger.debug(
            "🔍 Result preview: %s...",
            result_text[:100] if result_text else "No result",
        )

        span.set_attribute("output.value", f"**Results:**\n {result_text}\n")

        return result_text
    except Exception as e:
        error_msg = f"Error performing web search: {str(e)}"
        logger.error("❌ Web search failed: %s", str(e))
        logger.debug("💥 Full error details: %s", error_msg)
        span.set_attribute("output.value", f"**Error:**\n {error_msg}\n")
        return error_msg
