"""Integration tests for web search tool availability."""

import os

from shotgun.agents.config.models import ProviderType
from shotgun.agents.tools.web_search import (
    get_available_web_search_tools,
    is_provider_available,
)


def test_get_available_web_search_tools():
    """Test that get_available_web_search_tools returns correct tools."""
    tools = get_available_web_search_tools()

    # Should return a list
    assert isinstance(tools, list)

    # Count expected tools based on available API keys
    expected_count = 0
    if os.getenv("OPENAI_API_KEY"):
        expected_count += 1
    if os.getenv("ANTHROPIC_API_KEY"):
        expected_count += 1
    if os.getenv("GEMINI_API_KEY"):
        expected_count += 1

    # Should match the expected count
    assert len(tools) == expected_count

    # Each tool should be callable
    for tool in tools:
        assert callable(tool)
        assert hasattr(tool, "__name__")
        assert "web_search_tool" in tool.__name__


def test_provider_availability_detection():
    """Test that provider availability detection works correctly."""
    # Test with actual environment variables
    openai_available = is_provider_available(ProviderType.OPENAI)
    anthropic_available = is_provider_available(ProviderType.ANTHROPIC)
    google_available = is_provider_available(ProviderType.GOOGLE)

    # Check consistency with environment variables
    assert openai_available == bool(os.getenv("OPENAI_API_KEY"))
    assert anthropic_available == bool(os.getenv("ANTHROPIC_API_KEY"))
    assert google_available == bool(os.getenv("GEMINI_API_KEY"))


def test_no_tools_available_when_no_api_keys():
    """Test that no tools are available when no API keys are set."""
    # Save original API keys
    original_keys = {
        "OPENAI_API_KEY": os.environ.pop("OPENAI_API_KEY", None),
        "ANTHROPIC_API_KEY": os.environ.pop("ANTHROPIC_API_KEY", None),
        "GEMINI_API_KEY": os.environ.pop("GEMINI_API_KEY", None),
    }

    try:
        # No providers should be available
        assert not is_provider_available(ProviderType.OPENAI)
        assert not is_provider_available(ProviderType.ANTHROPIC)
        assert not is_provider_available(ProviderType.GOOGLE)

        # Should return empty list
        tools = get_available_web_search_tools()
        assert tools == []

    finally:
        # Restore API keys
        for key, value in original_keys.items():
            if value:
                os.environ[key] = value


def test_selective_tool_availability():
    """Test that only tools with API keys are available."""
    # Save original API keys
    original_keys = {
        "OPENAI_API_KEY": os.environ.pop("OPENAI_API_KEY", None),
        "ANTHROPIC_API_KEY": os.environ.pop("ANTHROPIC_API_KEY", None),
        "GEMINI_API_KEY": os.environ.pop("GEMINI_API_KEY", None),
    }

    try:
        # Set only OpenAI key
        os.environ["OPENAI_API_KEY"] = "test_key"

        assert is_provider_available(ProviderType.OPENAI)
        assert not is_provider_available(ProviderType.ANTHROPIC)
        assert not is_provider_available(ProviderType.GOOGLE)

        tools = get_available_web_search_tools()
        assert len(tools) == 1
        assert "openai" in tools[0].__name__

        # Add Anthropic key
        os.environ["ANTHROPIC_API_KEY"] = "test_key"

        assert is_provider_available(ProviderType.ANTHROPIC)
        tools = get_available_web_search_tools()
        assert len(tools) == 2

        # Add Gemini key
        os.environ["GEMINI_API_KEY"] = "test_key"

        assert is_provider_available(ProviderType.GOOGLE)
        tools = get_available_web_search_tools()
        assert len(tools) == 3

    finally:
        # Restore API keys
        for key, value in original_keys.items():
            if value:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]
