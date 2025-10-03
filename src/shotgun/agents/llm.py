"""LLM request utilities for Shotgun agents."""

from typing import Any

from pydantic_ai.direct import model_request
from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.settings import ModelSettings

from shotgun.agents.config.models import ModelConfig
from shotgun.logging_config import get_logger

logger = get_logger(__name__)


async def shotgun_model_request(
    model_config: ModelConfig,
    messages: list[ModelMessage],
    model_settings: ModelSettings | None = None,
    **kwargs: Any,
) -> ModelResponse:
    """Model request wrapper that uses full token capacity by default.

    This wrapper ensures all LLM calls in Shotgun use the maximum available
    token capacity of each model, improving response quality and completeness.
    The most common issue this fixes is truncated summaries that were cut off
    at default token limits (e.g., 4096 for Claude models).

    Args:
        model_config: ModelConfig instance with model settings and API key
        messages: Messages to send to the model
        model_settings: Optional ModelSettings. If None, creates default with max tokens
        **kwargs: Additional arguments passed to model_request

    Returns:
        ModelResponse from the model

    Example:
        # Uses full token capacity (e.g., 4096 for Claude, 128k for GPT-5)
        response = await shotgun_model_request(model_config, messages)

        # With custom settings
        response = await shotgun_model_request(model_config, messages, model_settings=ModelSettings(max_tokens=1000, temperature=0.7))
    """
    if kwargs.get("max_tokens") is not None:
        logger.warning(
            "⚠️ 'max_tokens' argument is ignored in shotgun_model_request. "
            "Set 'model_settings.max_tokens' instead."
        )

    if not model_settings:
        model_settings = ModelSettings()

    if model_settings.get("max_tokens") is None:
        model_settings["max_tokens"] = model_config.max_output_tokens

    # Make the model request with full token utilization
    return await model_request(
        model=model_config.model_instance,
        messages=messages,
        model_settings=model_settings,
        **kwargs,
    )
