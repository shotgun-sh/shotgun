"""Tests for Anthropic API tier detection."""

import os
from unittest.mock import MagicMock, patch

import httpx
import pytest

from shotgun.agents.config.tier_detection import (
    AnthropicTier,
    RateLimitInfo,
    detect_anthropic_tier,
    detect_tier_from_limits,
    extract_rate_limits_from_headers,
)


class TestRateLimitInfo:
    """Tests for RateLimitInfo dataclass."""

    def test_has_any_limits_true(self):
        """Test has_any_limits returns True when limits exist."""
        info = RateLimitInfo(requests_limit=50)
        assert info.has_any_limits is True

    def test_has_any_limits_false(self):
        """Test has_any_limits returns False when no limits exist."""
        info = RateLimitInfo()
        assert info.has_any_limits is False


class TestExtractRateLimitsFromHeaders:
    """Tests for extract_rate_limits_from_headers."""

    def test_extracts_all_headers(self):
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

    def test_handles_missing_headers(self):
        """Test handling of missing headers."""
        headers = {"anthropic-ratelimit-requests-limit": "1000"}

        result = extract_rate_limits_from_headers(headers)

        assert result.requests_limit == 1000
        assert result.input_tokens_limit is None
        assert result.output_tokens_limit is None

    def test_handles_invalid_values(self):
        """Test handling of invalid header values."""
        headers = {
            "anthropic-ratelimit-requests-limit": "not-a-number",
            "anthropic-ratelimit-input-tokens-limit": "",
        }

        result = extract_rate_limits_from_headers(headers)

        assert result.requests_limit is None
        assert result.input_tokens_limit is None

    def test_handles_empty_headers(self):
        """Test handling of empty headers dict."""
        result = extract_rate_limits_from_headers({})

        assert result.requests_limit is None
        assert result.input_tokens_limit is None
        assert result.output_tokens_limit is None


class TestDetectTierFromLimits:
    """Tests for detect_tier_from_limits."""

    def test_tier1_from_rpm(self):
        """Test Tier 1 detection from RPM."""
        limits = RateLimitInfo(requests_limit=50)
        assert detect_tier_from_limits(limits) == AnthropicTier.TIER_1

    def test_tier2_from_rpm(self):
        """Test Tier 2 detection from RPM."""
        limits = RateLimitInfo(requests_limit=1000)
        assert detect_tier_from_limits(limits) == AnthropicTier.TIER_2

    def test_tier3_from_rpm(self):
        """Test Tier 3 detection from RPM."""
        limits = RateLimitInfo(requests_limit=2000)
        assert detect_tier_from_limits(limits) == AnthropicTier.TIER_3

    def test_tier4_from_rpm(self):
        """Test Tier 4 detection from RPM."""
        limits = RateLimitInfo(requests_limit=4000)
        assert detect_tier_from_limits(limits) == AnthropicTier.TIER_4

    def test_custom_tier_from_rpm(self):
        """Test custom tier (higher than 4) detection from RPM."""
        limits = RateLimitInfo(requests_limit=10000)
        assert detect_tier_from_limits(limits) == AnthropicTier.TIER_4

    def test_tier1_from_itpm(self):
        """Test Tier 1 detection from ITPM (fallback 1)."""
        limits = RateLimitInfo(input_tokens_limit=50_000)
        assert detect_tier_from_limits(limits, "claude-haiku-4-5") == AnthropicTier.TIER_1

    def test_tier2_from_itpm(self):
        """Test Tier 2 detection from ITPM (fallback 1)."""
        limits = RateLimitInfo(input_tokens_limit=450_000)
        assert detect_tier_from_limits(limits, "claude-haiku-4-5") == AnthropicTier.TIER_2

    def test_tier1_from_otpm(self):
        """Test Tier 1 detection from OTPM (fallback 2)."""
        limits = RateLimitInfo(output_tokens_limit=10_000)
        assert detect_tier_from_limits(limits, "claude-haiku-4-5") == AnthropicTier.TIER_1

    def test_tier2_from_otpm(self):
        """Test Tier 2 detection from OTPM (fallback 2)."""
        limits = RateLimitInfo(output_tokens_limit=90_000)
        assert detect_tier_from_limits(limits, "claude-haiku-4-5") == AnthropicTier.TIER_2

    def test_unknown_when_no_limits(self):
        """Test UNKNOWN tier when no limits provided."""
        limits = RateLimitInfo()
        assert detect_tier_from_limits(limits) == AnthropicTier.UNKNOWN

    def test_ignores_token_limits_for_non_haiku(self):
        """Test that token limits are ignored for non-Haiku models."""
        limits = RateLimitInfo(input_tokens_limit=50_000)
        assert detect_tier_from_limits(limits, "claude-opus-4") == AnthropicTier.UNKNOWN


