"""Gemini web search tool implementation."""

from opentelemetry import trace

from shotgun.agents.config import get_provider_model
from shotgun.agents.config.models import ProviderType
from shotgun.logging_config import get_logger

logger = get_logger(__name__)


def gemini_web_search_tool(query: str) -> str:
    """Perform a web search using Google's Gemini API with grounding.

    This tool uses Gemini's Google Search grounding to find current information
    about the given query.

    Args:
        query: The search query

    Returns:
        Search results as a formatted string
    """
    logger.debug("🔧 Invoking Gemini web_search_tool with query: %s", query)

    span = trace.get_current_span()
    span.set_attribute("input.value", f"**Query:** {query}\n")

    try:
        import google.generativeai as genai  # type: ignore[import-untyped]

        logger.debug("📡 Executing Gemini web search with prompt: %s", query)

        # Get API key from centralized configuration
        try:
            model_config = get_provider_model(ProviderType.GOOGLE)
            api_key = model_config.api_key
        except ValueError as e:
            error_msg = f"Gemini API key not configured: {str(e)}"
            logger.error("❌ %s", error_msg)
            span.set_attribute("output.value", f"**Error:**\n {error_msg}\n")
            return error_msg

        genai.configure(api_key=api_key)

        # Create model with grounding
        model = genai.GenerativeModel(
            "gemini-2.0-flash-exp",
            tools=["google_search"],
        )

        # Generate response with grounding
        response = model.generate_content(
            query,
            generation_config=genai.GenerationConfig(temperature=0.3),
        )

        result_text = response.text or "No content returned from search"

        logger.debug("📄 Gemini web search result: %d characters", len(result_text))
        logger.debug(
            "🔍 Result preview: %s...",
            result_text[:100] if result_text else "No result",
        )

        span.set_attribute("output.value", f"**Results:**\n {result_text}\n")

        return result_text
    except ImportError:
        error_msg = (
            "google-generativeai package not installed. "
            "Install with: pip install google-generativeai"
        )
        logger.error("❌ %s", error_msg)
        span.set_attribute("output.value", f"**Error:**\n {error_msg}\n")
        return error_msg
    except Exception as e:
        error_msg = f"Error performing Gemini web search: {str(e)}"
        logger.error("❌ Gemini web search failed: %s", str(e))
        logger.debug("💥 Full error details: %s", error_msg)
        span.set_attribute("output.value", f"**Error:**\n {error_msg}\n")
        return error_msg
