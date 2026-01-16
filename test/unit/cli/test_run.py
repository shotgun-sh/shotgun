"""Unit tests for the run CLI command."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from shotgun.agents.models import AgentResponse
from shotgun.agents.router import RouterMode
from shotgun.cli.run import app

runner = CliRunner()


@pytest.fixture
def mock_router_agent():
    """Create a mock router agent and deps."""
    mock_agent = MagicMock()
    mock_deps = MagicMock()
    mock_deps.router_mode = (
        RouterMode.PLANNING
    )  # Will be set to DRAFTING by run command
    return mock_agent, mock_deps


@pytest.fixture
def mock_run_result():
    """Create a mock run result."""
    result = MagicMock()
    result.output = AgentResponse(
        response="Test response from router agent",
        clarifying_questions=None,
    )
    return result


@pytest.mark.smoke
def test_run_command_success(mock_router_agent, mock_run_result):
    """Test successful run command execution."""
    mock_agent, mock_deps = mock_router_agent

    with (
        patch(
            "shotgun.cli.run.create_router_agent",
            new_callable=AsyncMock,
            return_value=(mock_agent, mock_deps),
        ) as mock_create,
        patch(
            "shotgun.cli.run.run_router_agent",
            new_callable=AsyncMock,
            return_value=mock_run_result,
        ) as mock_run,
        patch("shotgun.cli.run.track_event") as mock_track,
    ):
        result = runner.invoke(app, ["Test prompt"])

    assert result.exit_code == 0
    assert "Complete!" in result.stdout
    # The AgentResponse object is printed, which includes the response field
    assert "Test response from router agent" in result.stdout

    # Verify agent was created
    mock_create.assert_called_once()

    # Verify router_mode was set to DRAFTING
    assert mock_deps.router_mode == RouterMode.DRAFTING

    # Verify agent was run with the prompt
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    assert call_args[0][0] == mock_agent  # First arg is agent
    assert call_args[0][1] == "Test prompt"  # Second arg is prompt
    assert call_args[0][2] == mock_deps  # Third arg is deps

    # Verify telemetry was tracked
    mock_track.assert_called_once_with(
        "run_command",
        {"non_interactive": False, "provider": "default"},
    )


def test_run_command_non_interactive(mock_router_agent, mock_run_result):
    """Test run command with non-interactive flag."""
    mock_agent, mock_deps = mock_router_agent

    with (
        patch(
            "shotgun.cli.run.create_router_agent",
            new_callable=AsyncMock,
            return_value=(mock_agent, mock_deps),
        ),
        patch(
            "shotgun.cli.run.run_router_agent",
            new_callable=AsyncMock,
            return_value=mock_run_result,
        ),
        patch("shotgun.cli.run.track_event") as mock_track,
    ):
        result = runner.invoke(app, ["--non-interactive", "Test prompt"])

    assert result.exit_code == 0
    mock_track.assert_called_once_with(
        "run_command",
        {"non_interactive": True, "provider": "default"},
    )


def test_run_command_short_non_interactive(mock_router_agent, mock_run_result):
    """Test run command with -n short flag."""
    mock_agent, mock_deps = mock_router_agent

    with (
        patch(
            "shotgun.cli.run.create_router_agent",
            new_callable=AsyncMock,
            return_value=(mock_agent, mock_deps),
        ),
        patch(
            "shotgun.cli.run.run_router_agent",
            new_callable=AsyncMock,
            return_value=mock_run_result,
        ),
        patch("shotgun.cli.run.track_event") as mock_track,
    ):
        result = runner.invoke(app, ["-n", "Test prompt"])

    assert result.exit_code == 0
    mock_track.assert_called_once_with(
        "run_command",
        {"non_interactive": True, "provider": "default"},
    )


def test_run_command_with_provider(mock_router_agent, mock_run_result):
    """Test run command with provider flag."""
    mock_agent, mock_deps = mock_router_agent

    with (
        patch(
            "shotgun.cli.run.create_router_agent",
            new_callable=AsyncMock,
            return_value=(mock_agent, mock_deps),
        ) as mock_create,
        patch(
            "shotgun.cli.run.run_router_agent",
            new_callable=AsyncMock,
            return_value=mock_run_result,
        ),
        patch("shotgun.cli.run.track_event") as mock_track,
    ):
        result = runner.invoke(app, ["--provider", "openai", "Test prompt"])

    assert result.exit_code == 0

    # Verify provider was passed to create_router_agent
    call_args = mock_create.call_args
    from shotgun.agents.config import ProviderType

    assert call_args[0][1] == ProviderType.OPENAI

    # Verify telemetry includes provider
    mock_track.assert_called_once_with(
        "run_command",
        {"non_interactive": False, "provider": "openai"},
    )


def test_run_command_with_short_provider(mock_router_agent, mock_run_result):
    """Test run command with -p short provider flag."""
    mock_agent, mock_deps = mock_router_agent

    with (
        patch(
            "shotgun.cli.run.create_router_agent",
            new_callable=AsyncMock,
            return_value=(mock_agent, mock_deps),
        ),
        patch(
            "shotgun.cli.run.run_router_agent",
            new_callable=AsyncMock,
            return_value=mock_run_result,
        ),
        patch("shotgun.cli.run.track_event") as mock_track,
    ):
        result = runner.invoke(app, ["-p", "anthropic", "Test prompt"])

    assert result.exit_code == 0
    mock_track.assert_called_once_with(
        "run_command",
        {"non_interactive": False, "provider": "anthropic"},
    )


def test_run_command_sets_drafting_mode(mock_router_agent, mock_run_result):
    """Test that run command sets router mode to DRAFTING."""
    mock_agent, mock_deps = mock_router_agent
    # Initially set to PLANNING (default)
    assert mock_deps.router_mode == RouterMode.PLANNING

    with (
        patch(
            "shotgun.cli.run.create_router_agent",
            new_callable=AsyncMock,
            return_value=(mock_agent, mock_deps),
        ),
        patch(
            "shotgun.cli.run.run_router_agent",
            new_callable=AsyncMock,
            return_value=mock_run_result,
        ),
        patch("shotgun.cli.run.track_event"),
    ):
        runner.invoke(app, ["Test prompt"])

    # After run command, mode should be DRAFTING
    assert mock_deps.router_mode == RouterMode.DRAFTING


def test_run_command_no_args():
    """Test run command with no arguments shows usage info."""
    result = runner.invoke(app, [])

    # Typer with no_args_is_help=True shows usage and exits with code 0 (help)
    # But when there's a required argument, it exits with code 2 (missing arg)
    # Either way, usage info should be shown
    assert result.exit_code in (0, 2)
    assert "Usage:" in result.stdout or "run" in result.stdout


def test_run_command_agent_error(mock_router_agent):
    """Test run command handles agent errors gracefully."""
    mock_agent, mock_deps = mock_router_agent

    with (
        patch(
            "shotgun.cli.run.create_router_agent",
            new_callable=AsyncMock,
            return_value=(mock_agent, mock_deps),
        ),
        patch(
            "shotgun.cli.run.run_router_agent",
            new_callable=AsyncMock,
            side_effect=Exception("Agent failed"),
        ),
        patch("shotgun.cli.run.track_event"),
    ):
        result = runner.invoke(app, ["Test prompt"])

    # The command should handle the error and not crash
    assert "An unexpected error occurred" in result.stdout
    assert "Agent failed" in result.stdout


def test_run_command_user_actionable_error(mock_router_agent):
    """Test run command handles user-actionable errors properly."""
    from shotgun.exceptions import ErrorNotPickedUpBySentry

    mock_agent, mock_deps = mock_router_agent

    class TestError(ErrorNotPickedUpBySentry):
        def to_plain_text(self) -> str:
            return "Test user error message"

    with (
        patch(
            "shotgun.cli.run.create_router_agent",
            new_callable=AsyncMock,
            return_value=(mock_agent, mock_deps),
        ),
        patch(
            "shotgun.cli.run.run_router_agent",
            new_callable=AsyncMock,
            side_effect=TestError("User error"),
        ),
        patch("shotgun.cli.run.track_event"),
        patch("shotgun.cli.run.print_agent_error") as mock_print_error,
    ):
        runner.invoke(app, ["Test prompt"])

    # User-actionable errors should be passed to print_agent_error
    mock_print_error.assert_called_once()
    called_exception = mock_print_error.call_args[0][0]
    assert isinstance(called_exception, ErrorNotPickedUpBySentry)
    assert called_exception.to_plain_text() == "Test user error message"
