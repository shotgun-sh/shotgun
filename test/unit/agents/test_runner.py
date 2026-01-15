"""Tests for AgentRunner."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from shotgun.agents.models import AgentType
from shotgun.agents.runner import AgentRunner
from shotgun.exceptions import (
    AgentCancelledException,
    BudgetExceededException,
    ContextSizeLimitExceeded,
    UnknownAgentException,
)


def create_mock_agent_manager(exception_to_raise=None):
    """Create a mock agent manager for testing."""
    mock_manager = AsyncMock()

    # Set up deps with llm_model
    mock_llm_model = Mock()
    mock_llm_model.is_shotgun_account = False
    mock_llm_model.name = "gpt-4"

    mock_deps = Mock()
    mock_deps.llm_model = mock_llm_model

    mock_manager.deps = mock_deps
    mock_manager._current_agent_type = AgentType.RESEARCH

    # Configure run behavior
    if exception_to_raise:
        mock_manager.run.side_effect = exception_to_raise
    else:
        mock_manager.run.return_value = None

    return mock_manager


@pytest.mark.asyncio
async def test_runner_success():
    """Test successful agent execution."""
    mock_manager = create_mock_agent_manager()
    runner = AgentRunner(mock_manager)

    # Should not raise any exception
    await runner.run("test prompt")

    mock_manager.run.assert_called_once_with(
        prompt="test prompt", attachment=None, file_contents=None
    )


@pytest.mark.asyncio
async def test_runner_cancelled_error():
    """Test that CancelledError is wrapped in AgentCancelledException."""
    mock_manager = create_mock_agent_manager(asyncio.CancelledError())
    runner = AgentRunner(mock_manager)

    with pytest.raises(AgentCancelledException):
        await runner.run("test prompt")


@pytest.mark.asyncio
async def test_runner_context_size_exceeded():
    """Test that ContextSizeLimitExceeded is re-raised."""
    exc = ContextSizeLimitExceeded(model_name="gpt-4", max_tokens=8000)
    mock_manager = create_mock_agent_manager(exc)
    runner = AgentRunner(mock_manager)

    with pytest.raises(ContextSizeLimitExceeded) as exc_info:
        await runner.run("test prompt")

    assert exc_info.value.model_name == "gpt-4"
    assert exc_info.value.max_tokens == 8000


@pytest.mark.asyncio
async def test_runner_budget_exceeded():
    """Test that budget exceeded error is wrapped in BudgetExceededException."""

    class MockAPIStatusError(Exception):
        def __init__(self, message: str):
            self.message = message
            super().__init__(message)

        def __str__(self) -> str:
            return self.message

    MockAPIStatusError.__name__ = "APIStatusError"

    exc = MockAPIStatusError("Your budget has been exceeded")

    # Create mock manager with Shotgun Account
    mock_manager = create_mock_agent_manager(exc)
    mock_manager.deps.llm_model.is_shotgun_account = True

    runner = AgentRunner(mock_manager)

    with pytest.raises(BudgetExceededException):
        await runner.run("test prompt")


@pytest.mark.asyncio
async def test_runner_generic_exception():
    """Test that generic exceptions are wrapped in UnknownAgentException."""
    exc = ValueError("Something went wrong")
    mock_manager = create_mock_agent_manager(exc)
    runner = AgentRunner(mock_manager)

    with pytest.raises(UnknownAgentException) as exc_info:
        await runner.run("test prompt")

    assert exc_info.value.original_exception == exc


@pytest.mark.asyncio
async def test_runner_error_context_includes_agent_info():
    """Test that error context includes agent type and model info."""
    exc = ValueError("Test error")
    mock_manager = create_mock_agent_manager(exc)
    mock_manager._current_agent_type = AgentType.TASKS
    mock_manager.deps.llm_model.name = "claude-3-opus"

    runner = AgentRunner(mock_manager)

    with pytest.raises(UnknownAgentException):
        await runner.run("test prompt")
