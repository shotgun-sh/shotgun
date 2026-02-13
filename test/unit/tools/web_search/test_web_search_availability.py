"""Unit tests for web search tool availability/selection logic."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from shotgun.agents.config.models import ProviderType
from shotgun.agents.tools.web_search import (
    anthropic_web_search_tool,
    gemini_web_search_tool,
    get_available_web_search_tools,
    openai_compatible_web_search_tool,
    openai_web_search_tool,
)


def _mock_config(shotgun_api_key: str | None = None, selected_model=None):
    """Create a mock config with the given settings."""
    config = Mock()
    config.shotgun.api_key = shotgun_api_key
    config.selected_model = selected_model
    return config


def _patch_config(config):
    """Patch config manager to return the given config."""
    mock_manager = AsyncMock()
    mock_manager.load.return_value = config
    return patch(
        "shotgun.agents.tools.web_search.get_config_manager",
        return_value=mock_manager,
    )


def _patch_settings(openai_compat_base_url=None, openai_compat_api_key=None):
    """Patch settings for OpenAI-compatible mode."""
    mock_settings = Mock()
    mock_settings.openai_compat.base_url = openai_compat_base_url
    mock_settings.openai_compat.api_key = openai_compat_api_key
    return patch("shotgun.agents.tools.web_search.settings", mock_settings)


def _patch_provider_available(available_providers: set[ProviderType]):
    """Patch is_provider_available to return True for the given providers."""

    async def mock_is_available(provider: ProviderType) -> bool:
        return provider in available_providers

    return patch(
        "shotgun.agents.tools.web_search.is_provider_available",
        side_effect=mock_is_available,
    )


@pytest.mark.asyncio
async def test_openai_compat_takes_highest_priority():
    """OpenAI-compatible mode overrides everything else."""
    config = _mock_config(shotgun_api_key="shotgun-key")
    with (
        _patch_settings("https://proxy.example.com", "compat-key"),
        _patch_config(config),
        _patch_provider_available({ProviderType.GOOGLE, ProviderType.ANTHROPIC}),
    ):
        tools = await get_available_web_search_tools()
        assert tools == [openai_compatible_web_search_tool]


@pytest.mark.asyncio
async def test_shotgun_account_uses_gemini():
    """Shotgun Account users always get Gemini web search."""
    config = _mock_config(shotgun_api_key="shotgun-key")
    with (
        _patch_settings(),
        _patch_config(config),
        _patch_provider_available({ProviderType.ANTHROPIC}),
    ):
        tools = await get_available_web_search_tools()
        assert tools == [gemini_web_search_tool]


@pytest.mark.asyncio
async def test_byok_prefers_gemini_when_available():
    """BYOK user with Google key should get Gemini web search even if other providers are available."""
    config = _mock_config()
    with (
        _patch_settings(),
        _patch_config(config),
        _patch_provider_available(
            {ProviderType.GOOGLE, ProviderType.ANTHROPIC, ProviderType.OPENAI}
        ),
    ):
        tools = await get_available_web_search_tools()
        assert tools == [gemini_web_search_tool]


@pytest.mark.asyncio
async def test_byok_prefers_gemini_over_anthropic():
    """BYOK user with both Google and Anthropic keys should get Gemini."""
    config = _mock_config()
    with (
        _patch_settings(),
        _patch_config(config),
        _patch_provider_available({ProviderType.GOOGLE, ProviderType.ANTHROPIC}),
    ):
        tools = await get_available_web_search_tools()
        assert tools == [gemini_web_search_tool]


@pytest.mark.asyncio
async def test_byok_falls_back_to_anthropic_without_gemini():
    """BYOK user without Google key falls back to Anthropic."""
    config = _mock_config()
    with (
        _patch_settings(),
        _patch_config(config),
        _patch_provider_available({ProviderType.ANTHROPIC}),
    ):
        tools = await get_available_web_search_tools()
        assert tools == [anthropic_web_search_tool]


@pytest.mark.asyncio
async def test_byok_falls_back_to_openai_without_gemini():
    """BYOK user with only OpenAI key falls back to OpenAI."""
    config = _mock_config()
    with (
        _patch_settings(),
        _patch_config(config),
        _patch_provider_available({ProviderType.OPENAI}),
    ):
        tools = await get_available_web_search_tools()
        assert tools == [openai_web_search_tool]


@pytest.mark.asyncio
async def test_no_providers_returns_empty():
    """No API keys configured returns empty list."""
    config = _mock_config()
    with (
        _patch_settings(),
        _patch_config(config),
        _patch_provider_available(set()),
    ):
        tools = await get_available_web_search_tools()
        assert tools == []
