"""Integration tests for Gemini web search tool."""

import os

import pytest

from shotgun.agents.config.models import ProviderType
from shotgun.agents.tools.web_search import (
    gemini_web_search_tool,
    is_provider_available,
)


@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="Gemini API key not set",
)
def test_gemini_web_search_smoke():
    """Smoke test to ensure Gemini web search doesn't crash."""
    # Check provider is available
    assert is_provider_available(ProviderType.GOOGLE)

    # Perform a simple search
    try:
        result = gemini_web_search_tool("What is Python programming language?")

        # Basic assertions
        assert isinstance(result, str)
        assert len(result) > 0

        # Check for common error messages
        if "not installed" in result:
            pytest.skip("google-generativeai package not installed")
        elif "Error" in result and "API" in result:
            pytest.skip(f"API error occurred: {result}")

        # Log result for debugging
        print(f"Gemini search result length: {len(result)}")
        print(f"Result preview: {result[:200]}...")

    except ImportError:
        pytest.skip("google-generativeai package not installed")
    except Exception as e:
        # Allow test to pass if API error occurs (rate limits, etc.)
        if "API" in str(e) or "rate" in str(e).lower() or "quota" in str(e).lower():
            pytest.skip(f"API error occurred: {e}")
        else:
            raise


@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="Gemini API key not set",
)
def test_gemini_web_search_with_specific_query():
    """Test Gemini web search with a specific query."""
    try:
        result = gemini_web_search_tool("Latest Google AI announcements")

        assert isinstance(result, str)

        # Check for package not installed error
        if "not installed" in result:
            pytest.skip("google-generativeai package not installed")

        assert len(result) > 50  # Should return substantial content

    except ImportError:
        pytest.skip("google-generativeai package not installed")
    except Exception as e:
        # Allow test to pass if API error occurs
        if "API" in str(e) or "rate" in str(e).lower() or "quota" in str(e).lower():
            pytest.skip(f"API error occurred: {e}")
        else:
            raise


def test_gemini_web_search_without_api_key():
    """Test that Gemini web search handles missing API key gracefully."""
    # Temporarily remove API key if it exists
    original_gemini_key = os.environ.pop("GEMINI_API_KEY", None)

    try:
        # Check availability - it might be available from config file
        # which is okay, we're testing the env var scenario
        is_available = is_provider_available(ProviderType.GOOGLE)

        if not is_available:
            # Tool should return an error message about missing API key
            result = gemini_web_search_tool("Test query")
            assert isinstance(result, str)
            assert "API key not configured" in result or "not installed" in result
        else:
            # If available from config, the tool should work
            # We're just testing that removing env var doesn't break things
            result = gemini_web_search_tool("Test query")
            assert isinstance(result, str)
            # Should either work or return a package not installed error
            # (but not an API key error since it's configured)

    finally:
        # Restore API key if it existed
        if original_gemini_key:
            os.environ["GEMINI_API_KEY"] = original_gemini_key