class TestDetectAnthropicTier:
    """Tests for detect_anthropic_tier."""

    @patch.dict(os.environ, {"SHOTGUN_ANTHROPIC_TIER1": "true"})
    def test_test_mode_tier1(self):
        """Test test mode override returns Tier 1."""
        tier, limits = detect_anthropic_tier("fake-api-key")

        assert tier == AnthropicTier.TIER_1
        assert limits.requests_limit == 50

    @patch.dict(os.environ, {"SHOTGUN_ANTHROPIC_TIER1": "True"})
    def test_test_mode_case_insensitive(self):
        """Test test mode is case insensitive."""
        tier, limits = detect_anthropic_tier("fake-api-key")

        assert tier == AnthropicTier.TIER_1
        assert limits.requests_limit == 50

    @patch("httpx.Client")
    def test_successful_tier_detection(self, mock_client):
        """Test successful tier detection from API."""
        # Mock the API response
        mock_response = MagicMock()
        mock_response.headers = {
            "anthropic-ratelimit-requests-limit": "1000",
            "anthropic-ratelimit-input-tokens-limit": "450000",
            "anthropic-ratelimit-output-tokens-limit": "90000",
        }
        mock_response.raise_for_status = MagicMock()

        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_context)
        mock_context.__exit__ = MagicMock(return_value=None)
        mock_context.post = MagicMock(return_value=mock_response)
        mock_client.return_value = mock_context

        tier, limits = detect_anthropic_tier("test-api-key")

        assert tier == AnthropicTier.TIER_2
        assert limits.requests_limit == 1000
        assert limits.input_tokens_limit == 450_000

    @patch("httpx.Client")
    def test_network_error(self, mock_client):
        """Test network error raises exception."""
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_context)
        mock_context.__exit__ = MagicMock(return_value=None)
        mock_context.post = MagicMock(side_effect=httpx.ConnectError("Network error"))
        mock_client.return_value = mock_context

        with pytest.raises(httpx.ConnectError):
            detect_anthropic_tier("test-api-key")

    @patch("httpx.Client")
    def test_api_error(self, mock_client):
        """Test API error raises exception."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Unauthorized", request=MagicMock(), response=MagicMock()
            )
        )

        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_context)
        mock_context.__exit__ = MagicMock(return_value=None)
        mock_context.post = MagicMock(return_value=mock_response)
        mock_client.return_value = mock_context

        with pytest.raises(httpx.HTTPStatusError):
            detect_anthropic_tier("test-api-key")

    @patch("httpx.Client")
    def test_missing_headers_returns_unknown(self, mock_client):
        """Test missing rate limit headers returns UNKNOWN tier."""
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_response.raise_for_status = MagicMock()

        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_context)
        mock_context.__exit__ = MagicMock(return_value=None)
        mock_context.post = MagicMock(return_value=mock_response)
        mock_client.return_value = mock_context

        tier, limits = detect_anthropic_tier("test-api-key")

        assert tier == AnthropicTier.UNKNOWN
        assert not limits.has_any_limits
