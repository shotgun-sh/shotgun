"""Tests for the autopilot orchestrator."""

from pathlib import Path

import pytest

from shotgun.agents.autopilot.autopilot_orchestrator import (
    AutopilotConfig,
    AutopilotOrchestrator,
)
from shotgun.agents.autopilot.models import (
    AutopilotMode,
    Stage,
    StageStatus,
    Task,
)


def test_config_defaults():
    """Test AutopilotConfig default values."""
    config = AutopilotConfig()

    assert config.tasks_file_path == ".shotgun/tasks.md"
    assert config.base_branch == "main"
    assert config.branch_prefix == "autopilot/stage-"


def test_config_custom_values():
    """Test AutopilotConfig with custom values."""
    config = AutopilotConfig(
        working_directory=Path("/custom/path"),
        tasks_file_path="custom/tasks.md",
        base_branch="develop",
        branch_prefix="feature/autopilot-",
    )

    assert config.working_directory == Path("/custom/path")
    assert config.tasks_file_path == "custom/tasks.md"
    assert config.base_branch == "develop"
    assert config.branch_prefix == "feature/autopilot-"


def test_orchestrator_initialization():
    """Test AutopilotOrchestrator initialization."""
    config = AutopilotConfig(base_branch="main")
    orchestrator = AutopilotOrchestrator(config)

    assert orchestrator.state.mode == AutopilotMode.PAUSE_BETWEEN
    assert orchestrator.state.stages == []
    assert orchestrator.state.base_branch == "main"
    assert orchestrator.is_complete is False


def test_set_mode():
    """Test setting execution mode."""
    orchestrator = AutopilotOrchestrator()

    orchestrator.set_mode(AutopilotMode.AUTO_CONTINUE)
    assert orchestrator.state.mode == AutopilotMode.AUTO_CONTINUE

    orchestrator.set_mode(AutopilotMode.PAUSE_BETWEEN)
    assert orchestrator.state.mode == AutopilotMode.PAUSE_BETWEEN


def test_advance_to_next_stage():
    """Test advancing through stages."""
    stages = [
        Stage(number="1", name="Stage 1", tasks=[]),
        Stage(number="2", name="Stage 2", tasks=[]),
        Stage(number="3", name="Stage 3", tasks=[]),
    ]
    orchestrator = AutopilotOrchestrator()
    orchestrator.state.stages = stages

    # Start at stage 0
    assert orchestrator.state.current_stage_index == 0
    assert orchestrator.state.current_stage.number == "1"

    # Advance to stage 2
    result = orchestrator.advance_to_next_stage()
    assert result is True
    assert orchestrator.state.current_stage_index == 1
    assert orchestrator.state.current_stage.number == "2"

    # Advance to stage 3
    result = orchestrator.advance_to_next_stage()
    assert result is True
    assert orchestrator.state.current_stage_index == 2

    # Cannot advance past last stage
    result = orchestrator.advance_to_next_stage()
    assert result is False
    assert orchestrator.state.current_stage_index == 2


def test_is_complete():
    """Test is_complete property."""
    stages = [
        Stage(number="1", name="Stage 1", status=StageStatus.PENDING, tasks=[]),
        Stage(number="2", name="Stage 2", status=StageStatus.PENDING, tasks=[]),
    ]
    orchestrator = AutopilotOrchestrator()
    orchestrator.state.stages = stages

    # Not complete
    assert orchestrator.is_complete is False

    # Mark first complete
    stages[0].status = StageStatus.COMPLETED
    assert orchestrator.is_complete is False

    # Mark all complete
    stages[1].status = StageStatus.COMPLETED
    assert orchestrator.is_complete is True


def test_awaiting_approval_set_by_workflow():
    """Test awaiting_approval is set after workflow completes."""
    stages = [
        Stage(number="1", name="Stage 1", status=StageStatus.COMPLETED, tasks=[]),
        Stage(number="2", name="Stage 2", status=StageStatus.PENDING, tasks=[]),
    ]
    orchestrator = AutopilotOrchestrator()
    orchestrator.state.stages = stages
    orchestrator.state.mode = AutopilotMode.PAUSE_BETWEEN

    # Initially not awaiting approval
    assert orchestrator.awaiting_approval is False

    # Manually set awaiting_approval (simulating workflow completion)
    orchestrator.state.awaiting_approval = True
    assert orchestrator.awaiting_approval is True


def test_awaiting_approval_default_false():
    """Test awaiting_approval defaults to false."""
    stages = [
        Stage(number="1", name="Stage 1", status=StageStatus.COMPLETED, tasks=[]),
        Stage(number="2", name="Stage 2", status=StageStatus.PENDING, tasks=[]),
    ]
    orchestrator = AutopilotOrchestrator()
    orchestrator.state.stages = stages
    orchestrator.state.mode = AutopilotMode.AUTO_CONTINUE

    # Default is False
    assert orchestrator.awaiting_approval is False


def test_build_execution_prompt():
    """Test building prompt for Claude."""
    tasks = [
        Task(text="Create login form", completed=False, line_number=10),
        Task(text="Add validation", completed=True, line_number=11),
    ]
    stage = Stage(number="1", name="Authentication", tasks=tasks)

    orchestrator = AutopilotOrchestrator()
    orchestrator.state.stages = [stage]

    prompt = orchestrator._build_execution_prompt(stage)

    assert "Stage 1" in prompt
    assert "Authentication" in prompt
    assert "Create login form" in prompt
    # Completed tasks should not be in the prompt (only pending)
    assert "Add validation" not in prompt
    assert ".shotgun/tasks.md" in prompt


@pytest.mark.asyncio
async def test_cancel():
    """Test cancellation."""
    orchestrator = AutopilotOrchestrator()

    # Should not raise
    await orchestrator.cancel()

    assert orchestrator._cancelled is True
