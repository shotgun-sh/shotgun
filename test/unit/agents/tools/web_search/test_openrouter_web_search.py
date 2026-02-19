"""Tests for OpenRouter web search tool and routing."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import SecretStr

from shotgun.agents.config.models import (
    OPENROUTER_BASE_URL,
    KeyProvider,
)
from shotgun.agents.tools.web_search.openrouter import openrouter_web_search_tool


@pytest.mark.asyncio
async def test_openrouter_web_search_uses_online_variant():
    """OpenRouter web search uses :online model variant."""
    mock_response = Mock()
    mock_response.parts = [Mock(content="Search results")]
    mock_response.parts[0].__class__.__name__ = "TextPart"
    mock_response.usage = Mock()

    with (
        patch(
            "shotgun.agents.tools.web_search.openrouter.get_config_manager"
        ) as mock_get_cm,
        patch(
            "shotgun.agents.tools.web_search.openrouter.shotgun_model_request",
            new_callable=AsyncMock,
        ) as mock_request,
        patch("shotgun.agents.tools.web_search.openrouter.trace") as mock_trace,
        patch(
            "shotgun.agents.tools.web_search.openrouter.track_usage",
            new_callable=AsyncMock,
        ),
    ):
        # Set up config mock
        mock_config = Mock()
        mock_config.openrouter.api_key = SecretStr("or-test-key")
        mock_manager = AsyncMock()
        mock_manager.load.return_value = mock_config
        mock_get_cm.return_value = mock_manager

        mock_request.return_value = mock_response
        mock_trace.get_current_span.return_value = Mock()

        # Import TextPart for isinstance check in the tool
        from pydantic_ai.messages import TextPart

        mock_response.parts = [TextPart(content="Search results")]

        await openrouter_web_search_tool("test query")

        # Verify model_config passed to shotgun_model_request uses :online variant
        call_args = mock_request.call_args
        model_config = call_args.kwargs.get("model_config") or call_args[0][0]
        assert ":online" in str(model_config.name)
        assert model_config.key_provider == KeyProvider.OPENROUTER
        assert model_config.base_url == OPENROUTER_BASE_URL


@pytest.mark.asyncio
async def test_openrouter_web_search_no_api_key():
    """OpenRouter web search returns error when API key is not configured."""
    with (
        patch(
            "shotgun.agents.tools.web_search.openrouter.get_config_manager"
        ) as mock_get_cm,
        patch("shotgun.agents.tools.web_search.openrouter.trace") as mock_trace,
    ):
        mock_config = Mock()
        mock_config.openrouter.api_key = None
        mock_manager = AsyncMock()
        mock_manager.load.return_value = mock_config
        mock_get_cm.return_value = mock_manager
        mock_trace.get_current_span.return_value = Mock()

        result = await openrouter_web_search_tool("test query")

        assert "not configured" in result


@pytest.mark.asyncio
async def test_web_search_routing_prefers_openrouter():
    """get_available_web_search_tools returns OpenRouter tool when OpenRouter key is set."""
    from shotgun.agents.tools.web_search import (
        get_available_web_search_tools,
    )
    from shotgun.agents.tools.web_search import (
        openrouter_web_search_tool as or_tool,
    )

    mock_config = Mock()
    mock_config.shotgun.api_key = None  # No shotgun key
    mock_config.openrouter.api_key = SecretStr("or-key")

    with (
        patch("shotgun.agents.tools.web_search.settings") as mock_settings,
        patch("shotgun.agents.tools.web_search.get_config_manager") as mock_get_cm,
    ):
        mock_settings.openai_compat.base_url = None
        mock_settings.openai_compat.api_key = None
        mock_manager = AsyncMock()
        mock_manager.load.return_value = mock_config
        mock_get_cm.return_value = mock_manager

        tools = await get_available_web_search_tools()

        assert len(tools) == 1
        assert tools[0] is or_tool


@pytest.mark.asyncio
async def test_web_search_routing_shotgun_over_openrouter():
    """Shotgun Account web search takes priority over OpenRouter."""
    from shotgun.agents.tools.web_search import (
        gemini_web_search_tool,
        get_available_web_search_tools,
    )

    mock_config = Mock()
    mock_config.shotgun.api_key = SecretStr("sg-key")  # Shotgun key present
    mock_config.openrouter.api_key = SecretStr("or-key")

    with (
        patch("shotgun.agents.tools.web_search.settings") as mock_settings,
        patch("shotgun.agents.tools.web_search.get_config_manager") as mock_get_cm,
    ):
        mock_settings.openai_compat.base_url = None
        mock_settings.openai_compat.api_key = None
        mock_manager = AsyncMock()
        mock_manager.load.return_value = mock_config
        mock_get_cm.return_value = mock_manager

        tools = await get_available_web_search_tools()

        assert len(tools) == 1
        # Shotgun uses gemini web search, not openrouter
        assert tools[0] is gemini_web_search_tool
