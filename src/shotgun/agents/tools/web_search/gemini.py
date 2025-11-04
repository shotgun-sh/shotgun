"""Gemini web search tool implementation."""

from opentelemetry import trace
from pydantic_ai.messages import ModelMessage, ModelRequest
from pydantic_ai.settings import ModelSettings

from shotgun.agents.config import get_provider_model
from shotgun.agents.config.constants import MEDIUM_TEXT_8K_TOKENS
from shotgun.agents.config.models import ModelName
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
async def gemini_web_search_tool(query: str) -> str:
    """Perform a web search using Google's Gemini API with grounding.

    This tool uses Gemini's Google Search grounding to find current information
    about the given query. Works with both Shotgun API keys (via LiteLLM proxy)
    and direct Gemini API keys (BYOK).

    Args:
        query: The search query

    Returns:
        Search results as a formatted string
    """
    logger.debug("🔧 Invoking Gemini web_search_tool with query: %s", query)

    span = trace.get_current_span()
    span.set_attribute("input.value", f"**Query:** {query}\n")

    logger.debug("📡 Executing Gemini web search with prompt: %s", query)

    # Get model configuration (supports both Shotgun and BYOK)
    try:
        model_config = await get_provider_model(ModelName.GEMINI_2_5_FLASH)
    except ValueError as e:
        error_msg = f"Gemini API key not configured: {str(e)}"
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

    # Generate response using Pydantic AI with Google Search grounding
    try:
        response = await shotgun_model_request(
            model_config=model_config,
            messages=messages,
            model_settings=ModelSettings(
                temperature=0.3,
                max_tokens=MEDIUM_TEXT_8K_TOKENS,
                # Enable Google Search grounding for Gemini
                extra_body={"tools": [{"googleSearch": {}}]},
            ),
        )

        # Extract text from response
        from pydantic_ai.messages import TextPart

        result_text = "No content returned from search"
        if response.parts:
            for part in response.parts:
                if isinstance(part, TextPart):
                    result_text = part.content
                    break

        logger.debug("📄 Gemini web search result: %d characters", len(result_text))
        logger.debug(
            "🔍 Result preview: %s...",
            result_text[:100] if result_text else "No result",
        )

        span.set_attribute("output.value", f"**Results:**\n {result_text}\n")

        return result_text
    except Exception as e:
        error_msg = f"Error performing Gemini web search: {str(e)}"
        logger.error("❌ Gemini web search failed: %s", str(e))
        logger.debug("💥 Full error details: %s", error_msg)
        span.set_attribute("output.value", f"**Error:**\n {error_msg}\n")
        return error_msg
