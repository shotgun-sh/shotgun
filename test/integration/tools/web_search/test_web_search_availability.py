"""Integration tests for web search tool availability."""

import os

import pytest

from shotgun.agents.config.models import ProviderType
from shotgun.agents.tools.web_search import (
    get_available_web_search_tools,
    is_provider_available,
)


@pytest.mark.asyncio
async def test_get_available_web_search_tools_returns_list():
    """Test that get_available_web_search_tools returns a list with at most one tool."""
    tools = await get_available_web_search_tools()

    assert isinstance(tools, list)
    assert len(tools) <= 1

    for tool in tools:
        assert callable(tool)
        assert hasattr(tool, "__name__")
        assert "web_search_tool" in tool.__name__


@pytest.mark.asyncio
async def test_prefers_gemini_when_google_key_available():
    """Test that Gemini is preferred when a Google API key is available."""
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")

    tools = await get_available_web_search_tools()
    assert len(tools) == 1
    assert "gemini" in tools[0].__name__


@pytest.mark.asyncio
async def test_no_tools_available_when_no_api_keys():
    """Test that no tools are available when no API keys are set."""
    original_keys = {
        "OPENAI_API_KEY": os.environ.pop("OPENAI_API_KEY", None),
        "ANTHROPIC_API_KEY": os.environ.pop("ANTHROPIC_API_KEY", None),
        "GEMINI_API_KEY": os.environ.pop("GEMINI_API_KEY", None),
    }

    try:
        assert not await is_provider_available(ProviderType.OPENAI)
        assert not await is_provider_available(ProviderType.ANTHROPIC)
        assert not await is_provider_available(ProviderType.GOOGLE)

        tools = await get_available_web_search_tools()
        assert tools == []

    finally:
        for key, value in original_keys.items():
            if value:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]


@pytest.mark.asyncio
async def test_falls_back_when_only_anthropic_key():
    """Test fallback to Anthropic when only Anthropic key is available."""
    original_keys = {
        "OPENAI_API_KEY": os.environ.pop("OPENAI_API_KEY", None),
        "ANTHROPIC_API_KEY": os.environ.pop("ANTHROPIC_API_KEY", None),
        "GEMINI_API_KEY": os.environ.pop("GEMINI_API_KEY", None),
    }

    try:
        os.environ["ANTHROPIC_API_KEY"] = "test_key"

        tools = await get_available_web_search_tools()
        assert len(tools) == 1
        assert "anthropic" in tools[0].__name__

    finally:
        for key, value in original_keys.items():
            if value:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]
