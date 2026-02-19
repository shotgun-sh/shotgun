"""OpenRouter web search tool implementation."""

from opentelemetry import trace
from pydantic_ai.messages import ModelMessage, ModelRequest, TextPart
from pydantic_ai.settings import ModelSettings

from shotgun.agents.config.constants import MEDIUM_TEXT_8K_TOKENS
from shotgun.agents.config.manager import get_config_manager
from shotgun.agents.config.models import (
    OPENROUTER_BASE_URL,
    KeyProvider,
    ModelConfig,
    ProviderType,
)
from shotgun.agents.llm import shotgun_model_request
from shotgun.agents.tools.registry import ToolCategory, register_tool
from shotgun.agents.tools.web_search.utils import track_usage
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
async def openrouter_web_search_tool(query: str) -> str:
    """Perform a web search using OpenRouter's :online model variant.

    Uses Google Gemini Flash via OpenRouter with the :online suffix
    which enables web search grounding for the query.

    Args:
        query: The search query

    Returns:
        Search results as a formatted string
    """
    logger.debug("Invoking OpenRouter web_search_tool with query: %s", query)

    span = trace.get_current_span()
    span.set_attribute("input.value", f"**Query:** {query}\n")

    # Get OpenRouter API key from config
    config_manager = get_config_manager()
    config = await config_manager.load(force_reload=False)

    if not config.openrouter.api_key:
        error_msg = "OpenRouter API key not configured"
        logger.error(error_msg)
        span.set_attribute("output.value", f"**Error:**\n {error_msg}\n")
        return error_msg

    openrouter_api_key = config.openrouter.api_key.get_secret_value()

    # Create ModelConfig for OpenRouter with :online variant
    model_config = ModelConfig(
        name="google/gemini-3-flash-preview:online",
        provider=ProviderType.GOOGLE,
        key_provider=KeyProvider.OPENROUTER,
        max_input_tokens=1_048_576,
        max_output_tokens=65_536,
        api_key=openrouter_api_key,
        base_url=OPENROUTER_BASE_URL,
        supports_streaming=True,
    )

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

    # Generate response using OpenRouter with :online model
    try:
        response = await shotgun_model_request(
            model_config=model_config,
            messages=messages,
            model_settings=ModelSettings(
                temperature=0.3,
                max_tokens=MEDIUM_TEXT_8K_TOKENS,
            ),
        )

        # Track usage from the web search LLM call
        await track_usage(
            response.usage,
            model_name=str(model_config.name),
            provider=model_config.provider,
        )

        # Extract text from response
        result_text = "No content returned from search"
        if response.parts:
            for part in response.parts:
                if isinstance(part, TextPart):
                    result_text = part.content
                    break

        logger.debug("OpenRouter web search result: %d characters", len(result_text))

        span.set_attribute("output.value", f"**Results:**\n {result_text}\n")

        return result_text
    except Exception as e:
        error_msg = f"Error performing OpenRouter web search: {str(e)}"
        logger.error("OpenRouter web search failed: %s", str(e))
        span.set_attribute("output.value", f"**Error:**\n {error_msg}\n")
        return error_msg
