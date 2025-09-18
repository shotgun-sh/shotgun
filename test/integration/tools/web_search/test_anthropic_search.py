"""Integration tests for Anthropic web search tool."""

import os

import pytest

from shotgun.agents.config.models import ProviderType
from shotgun.agents.tools.web_search import (
    anthropic_web_search_tool,
    is_provider_available,
)


@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"), reason="Anthropic API key not set"
)
def test_anthropic_web_search_smoke():
    """Smoke test to ensure Anthropic web search doesn't crash."""
    # Check provider is available
    assert is_provider_available(ProviderType.ANTHROPIC)

    # Perform a simple search
    try:
        result = anthropic_web_search_tool("What is Python programming language?")

        # Basic assertions
        assert isinstance(result, str)
        assert len(result) > 0

        # Check for common error messages
        if "not installed" in result:
            pytest.skip("anthropic package not installed")
        elif "Error" in result and "API" in result:
            pytest.skip(f"API error occurred: {result}")

        # Log result for debugging
        print(f"Anthropic search result length: {len(result)}")
        print(f"Result preview: {result[:200]}...")

    except ImportError:
        pytest.skip("anthropic package not installed")
    except Exception as e:
        # Allow test to pass if API error occurs (rate limits, etc.)
        if "API" in str(e) or "rate" in str(e).lower():
            pytest.skip(f"API error occurred: {e}")
        else:
            raise


@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"), reason="Anthropic API key not set"
)
def test_anthropic_web_search_with_specific_query():
    """Test Anthropic web search with a specific query."""
    try:
        result = anthropic_web_search_tool("Latest developments in machine learning")

        assert isinstance(result, str)

        # Check for package not installed error
        if "not installed" in result:
            pytest.skip("anthropic package not installed")

        assert len(result) > 50  # Should return substantial content

    except ImportError:
        pytest.skip("anthropic package not installed")
    except Exception as e:
        # Allow test to pass if API error occurs
        if "API" in str(e) or "rate" in str(e).lower():
            pytest.skip(f"API error occurred: {e}")
        else:
            raise


def test_anthropic_web_search_without_api_key():
    """Test that Anthropic web search handles missing API key gracefully."""
    # Temporarily remove API key if it exists
    original_key = os.environ.pop("ANTHROPIC_API_KEY", None)

    try:
        # Should not be available without API key
        assert not is_provider_available(ProviderType.ANTHROPIC)

        # Tool should return an error message about missing API key
        result = anthropic_web_search_tool("Test query")
        assert isinstance(result, str)
        assert "API key not configured" in result or "not installed" in result

    finally:
        # Restore API key if it existed
        if original_key:
            os.environ["ANTHROPIC_API_KEY"] = original_key
