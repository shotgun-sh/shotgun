"""Utility functions for web search tools."""

from logging import getLogger

from pydantic_ai import RunUsage
from pydantic_ai.usage import RequestUsage

from shotgun.agents.config import get_provider_model
from shotgun.agents.config.models import ProviderType
from shotgun.agents.usage_manager import get_session_usage_manager

logger = getLogger(__name__)


async def track_usage(
    usage: RequestUsage | RunUsage | None,
    *,
    model_name: str,
    provider: ProviderType,
) -> None:
    """Track token usage from a web search LLM call.

    Converts the response usage into a RunUsage and records it
    with the session usage manager. Silently handles errors so
    usage tracking never breaks a search.

    Args:
        usage: The usage from the LLM response (RequestUsage, RunUsage, or None).
        model_name: The model name string for attribution.
        provider: The provider type for attribution.
    """
    try:
        if usage:
            if isinstance(usage, RunUsage):
                run_usage = usage
            else:
                run_usage = RunUsage(
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    cache_write_tokens=usage.cache_write_tokens,
                    cache_read_tokens=usage.cache_read_tokens,
                )
            await get_session_usage_manager().add_usage(
                run_usage, model_name=model_name, provider=provider
            )
    except Exception:
        logger.debug("Failed to track web search usage", exc_info=True)


async def is_provider_available(provider: ProviderType) -> bool:
    """Check if a provider has API key configured.

    Args:
        provider: The provider to check

    Returns:
        True if the provider has valid credentials configured (from config or env)
    """
    try:
        await get_provider_model(provider)
        return True
    except ValueError:
        return False
