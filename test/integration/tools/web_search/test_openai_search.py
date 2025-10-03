"""Integration tests for OpenAI web search tool."""

import os

import pytest

from shotgun.agents.config.models import ProviderType
from shotgun.agents.tools.web_search import (
    is_provider_available,
    openai_web_search_tool,
)


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OpenAI API key not set")
async def test_openai_web_search_smoke():
    """Smoke test to ensure OpenAI web search doesn't crash."""
    # Check provider is available
    assert is_provider_available(ProviderType.OPENAI)

    # Perform a simple search
    try:
        result = await openai_web_search_tool("What is Python programming language?")

        # Basic assertions
        assert isinstance(result, str)
        assert len(result) > 0
        assert "Error" not in result or "API key" in result

        # Log result for debugging
        print(f"OpenAI search result length: {len(result)}")
        print(f"Result preview: {result[:200]}...")

    except Exception as e:
        # Allow test to pass if API error occurs (rate limits, etc.)
        if "API" in str(e) or "rate" in str(e).lower():
            pytest.skip(f"API error occurred: {e}")
        else:
            raise


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OpenAI API key not set")
async def test_openai_web_search_with_specific_query():
    """Test OpenAI web search with a specific query."""
    try:
        result = await openai_web_search_tool("Latest news about AI in 2025")

        assert isinstance(result, str)

        # Check for errors first
        if "Error" in result or "error" in result.lower():
            # If it's an API/connection error, skip the test
            pytest.skip(f"API/Connection error occurred: {result}")

        assert len(result) > 50  # Should return substantial content

    except Exception as e:
        # Allow test to pass if API error occurs
        if "API" in str(e) or "rate" in str(e).lower():
            pytest.skip(f"API error occurred: {e}")
        else:
            raise


@pytest.mark.asyncio
async def test_openai_web_search_without_api_key():
    """Test that OpenAI web search handles missing API key gracefully."""
    # Temporarily remove API key if it exists
    original_key = os.environ.pop("OPENAI_API_KEY", None)

    try:
        # Check availability - it might be available from config file or Shotgun key
        # which is okay, we're testing the env var scenario
        is_available = is_provider_available(ProviderType.OPENAI)

        if not is_available:
            # Tool should return an error message about missing API key
            result = await openai_web_search_tool("Test query")
            assert isinstance(result, str)
            assert "API key not configured" in result or "Error" in result
        else:
            # If available from config, the tool should work
            # We're just testing that removing env var doesn't break things
            result = await openai_web_search_tool("Test query")
            assert isinstance(result, str)
            # Should either work or return an error
            # (but not crash with an exception)

    finally:
        # Restore API key if it existed
        if original_key:
            os.environ["OPENAI_API_KEY"] = original_key
