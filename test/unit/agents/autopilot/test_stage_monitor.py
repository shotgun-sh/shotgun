"""Tests for the stage monitor agent."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from shotgun.agents.autopilot.models import (
    MonitorAction,
    MonitorDecision,
)
from shotgun.agents.autopilot.stage_monitor import (
    MonitorDeps,
    StageMonitor,
)


def test_monitor_action_enum():
    """Test MonitorAction enum values."""
    assert MonitorAction.CONTINUE == "continue"
    assert MonitorAction.REVIEW == "review"
    assert MonitorAction.CREATE_PR == "create_pr"
    assert MonitorAction.COMPLETE == "complete"
    assert MonitorAction.ESCALATE == "escalate"
    assert MonitorAction.DEFER == "defer"


def test_monitor_decision_model():
    """Test MonitorDecision model creation."""
    decision = MonitorDecision(
        action=MonitorAction.CONTINUE,
        reasoning="Tasks remain incomplete",
        next_prompt="Please finish task 3",
    )
    assert decision.action == MonitorAction.CONTINUE
    assert decision.reasoning == "Tasks remain incomplete"
    assert decision.next_prompt == "Please finish task 3"


def test_monitor_decision_defaults():
    """Test MonitorDecision model defaults."""
    decision = MonitorDecision(
        action=MonitorAction.COMPLETE,
        reasoning="All tasks verified",
    )
    assert decision.next_prompt is None


def test_monitor_decision_escalate():
    """Test MonitorDecision with escalate action."""
    decision = MonitorDecision(
        action=MonitorAction.ESCALATE,
        reasoning="Claude Code claims done but 3 tasks unchecked",
    )
    assert decision.action == MonitorAction.ESCALATE
    assert "unchecked" in decision.reasoning


def test_monitor_decision_defer():
    """Test MonitorDecision with defer action."""
    decision = MonitorDecision(
        action=MonitorAction.DEFER,
        reasoning="Task is blocked by external dependency",
    )
    assert decision.action == MonitorAction.DEFER


def test_monitor_deps():
    """Test MonitorDeps creation."""
    deps = MonitorDeps(
        working_directory=Path("/test/project"),
        tasks_file_path=".shotgun/tasks.md",
    )
    assert deps.working_directory == Path("/test/project")
    assert deps.tasks_file_path == ".shotgun/tasks.md"


def test_stage_monitor_init():
    """Test StageMonitor initialization."""
    monitor = StageMonitor(working_directory=Path("/test"))
    assert monitor._recent_outputs == []
    assert monitor._max_history == 3
    assert monitor._agent is None


def test_stage_monitor_format_history_empty():
    """Test _format_history with no history."""
    monitor = StageMonitor(working_directory=Path("/test"))
    assert monitor._format_history() == "No previous iterations."


def test_stage_monitor_format_history_with_entries():
    """Test _format_history with entries."""
    monitor = StageMonitor(working_directory=Path("/test"))
    monitor._recent_outputs = ["First output", "Second output"]
    formatted = monitor._format_history()
    assert "### Iteration 1" in formatted
    assert "First output" in formatted
    assert "### Iteration 2" in formatted
    assert "Second output" in formatted


@pytest.mark.asyncio
async def test_stage_monitor_evaluate_tracks_history():
    """Test that evaluate tracks recent outputs."""
    monitor = StageMonitor(working_directory=Path("/test"))

    mock_decision = MonitorDecision(
        action=MonitorAction.COMPLETE,
        reasoning="All done",
    )

    # Mock the agent to avoid actual LLM calls
    mock_agent = AsyncMock()
    mock_agent.run = AsyncMock(return_value=AsyncMock(output=mock_decision))

    with patch.object(monitor, "_get_agent", return_value=mock_agent):
        await monitor.evaluate(
            claude_output_summary="Did some work",
            stage_number="1",
            stage_name="Test Stage",
            working_directory=Path("/test"),
            tasks_file_path=".shotgun/tasks.md",
        )

    assert len(monitor._recent_outputs) == 1
    assert "Did some work" in monitor._recent_outputs[0]


@pytest.mark.asyncio
async def test_stage_monitor_evaluate_limits_history():
    """Test that evaluate limits history to max_history entries."""
    monitor = StageMonitor(working_directory=Path("/test"))
    monitor._recent_outputs = ["old1", "old2", "old3"]

    mock_decision = MonitorDecision(
        action=MonitorAction.CONTINUE,
        reasoning="Keep going",
        next_prompt="Finish task 2",
    )

    mock_agent = AsyncMock()
    mock_agent.run = AsyncMock(return_value=AsyncMock(output=mock_decision))

    with patch.object(monitor, "_get_agent", return_value=mock_agent):
        await monitor.evaluate(
            claude_output_summary="New output",
            stage_number="1",
            stage_name="Test Stage",
            working_directory=Path("/test"),
            tasks_file_path=".shotgun/tasks.md",
        )

    assert len(monitor._recent_outputs) == 3
    # Oldest entry should be dropped
    assert monitor._recent_outputs[0] == "old2"
    assert monitor._recent_outputs[2] == "New output"


@pytest.mark.asyncio
async def test_stage_monitor_evaluate_truncates_long_output():
    """Test that evaluate truncates long Claude output summaries."""
    monitor = StageMonitor(working_directory=Path("/test"))

    mock_decision = MonitorDecision(
        action=MonitorAction.COMPLETE,
        reasoning="Done",
    )

    mock_agent = AsyncMock()
    mock_agent.run = AsyncMock(return_value=AsyncMock(output=mock_decision))

    long_output = "x" * 1000

    with patch.object(monitor, "_get_agent", return_value=mock_agent):
        await monitor.evaluate(
            claude_output_summary=long_output,
            stage_number="1",
            stage_name="Test Stage",
            working_directory=Path("/test"),
            tasks_file_path=".shotgun/tasks.md",
        )

    # Should be truncated to 500 chars
    assert len(monitor._recent_outputs[0]) == 500


@pytest.mark.asyncio
async def test_stage_monitor_evaluate_returns_decision():
    """Test that evaluate returns the monitor decision."""
    monitor = StageMonitor(working_directory=Path("/test"))

    expected_decision = MonitorDecision(
        action=MonitorAction.ESCALATE,
        reasoning="Stuck in a loop",
    )

    mock_agent = AsyncMock()
    mock_agent.run = AsyncMock(return_value=AsyncMock(output=expected_decision))

    with patch.object(monitor, "_get_agent", return_value=mock_agent):
        decision = await monitor.evaluate(
            claude_output_summary="Same output again",
            stage_number="2",
            stage_name="API Integration",
            working_directory=Path("/test"),
            tasks_file_path=".shotgun/tasks.md",
        )

    assert decision.action == MonitorAction.ESCALATE
    assert decision.reasoning == "Stuck in a loop"


@pytest.mark.asyncio
async def test_stage_monitor_evaluate_passes_correct_prompt():
    """Test that evaluate passes stage info in the prompt to the agent."""
    monitor = StageMonitor(working_directory=Path("/test"))

    mock_decision = MonitorDecision(
        action=MonitorAction.CONTINUE,
        reasoning="Still working",
        next_prompt="Do task 4",
    )

    mock_agent = AsyncMock()
    mock_agent.run = AsyncMock(return_value=AsyncMock(output=mock_decision))

    with patch.object(monitor, "_get_agent", return_value=mock_agent):
        await monitor.evaluate(
            claude_output_summary="Made progress on auth",
            stage_number="3",
            stage_name="Authentication",
            working_directory=Path("/test"),
            tasks_file_path=".shotgun/tasks.md",
        )

    # Check the prompt passed to the agent
    call_args = mock_agent.run.call_args
    prompt = call_args[0][0]
    assert "Stage 3" in prompt
    assert "Authentication" in prompt
    assert "Made progress on auth" in prompt
