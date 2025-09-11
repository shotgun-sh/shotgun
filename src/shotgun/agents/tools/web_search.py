"""Web search tool for Pydantic AI agents."""

from openai import OpenAI
from opentelemetry import trace

from shotgun.logging_config import setup_logger

logger = setup_logger(__name__)


def web_search_tool(query: str) -> str:
    """Perform a web search and return results.

    This tool uses OpenAI's web search capabilities to find current information
    about the given query.

    Args:
        query: The search query

    Returns:
        Search results as a formatted string
    """
    logger.debug("🔧 Invoking web_search_tool with query: %s", query)

    span = trace.get_current_span()
    span.set_attribute("input.value", f"**Query:** {query}\n")

    try:
        logger.debug("📡 Executing web search with prompt: %s", query)

        client = OpenAI()
        response = client.responses.create(  # type: ignore[call-overload]
            model="gpt-5-mini",
            input=[
                {"role": "user", "content": [{"type": "input_text", "text": query}]}
            ],
            text={"format": {"type": "text"}, "verbosity": "medium"},
            reasoning={"effort": "medium", "summary": "auto"},
            tools=[
                {
                    "type": "web_search",
                    "user_location": {"type": "approximate"},
                    "search_context_size": "low",
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
