"""Tests for the cowboy mode push_to_remote feature."""

from shotgun.agents.autopilot.autopilot_orchestrator import (
    AutopilotConfig,
    AutopilotOrchestrator,
)
from shotgun.agents.autopilot.models import (
    AutopilotMode,
    AutopilotState,
)
from shotgun.agents.autopilot.prompts import render_review_code
from shotgun.tui.screens.autopilot_startup import AutopilotStartResult


def test_autopilot_start_result_push_to_remote_defaults_false():
    """AutopilotStartResult.push_to_remote defaults to False."""
    result = AutopilotStartResult(started=True)
    assert result.push_to_remote is False


def test_autopilot_start_result_push_to_remote_true():
    """AutopilotStartResult.push_to_remote can be set to True."""
    result = AutopilotStartResult(started=True, push_to_remote=True)
    assert result.push_to_remote is True


def test_autopilot_state_push_to_remote_defaults_false():
    """AutopilotState.push_to_remote defaults to False."""
    state = AutopilotState()
    assert state.push_to_remote is False


def test_autopilot_state_push_to_remote_true():
    """AutopilotState.push_to_remote can be set to True."""
    state = AutopilotState(push_to_remote=True)
    assert state.push_to_remote is True


def test_autopilot_config_push_to_remote_defaults_false():
    """AutopilotConfig.push_to_remote defaults to False."""
    config = AutopilotConfig()
    assert config.push_to_remote is False


def test_autopilot_config_push_to_remote_true():
    """AutopilotConfig.push_to_remote can be set to True."""
    config = AutopilotConfig(push_to_remote=True)
    assert config.push_to_remote is True


def test_orchestrator_cowboy_mode_local_by_default():
    """Orchestrator in cowboy mode defaults to local-only (no push)."""
    config = AutopilotConfig(push_to_remote=False)
    orchestrator = AutopilotOrchestrator(config)
    orchestrator.set_mode(AutopilotMode.COWBOY)

    assert orchestrator.config.push_to_remote is False
    assert orchestrator.state.mode == AutopilotMode.COWBOY


def test_orchestrator_cowboy_mode_push_enabled():
    """Orchestrator in cowboy mode can enable push to remote."""
    config = AutopilotConfig(push_to_remote=True)
    orchestrator = AutopilotOrchestrator(config)
    orchestrator.set_mode(AutopilotMode.COWBOY)

    assert orchestrator.config.push_to_remote is True
    assert orchestrator.state.mode == AutopilotMode.COWBOY


def test_render_review_code_with_push():
    """Review code prompt includes push instruction when push_to_remote=True."""
    prompt = render_review_code(
        tasks_file_path=".shotgun/tasks.md",
        stage_number="1",
        stage_name="Auth",
        push_to_remote=True,
    )
    assert "Push the changes" in prompt


def test_render_review_code_without_push():
    """Review code prompt omits push instruction when push_to_remote=False."""
    prompt = render_review_code(
        tasks_file_path=".shotgun/tasks.md",
        stage_number="1",
        stage_name="Auth",
        push_to_remote=False,
    )
    assert "Push the changes" not in prompt


def test_render_review_code_defaults_to_push():
    """Review code prompt defaults to including push instruction."""
    prompt = render_review_code(
        tasks_file_path=".shotgun/tasks.md",
        stage_number="1",
        stage_name="Auth",
    )
    assert "Push the changes" in prompt
