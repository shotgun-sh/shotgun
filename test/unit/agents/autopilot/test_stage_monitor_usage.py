"""Tests for stage monitor usage tracking."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import RunUsage

from shotgun.agents.autopilot.models import MonitorAction, MonitorDecision
from shotgun.agents.autopilot.stage_monitor import StageMonitor
from shotgun.agents.config.models import ModelConfig, ProviderType


def _make_model_config() -> ModelConfig:
    return ModelConfig(
        name="claude-opus-4-5",
        provider=ProviderType.ANTHROPIC,
        key_provider="byok",
        max_input_tokens=200000,
        max_output_tokens=8192,
        api_key="test-key",
    )


@pytest.mark.asyncio
@patch("shotgun.agents.autopilot.stage_monitor.get_session_usage_manager")
async def test_stage_monitor_tracks_usage_after_evaluate(
    mock_get_usage_manager: MagicMock,
) -> None:
    """Stage monitor should call add_usage after agent.run() completes."""
    monitor = StageMonitor(working_directory=Path("/test"))

    model_config = _make_model_config()
    monitor._model_config = model_config

    mock_decision = MonitorDecision(
        action=MonitorAction.COMPLETE,
        reasoning="All done",
    )

    mock_usage = RunUsage(input_tokens=500, output_tokens=200)
    mock_result = MagicMock()
    mock_result.output = mock_decision
    mock_result.usage.return_value = mock_usage

    mock_agent = AsyncMock()
    mock_agent.run = AsyncMock(return_value=mock_result)

    mock_manager = AsyncMock()
    mock_get_usage_manager.return_value = mock_manager

    with patch.object(monitor, "_get_agent", return_value=mock_agent):
        decision = await monitor.evaluate(
            claude_output_summary="Did some work",
            stage_number="1",
            stage_name="Test Stage",
            working_directory=Path("/test"),
            tasks_file_path=".shotgun/tasks.md",
        )

    assert decision.action == MonitorAction.COMPLETE
    mock_manager.add_usage.assert_called_once()
    call_kwargs = mock_manager.add_usage.call_args
    assert call_kwargs[0][0] == mock_usage
    assert call_kwargs[1]["model_name"] == "claude-opus-4-5"
    assert call_kwargs[1]["provider"] == ProviderType.ANTHROPIC


@pytest.mark.asyncio
@patch("shotgun.agents.autopilot.stage_monitor.get_session_usage_manager")
async def test_stage_monitor_tracks_zero_usage(
    mock_get_usage_manager: MagicMock,
) -> None:
    """Stage monitor should still call add_usage even with zero-token usage."""
    monitor = StageMonitor(working_directory=Path("/test"))

    model_config = _make_model_config()
    monitor._model_config = model_config

    mock_decision = MonitorDecision(
        action=MonitorAction.COMPLETE,
        reasoning="All done",
    )

    # RunUsage with zeros is still truthy
    zero_usage = RunUsage()
    mock_result = MagicMock()
    mock_result.output = mock_decision
    mock_result.usage.return_value = zero_usage

    mock_agent = AsyncMock()
    mock_agent.run = AsyncMock(return_value=mock_result)

    mock_manager = AsyncMock()
    mock_get_usage_manager.return_value = mock_manager

    with patch.object(monitor, "_get_agent", return_value=mock_agent):
        await monitor.evaluate(
            claude_output_summary="Did some work",
            stage_number="1",
            stage_name="Test Stage",
            working_directory=Path("/test"),
            tasks_file_path=".shotgun/tasks.md",
        )

    mock_manager.add_usage.assert_called_once()
    call_kwargs = mock_manager.add_usage.call_args
    assert call_kwargs[0][0] == zero_usage


@pytest.mark.asyncio
@patch("shotgun.agents.autopilot.stage_monitor.get_session_usage_manager")
async def test_stage_monitor_no_usage_when_no_model_config(
    mock_get_usage_manager: MagicMock,
) -> None:
    """Stage monitor should not call add_usage when _model_config is None."""
    monitor = StageMonitor(working_directory=Path("/test"))
    # _model_config defaults to None

    mock_decision = MonitorDecision(
        action=MonitorAction.COMPLETE,
        reasoning="All done",
    )

    mock_usage = RunUsage(input_tokens=500, output_tokens=200)
    mock_result = MagicMock()
    mock_result.output = mock_decision
    mock_result.usage.return_value = mock_usage

    mock_agent = AsyncMock()
    mock_agent.run = AsyncMock(return_value=mock_result)

    mock_manager = AsyncMock()
    mock_get_usage_manager.return_value = mock_manager

    with patch.object(monitor, "_get_agent", return_value=mock_agent):
        await monitor.evaluate(
            claude_output_summary="Did some work",
            stage_number="1",
            stage_name="Test Stage",
            working_directory=Path("/test"),
            tasks_file_path=".shotgun/tasks.md",
        )

    mock_manager.add_usage.assert_not_called()


@pytest.mark.asyncio
@patch("shotgun.agents.autopilot.stage_monitor.get_provider_model")
async def test_stage_monitor_get_agent_stores_model_config(
    mock_get_provider_model: AsyncMock,
) -> None:
    """_get_agent should store model_config on self for usage tracking."""
    monitor = StageMonitor(working_directory=Path("/test"))
    assert monitor._model_config is None

    # Use a MagicMock for model_config so .model_instance doesn't trigger real code
    model_config = MagicMock()
    model_config.name = "claude-opus-4-5"
    model_config.provider = ProviderType.ANTHROPIC
    mock_get_provider_model.return_value = model_config

    # Mock Agent to avoid actual model instantiation
    with patch("shotgun.agents.autopilot.stage_monitor.Agent") as mock_agent_cls:
        mock_agent_instance = MagicMock()
        mock_agent_instance.tool = lambda f: f
        mock_agent_cls.return_value = mock_agent_instance

        await monitor._get_agent()

    assert monitor._model_config is model_config
