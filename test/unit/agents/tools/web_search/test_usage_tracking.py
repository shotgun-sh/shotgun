"""Tests for web search usage tracking."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import RunUsage
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.usage import RequestUsage

from shotgun.agents.config.models import ModelConfig, ModelName, ProviderType


def _make_model_config(
    name: str = "claude-haiku-4.5",
    provider: ProviderType = ProviderType.ANTHROPIC,
) -> ModelConfig:
    return ModelConfig(
        name=name,
        provider=provider,
        key_provider="byok",
        max_input_tokens=200000,
        max_output_tokens=8192,
        api_key="test-key",
    )


def _make_model_response(
    text: str = "Search results here",
    input_tokens: int = 100,
    output_tokens: int = 50,
) -> ModelResponse:
    return ModelResponse(
        parts=[TextPart(content=text)],
        usage=RequestUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
        model_name="test-model",
    )


@pytest.mark.asyncio
@patch("shotgun.agents.tools.web_search.anthropic.track_usage", new_callable=AsyncMock)
@patch("shotgun.agents.tools.web_search.anthropic.shotgun_model_request")
@patch("shotgun.agents.tools.web_search.anthropic.get_provider_model")
async def test_anthropic_web_search_tracks_usage(
    mock_get_provider_model: AsyncMock,
    mock_model_request: AsyncMock,
    mock_track_usage: AsyncMock,
) -> None:
    """Anthropic web search should call track_usage after a successful search."""
    from shotgun.agents.tools.web_search.anthropic import anthropic_web_search_tool

    model_config = _make_model_config(
        name=ModelName.CLAUDE_HAIKU_4_5, provider=ProviderType.ANTHROPIC
    )
    mock_get_provider_model.return_value = model_config

    response = _make_model_response(input_tokens=150, output_tokens=75)
    mock_model_request.return_value = response

    result = await anthropic_web_search_tool("test query")

    assert result == "Search results here"
    mock_track_usage.assert_called_once_with(
        response.usage,
        model_name=ModelName.CLAUDE_HAIKU_4_5,
        provider=ProviderType.ANTHROPIC,
    )


@pytest.mark.asyncio
@patch("shotgun.agents.tools.web_search.anthropic.track_usage", new_callable=AsyncMock)
@patch("shotgun.agents.tools.web_search.anthropic.shotgun_model_request")
@patch("shotgun.agents.tools.web_search.anthropic.get_provider_model")
async def test_anthropic_web_search_calls_track_usage_with_none(
    mock_get_provider_model: AsyncMock,
    mock_model_request: AsyncMock,
    mock_track_usage: AsyncMock,
) -> None:
    """Anthropic web search should call track_usage even when usage is None."""
    from shotgun.agents.tools.web_search.anthropic import anthropic_web_search_tool

    model_config = _make_model_config()
    mock_get_provider_model.return_value = model_config

    response = ModelResponse(
        parts=[TextPart(content="results")],
        usage=None,
        model_name="test-model",
    )
    mock_model_request.return_value = response

    await anthropic_web_search_tool("test query")

    mock_track_usage.assert_called_once_with(
        None, model_name="claude-haiku-4.5", provider=ProviderType.ANTHROPIC
    )


@pytest.mark.asyncio
@patch("shotgun.agents.tools.web_search.gemini.track_usage", new_callable=AsyncMock)
@patch("shotgun.agents.tools.web_search.gemini.shotgun_model_request")
@patch("shotgun.agents.tools.web_search.gemini.get_provider_model")
async def test_gemini_web_search_tracks_usage(
    mock_get_provider_model: AsyncMock,
    mock_model_request: AsyncMock,
    mock_track_usage: AsyncMock,
) -> None:
    """Gemini web search should call track_usage after a successful search."""
    from shotgun.agents.tools.web_search.gemini import gemini_web_search_tool

    model_config = _make_model_config(
        name=ModelName.GEMINI_3_FLASH_PREVIEW, provider=ProviderType.GOOGLE
    )
    mock_get_provider_model.return_value = model_config

    response = _make_model_response(input_tokens=200, output_tokens=100)
    mock_model_request.return_value = response

    result = await gemini_web_search_tool("test query")

    assert result == "Search results here"
    mock_track_usage.assert_called_once_with(
        response.usage,
        model_name=ModelName.GEMINI_3_FLASH_PREVIEW,
        provider=ProviderType.GOOGLE,
    )


@pytest.mark.asyncio
@patch("shotgun.agents.tools.web_search.gemini.track_usage", new_callable=AsyncMock)
@patch("shotgun.agents.tools.web_search.gemini.shotgun_model_request")
@patch("shotgun.agents.tools.web_search.gemini.get_provider_model")
async def test_gemini_web_search_calls_track_usage_with_none(
    mock_get_provider_model: AsyncMock,
    mock_model_request: AsyncMock,
    mock_track_usage: AsyncMock,
) -> None:
    """Gemini web search should call track_usage even when usage is None."""
    from shotgun.agents.tools.web_search.gemini import gemini_web_search_tool

    model_config = _make_model_config(
        name=ModelName.GEMINI_3_FLASH_PREVIEW, provider=ProviderType.GOOGLE
    )
    mock_get_provider_model.return_value = model_config

    response = ModelResponse(
        parts=[TextPart(content="results")],
        usage=None,
        model_name="test-model",
    )
    mock_model_request.return_value = response

    await gemini_web_search_tool("test query")

    mock_track_usage.assert_called_once_with(
        None,
        model_name=ModelName.GEMINI_3_FLASH_PREVIEW,
        provider=ProviderType.GOOGLE,
    )


@pytest.mark.asyncio
@patch("shotgun.agents.tools.web_search.openai.track_usage", new_callable=AsyncMock)
@patch("shotgun.agents.tools.web_search.openai.AsyncOpenAI")
@patch("shotgun.agents.tools.web_search.openai.get_provider_model")
async def test_openai_web_search_tracks_usage(
    mock_get_provider_model: AsyncMock,
    mock_openai_cls: MagicMock,
    mock_track_usage: AsyncMock,
) -> None:
    """OpenAI web search should call track_usage after a successful search."""
    from shotgun.agents.tools.web_search.openai import openai_web_search_tool

    model_config = _make_model_config(name="gpt-5-mini", provider=ProviderType.OPENAI)
    mock_get_provider_model.return_value = model_config

    # Mock the OpenAI response with usage
    mock_usage = MagicMock()
    mock_usage.input_tokens = 300
    mock_usage.output_tokens = 150

    mock_response = MagicMock()
    mock_response.output_text = "OpenAI search results"
    mock_response.usage = mock_usage

    mock_client = AsyncMock()
    mock_client.responses.create = AsyncMock(return_value=mock_response)
    mock_openai_cls.return_value = mock_client

    result = await openai_web_search_tool("test query")

    assert result == "OpenAI search results"
    mock_track_usage.assert_called_once()
    call_args = mock_track_usage.call_args
    usage_arg = call_args[0][0]
    assert isinstance(usage_arg, RunUsage)
    assert usage_arg.input_tokens == 300
    assert usage_arg.output_tokens == 150
    assert call_args[1]["model_name"] == "gpt-5-mini"
    assert call_args[1]["provider"] == ProviderType.OPENAI


@pytest.mark.asyncio
@patch("shotgun.agents.tools.web_search.openai.track_usage", new_callable=AsyncMock)
@patch("shotgun.agents.tools.web_search.openai.AsyncOpenAI")
@patch("shotgun.agents.tools.web_search.openai.get_provider_model")
async def test_openai_web_search_no_usage_when_none(
    mock_get_provider_model: AsyncMock,
    mock_openai_cls: MagicMock,
    mock_track_usage: AsyncMock,
) -> None:
    """OpenAI web search should pass None to track_usage when response.usage is None."""
    from shotgun.agents.tools.web_search.openai import openai_web_search_tool

    model_config = _make_model_config(name="gpt-5-mini", provider=ProviderType.OPENAI)
    mock_get_provider_model.return_value = model_config

    mock_response = MagicMock()
    mock_response.output_text = "results"
    mock_response.usage = None

    mock_client = AsyncMock()
    mock_client.responses.create = AsyncMock(return_value=mock_response)
    mock_openai_cls.return_value = mock_client

    await openai_web_search_tool("test query")

    mock_track_usage.assert_called_once()
    call_args = mock_track_usage.call_args
    assert call_args[0][0] is None
