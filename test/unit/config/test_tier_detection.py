"""Tests for Anthropic API tier detection."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from shotgun.agents.config.tier_detection import (
    AnthropicTier,
    RateLimitInfo,
    detect_anthropic_tier,
    detect_tier_from_limits,
    extract_rate_limits_from_headers,
)

# --- RateLimitInfo tests ---


def test_rate_limit_info_has_any_limits_true():
    """Test has_any_limits returns True when limits exist."""
    info = RateLimitInfo(requests_limit=50)
    assert info.has_any_limits is True


def test_rate_limit_info_has_any_limits_false():
    """Test has_any_limits returns False when no limits exist."""
    info = RateLimitInfo()
    assert info.has_any_limits is False


# --- extract_rate_limits_from_headers tests ---


def test_extract_rate_limits_all_headers():
    """Test extraction of all rate limit headers."""
    headers = {
        "anthropic-ratelimit-requests-limit": "50",
        "anthropic-ratelimit-input-tokens-limit": "50000",
        "anthropic-ratelimit-output-tokens-limit": "10000",
        "anthropic-ratelimit-requests-remaining": "49",
        "anthropic-ratelimit-input-tokens-remaining": "49900",
        "anthropic-ratelimit-output-tokens-remaining": "9900",
    }

    result = extract_rate_limits_from_headers(headers)

    assert result.requests_limit == 50
    assert result.input_tokens_limit == 50_000
    assert result.output_tokens_limit == 10_000
    assert result.requests_remaining == 49
    assert result.input_tokens_remaining == 49_900
    assert result.output_tokens_remaining == 9_900


def test_extract_rate_limits_missing_headers():
    """Test handling of missing headers."""
    headers = {"anthropic-ratelimit-requests-limit": "1000"}

    result = extract_rate_limits_from_headers(headers)

    assert result.requests_limit == 1000
    assert result.input_tokens_limit is None
    assert result.output_tokens_limit is None


def test_extract_rate_limits_invalid_values():
    """Test handling of invalid header values."""
    headers = {
        "anthropic-ratelimit-requests-limit": "not-a-number",
        "anthropic-ratelimit-input-tokens-limit": "",
    }

    result = extract_rate_limits_from_headers(headers)

    assert result.requests_limit is None
    assert result.input_tokens_limit is None


def test_extract_rate_limits_empty_headers():
    """Test handling of empty headers dict."""
    result = extract_rate_limits_from_headers({})

    assert result.requests_limit is None
    assert result.input_tokens_limit is None
    assert result.output_tokens_limit is None


# --- detect_tier_from_limits tests ---


def test_detect_tier1_from_rpm():
    """Test Tier 1 detection from RPM."""
    limits = RateLimitInfo(requests_limit=50)
    assert detect_tier_from_limits(limits) == AnthropicTier.TIER_1


def test_detect_tier2_from_rpm():
    """Test Tier 2 detection from RPM."""
    limits = RateLimitInfo(requests_limit=1000)
    assert detect_tier_from_limits(limits) == AnthropicTier.TIER_2


def test_detect_tier3_from_rpm():
    """Test Tier 3 detection from RPM."""
    limits = RateLimitInfo(requests_limit=2000)
    assert detect_tier_from_limits(limits) == AnthropicTier.TIER_3


def test_detect_tier4_from_rpm():
    """Test Tier 4 detection from RPM."""
    limits = RateLimitInfo(requests_limit=4000)
    assert detect_tier_from_limits(limits) == AnthropicTier.TIER_4


def test_detect_custom_tier_from_rpm():
    """Test custom tier (higher than 4) detection from RPM."""
    limits = RateLimitInfo(requests_limit=10000)
    assert detect_tier_from_limits(limits) == AnthropicTier.TIER_4


def test_detect_tier1_from_itpm():
    """Test Tier 1 detection from ITPM (fallback 1)."""
    limits = RateLimitInfo(input_tokens_limit=50_000)
    assert detect_tier_from_limits(limits, "claude-haiku-4-5") == AnthropicTier.TIER_1


def test_detect_tier2_from_itpm():
    """Test Tier 2 detection from ITPM (fallback 1)."""
    limits = RateLimitInfo(input_tokens_limit=450_000)
    assert detect_tier_from_limits(limits, "claude-haiku-4-5") == AnthropicTier.TIER_2


def test_detect_tier1_from_otpm():
    """Test Tier 1 detection from OTPM (fallback 2)."""
    limits = RateLimitInfo(output_tokens_limit=10_000)
    assert detect_tier_from_limits(limits, "claude-haiku-4-5") == AnthropicTier.TIER_1


def test_detect_tier2_from_otpm():
    """Test Tier 2 detection from OTPM (fallback 2)."""
    limits = RateLimitInfo(output_tokens_limit=90_000)
    assert detect_tier_from_limits(limits, "claude-haiku-4-5") == AnthropicTier.TIER_2


def test_detect_unknown_when_no_limits():
    """Test UNKNOWN tier when no limits provided."""
    limits = RateLimitInfo()
    assert detect_tier_from_limits(limits) == AnthropicTier.UNKNOWN


def test_detect_ignores_token_limits_for_non_haiku():
    """Test that token limits are ignored for non-Haiku models."""
    limits = RateLimitInfo(input_tokens_limit=50_000)
    assert detect_tier_from_limits(limits, "claude-opus-4") == AnthropicTier.UNKNOWN


# --- detect_anthropic_tier tests ---


@patch.dict(os.environ, {"SHOTGUN_ANTHROPIC_TIER1": "true"})
@pytest.mark.asyncio
async def test_detect_tier_test_mode_tier1():
    """Test test mode override returns Tier 1."""
    tier, limits = await detect_anthropic_tier("fake-api-key")

    assert tier == AnthropicTier.TIER_1
    assert limits.requests_limit == 50


@patch.dict(os.environ, {"SHOTGUN_ANTHROPIC_TIER1": "True"})
@pytest.mark.asyncio
async def test_detect_tier_test_mode_case_insensitive():
    """Test test mode is case insensitive."""
    tier, limits = await detect_anthropic_tier("fake-api-key")

    assert tier == AnthropicTier.TIER_1
    assert limits.requests_limit == 50


@pytest.mark.asyncio
async def test_detect_tier_successful():
    """Test successful tier detection from API."""
    mock_response = MagicMock()
    mock_response.headers = {
        "anthropic-ratelimit-requests-limit": "1000",
        "anthropic-ratelimit-input-tokens-limit": "450000",
        "anthropic-ratelimit-output-tokens-limit": "90000",
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("shotgun.agents.config.tier_detection.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        tier, limits = await detect_anthropic_tier("test-api-key")

    assert tier == AnthropicTier.TIER_2
    assert limits.requests_limit == 1000
    assert limits.input_tokens_limit == 450_000


@pytest.mark.asyncio
async def test_detect_tier_network_error():
    """Test network error raises exception."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Network error"))

    with patch("shotgun.agents.config.tier_detection.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        with pytest.raises(httpx.ConnectError):
            await detect_anthropic_tier("test-api-key")


@pytest.mark.asyncio
async def test_detect_tier_api_error():
    """Test API error raises exception."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=MagicMock()
        )
    )

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("shotgun.agents.config.tier_detection.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        with pytest.raises(httpx.HTTPStatusError):
            await detect_anthropic_tier("test-api-key")


@pytest.mark.asyncio
async def test_detect_tier_missing_headers_returns_unknown():
    """Test missing rate limit headers returns UNKNOWN tier."""
    mock_response = MagicMock()
    mock_response.headers = {}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("shotgun.agents.config.tier_detection.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        tier, limits = await detect_anthropic_tier("test-api-key")

    assert tier == AnthropicTier.UNKNOWN
    assert not limits.has_any_limits
