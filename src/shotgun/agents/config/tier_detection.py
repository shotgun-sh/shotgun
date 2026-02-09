"""Anthropic API tier detection using minimal Haiku request.

This module detects the API tier by making a minimal API request
and extracting tier information from response headers.
"""

import os
from dataclasses import dataclass
from enum import IntEnum

import httpx

from shotgun.logging_config import get_logger

logger = get_logger(__name__)


class AnthropicTier(IntEnum):
    """Anthropic API usage tiers."""

    TIER_1 = 1
    TIER_2 = 2
    TIER_3 = 3
    TIER_4 = 4
    UNKNOWN = -1


@dataclass
class RateLimitInfo:
    """Rate limit information extracted from API response headers."""

    requests_limit: int | None = None
    input_tokens_limit: int | None = None
    output_tokens_limit: int | None = None
    requests_remaining: int | None = None
    input_tokens_remaining: int | None = None
    output_tokens_remaining: int | None = None

    @property
    def has_any_limits(self) -> bool:
        """Check if we got any rate limit information."""
        return any(
            [
                self.requests_limit is not None,
                self.input_tokens_limit is not None,
                self.output_tokens_limit is not None,
            ]
        )


def extract_rate_limits_from_headers(headers: dict[str, str]) -> RateLimitInfo:
    """Safely extract rate limit information from response headers.

    Args:
        headers: Response headers from Anthropic API

    Returns:
        RateLimitInfo with extracted values (None for missing headers)
    """

    def safe_int(value: str | None) -> int | None:
        """Safely convert string to int, returning None on failure."""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    return RateLimitInfo(
        requests_limit=safe_int(headers.get("anthropic-ratelimit-requests-limit")),
        input_tokens_limit=safe_int(
            headers.get("anthropic-ratelimit-input-tokens-limit")
        ),
        output_tokens_limit=safe_int(
            headers.get("anthropic-ratelimit-output-tokens-limit")
        ),
        requests_remaining=safe_int(
            headers.get("anthropic-ratelimit-requests-remaining")
        ),
        input_tokens_remaining=safe_int(
            headers.get("anthropic-ratelimit-input-tokens-remaining")
        ),
        output_tokens_remaining=safe_int(
            headers.get("anthropic-ratelimit-output-tokens-remaining")
        ),
    )


def detect_tier_from_limits(
    rate_limits: RateLimitInfo, model_name: str = "claude-haiku-4-5"
) -> AnthropicTier:
    """Detect API tier from rate limit values.

    Uses multiple fallback strategies to determine tier even if some headers are missing.

    Args:
        rate_limits: Extracted rate limit information
        model_name: Model used for the request (different models have different limits)

    Returns:
        Detected tier or UNKNOWN if cannot be determined
    """
    # Tier detection based on requests per minute (RPM) - most reliable
    if rate_limits.requests_limit is not None:
        rpm = rate_limits.requests_limit
        if rpm <= 50:
            return AnthropicTier.TIER_1
        elif rpm <= 1000:
            return AnthropicTier.TIER_2
        elif rpm <= 2000:
            return AnthropicTier.TIER_3
        elif rpm <= 4000:
            return AnthropicTier.TIER_4
        else:
            # Custom tier (higher than 4)
            return AnthropicTier.TIER_4

    # Fallback 1: Use input tokens limit for Haiku 4.5
    if rate_limits.input_tokens_limit is not None and "haiku" in model_name.lower():
        itpm = rate_limits.input_tokens_limit
        if itpm <= 50_000:
            return AnthropicTier.TIER_1
        elif itpm <= 450_000:
            return AnthropicTier.TIER_2
        elif itpm <= 1_000_000:
            return AnthropicTier.TIER_3
        elif itpm <= 4_000_000:
            return AnthropicTier.TIER_4
        else:
            return AnthropicTier.TIER_4

    # Fallback 2: Use output tokens limit for Haiku 4.5
    if rate_limits.output_tokens_limit is not None and "haiku" in model_name.lower():
        otpm = rate_limits.output_tokens_limit
        if otpm <= 10_000:
            return AnthropicTier.TIER_1
        elif otpm <= 90_000:
            return AnthropicTier.TIER_2
        elif otpm <= 200_000:
            return AnthropicTier.TIER_3
        elif otpm <= 800_000:
            return AnthropicTier.TIER_4
        else:
            return AnthropicTier.TIER_4

    # Could not determine tier
    return AnthropicTier.UNKNOWN


def detect_anthropic_tier(api_key: str) -> tuple[AnthropicTier, RateLimitInfo]:
    """Detect Anthropic API tier by making a minimal request.

    Makes the cheapest possible API request (Haiku with 1 output token)
    and extracts tier information from response headers.

    Test mode: Set SHOTGUN_ANTHROPIC_TIER1=true to simulate Tier 1 without API call.

    Args:
        api_key: Anthropic API key

    Returns:
        Tuple of (detected tier, rate limit info)

    Raises:
        Exception: If API request fails
    """
    # Test mode override
    if os.environ.get("SHOTGUN_ANTHROPIC_TIER1", "").lower() == "true":
        logger.info("SHOTGUN_ANTHROPIC_TIER1=true detected, simulating Tier 1")
        return AnthropicTier.TIER_1, RateLimitInfo(requests_limit=50)

    # Use httpx directly to access response headers
    # The Anthropic SDK doesn't expose headers easily
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
        "X-Api-Key": api_key,
    }
    payload = {
        "model": "claude-haiku-4-5",
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "Hi"}],
    }

    # Make the request
    with httpx.Client() as client:
        response = client.post(url, headers=headers, json=payload, timeout=30.0)
        response.raise_for_status()

    # Extract rate limits from response headers
    rate_limits = extract_rate_limits_from_headers(dict(response.headers))

    # Detect tier
    tier = detect_tier_from_limits(rate_limits, model_name="claude-haiku-4-5")

    return tier, rate_limits
