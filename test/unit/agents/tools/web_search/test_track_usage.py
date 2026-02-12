"""Tests for the track_usage utility function."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import RunUsage
from pydantic_ai.usage import RequestUsage

from shotgun.agents.config.models import ProviderType
from shotgun.agents.tools.web_search.utils import track_usage


@pytest.mark.asyncio
@patch("shotgun.agents.tools.web_search.utils.get_session_usage_manager")
async def test_track_usage_converts_request_usage(
    mock_get_manager: MagicMock,
) -> None:
    """track_usage should convert RequestUsage to RunUsage and call add_usage."""
    mock_manager = AsyncMock()
    mock_get_manager.return_value = mock_manager

    request_usage = RequestUsage(
        input_tokens=100,
        output_tokens=50,
        cache_write_tokens=10,
        cache_read_tokens=20,
    )

    await track_usage(
        request_usage, model_name="claude-haiku-4.5", provider=ProviderType.ANTHROPIC
    )

    mock_manager.add_usage.assert_called_once()
    call_args = mock_manager.add_usage.call_args
    run_usage = call_args[0][0]
    assert isinstance(run_usage, RunUsage)
    assert run_usage.input_tokens == 100
    assert run_usage.output_tokens == 50
    assert run_usage.cache_write_tokens == 10
    assert run_usage.cache_read_tokens == 20


@pytest.mark.asyncio
@patch("shotgun.agents.tools.web_search.utils.get_session_usage_manager")
async def test_track_usage_passes_run_usage_directly(
    mock_get_manager: MagicMock,
) -> None:
    """track_usage should pass RunUsage through without conversion."""
    mock_manager = AsyncMock()
    mock_get_manager.return_value = mock_manager

    run_usage = RunUsage(input_tokens=300, output_tokens=150)

    await track_usage(
        run_usage, model_name="gpt-5-mini", provider=ProviderType.OPENAI
    )

    mock_manager.add_usage.assert_called_once()
    call_args = mock_manager.add_usage.call_args
    assert call_args[0][0] is run_usage


@pytest.mark.asyncio
@patch("shotgun.agents.tools.web_search.utils.get_session_usage_manager")
async def test_track_usage_skips_none(
    mock_get_manager: MagicMock,
) -> None:
    """track_usage should not call add_usage when usage is None."""
    mock_manager = AsyncMock()
    mock_get_manager.return_value = mock_manager

    await track_usage(
        None, model_name="claude-haiku-4.5", provider=ProviderType.ANTHROPIC
    )

    mock_manager.add_usage.assert_not_called()


@pytest.mark.asyncio
@patch("shotgun.agents.tools.web_search.utils.get_session_usage_manager")
async def test_track_usage_swallows_exceptions(
    mock_get_manager: MagicMock,
) -> None:
    """track_usage should not raise when add_usage fails."""
    mock_manager = AsyncMock()
    mock_manager.add_usage.side_effect = RuntimeError("boom")
    mock_get_manager.return_value = mock_manager

    request_usage = RequestUsage(input_tokens=100, output_tokens=50)

    # Should not raise
    await track_usage(
        request_usage, model_name="claude-haiku-4.5", provider=ProviderType.ANTHROPIC
    )
