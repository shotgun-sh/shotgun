"""Anthropic token counting using official client."""

from pydantic_ai.messages import ModelMessage

from shotgun.agents.config.models import KeyProvider
from shotgun.llm_proxy import create_anthropic_proxy_provider
from shotgun.logging_config import get_logger

from .base import TokenCounter, extract_text_from_messages

logger = get_logger(__name__)


class AnthropicTokenCounter(TokenCounter):
    """Token counter for Anthropic models using official client."""

    def __init__(
        self,
        model_name: str,
        api_key: str,
        key_provider: KeyProvider = KeyProvider.BYOK,
    ):
        """Initialize Anthropic token counter.

        Args:
            model_name: Anthropic model name for token counting
            api_key: API key (Anthropic for BYOK, Shotgun for proxy)
            key_provider: Key provider type (BYOK or SHOTGUN)

        Raises:
            RuntimeError: If client initialization fails
        """
        self.model_name = model_name
        import anthropic

        try:
            if key_provider == KeyProvider.SHOTGUN:
                # Use LiteLLM proxy for Shotgun Account
                # Get async client from AnthropicProvider
                provider = create_anthropic_proxy_provider(api_key)
                self.client = provider.client
                logger.debug(
                    f"Initialized async Anthropic token counter for {model_name} via LiteLLM proxy"
                )
            else:
                # Direct Anthropic API for BYOK - use async client
                self.client = anthropic.AsyncAnthropic(api_key=api_key)
                logger.debug(
                    f"Initialized async Anthropic token counter for {model_name} via direct API"
                )
        except Exception as e:
            raise RuntimeError("Failed to initialize Anthropic async client") from e

    async def count_tokens(self, text: str) -> int:
        """Count tokens using Anthropic's official API (async).

        Args:
            text: Text to count tokens for

        Returns:
            Exact token count from Anthropic API

        Raises:
            RuntimeError: If API call fails
        """
        try:
            # Anthropic API expects messages format and model parameter
            # Use await with async client
            result = await self.client.messages.count_tokens(
                messages=[{"role": "user", "content": text}], model=self.model_name
            )
            return result.input_tokens
        except Exception as e:
            raise RuntimeError(
                f"Anthropic token counting API failed for {self.model_name}"
            ) from e

    async def count_message_tokens(self, messages: list[ModelMessage]) -> int:
        """Count tokens across all messages using Anthropic API (async).

        Args:
            messages: List of PydanticAI messages

        Returns:
            Total token count for all messages

        Raises:
            RuntimeError: If token counting fails
        """
        total_text = extract_text_from_messages(messages)
        return await self.count_tokens(total_text)
