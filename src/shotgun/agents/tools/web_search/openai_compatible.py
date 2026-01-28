"""OpenAI-compatible endpoint web search tool implementation."""

import asyncio

from openai import AsyncOpenAI
from opentelemetry import trace

from shotgun.agents.tools.registry import ToolCategory, register_tool
from shotgun.logging_config import get_logger
from shotgun.prompts import PromptLoader
from shotgun.settings import settings
from shotgun.utils.datetime_utils import get_datetime_context

logger = get_logger(__name__)

# Global prompt loader instance
prompt_loader = PromptLoader()

# Timeout for web search API call (in seconds)
WEB_SEARCH_TIMEOUT = 120  # 2 minutes

# Default model for web search if not configured
DEFAULT_WEB_SEARCH_MODEL = "openai/gpt-5.2"


@register_tool(
    category=ToolCategory.WEB_RESEARCH,
    display_text="Searching web",
    key_arg="query",
)
async def openai_compatible_web_search_tool(query: str) -> str:
    """Perform a web search using an OpenAI-compatible endpoint.

    This tool uses OpenAI's Responses API with web_search capabilities
    via the configured OpenAI-compatible endpoint (e.g., LiteLLM proxy).

    Args:
        query: The search query

    Returns:
        Search results as a formatted string
    """
    logger.debug("Invoking OpenAI-compatible web_search_tool with query: %s", query)

    span = trace.get_current_span()
    span.set_attribute("input.value", f"**Query:** {query}\n")

    try:
        base_url = settings.openai_compat.base_url
        api_key = settings.openai_compat.api_key

        if not base_url or not api_key:
            error_msg = "OpenAI-compatible endpoint not configured"
            logger.error(error_msg)
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

        # Use configured web search model or default
        web_search_model = (
            settings.openai_compat.web_search_model or DEFAULT_WEB_SEARCH_MODEL
        )

        logger.debug(
            "Using OpenAI-compatible endpoint for web search: %s with model %s",
            base_url,
            web_search_model,
        )

        client = AsyncOpenAI(api_key=api_key, base_url=base_url)

        # Wrap API call with timeout to prevent indefinite hangs
        try:
            response = await asyncio.wait_for(
                client.responses.create(
                    model=web_search_model,
                    input=[
                        {
                            "role": "user",
                            "content": [{"type": "input_text", "text": prompt}],
                        }
                    ],
                    text={
                        "format": {"type": "text"},
                        "verbosity": "high",
                    },
                    reasoning={"effort": "medium", "summary": "auto"},
                    tools=[
                        {
                            "type": "web_search",
                            "user_location": {"type": "approximate"},
                            "search_context_size": "high",
                        }
                    ],
                    store=False,
                    include=[
                        "reasoning.encrypted_content",
                        "web_search_call.action.sources",  # pyright: ignore[reportArgumentType]
                    ],
                ),
                timeout=WEB_SEARCH_TIMEOUT,
            )
        except asyncio.TimeoutError:
            error_msg = f"Web search timed out after {WEB_SEARCH_TIMEOUT} seconds"
            logger.warning(error_msg)
            span.set_attribute("output.value", f"**Error:**\n {error_msg}\n")
            return error_msg

        result_text = response.output_text or "No content returned"

        logger.debug("Web search result: %d characters", len(result_text))
        logger.debug(
            "Result preview: %s...",
            result_text[:100] if result_text else "No result",
        )

        span.set_attribute("output.value", f"**Results:**\n {result_text}\n")

        return result_text
    except Exception as e:
        error_msg = f"Error performing web search: {str(e)}"
        logger.error("Web search failed: %s", str(e))
        logger.debug("Full error details: %s", error_msg)
        span.set_attribute("output.value", f"**Error:**\n {error_msg}\n")
        return error_msg
