"""Integration tests for AgentRunner."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from shotgun.agents.error_classifier import ErrorType
from shotgun.agents.error_messages import ErrorMessage
from shotgun.agents.models import AgentType
from shotgun.agents.runner import AgentRunner
from shotgun.exceptions import ContextSizeLimitExceeded


class MockErrorHandler:
    """Mock error handler for testing."""

    def __init__(self):
        self.cancellation_called = False
        self.error_called = False
        self.success_called = False
        self.last_error_type = None
        self.last_error_message = None

    def handle_cancellation(self) -> None:
        """Track cancellation calls."""
        self.cancellation_called = True

    def handle_error(self, error_type: ErrorType, error_message: ErrorMessage) -> None:
        """Track error calls."""
        self.error_called = True
        self.last_error_type = error_type
        self.last_error_message = error_message

    def handle_success(self) -> None:
        """Track success calls."""
        self.success_called = True


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
    mock_manager.agent_type = AgentType.RESEARCH

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
    error_handler = MockErrorHandler()
    runner = AgentRunner(mock_manager, error_handler)

    result = await runner.run("test prompt", use_markdown=True)

    assert result is True
    assert error_handler.success_called
    assert not error_handler.error_called
    assert not error_handler.cancellation_called
    mock_manager.run.assert_called_once_with(prompt="test prompt")


@pytest.mark.asyncio
async def test_runner_cancelled_error():
    """Test handling of CancelledError."""
    mock_manager = create_mock_agent_manager(asyncio.CancelledError())
    error_handler = MockErrorHandler()
    runner = AgentRunner(mock_manager, error_handler)

    result = await runner.run("test prompt", use_markdown=True)

    assert result is False
    assert error_handler.cancellation_called
    assert not error_handler.error_called
    assert not error_handler.success_called


@pytest.mark.asyncio
async def test_runner_context_size_exceeded():
    """Test handling of ContextSizeLimitExceeded."""
    exc = ContextSizeLimitExceeded(model_name="gpt-4", max_tokens=8000)
    mock_manager = create_mock_agent_manager(exc)
    error_handler = MockErrorHandler()
    runner = AgentRunner(mock_manager, error_handler)

    result = await runner.run("test prompt", use_markdown=True)

    assert result is False
    assert error_handler.error_called
    assert error_handler.last_error_type == ErrorType.CONTEXT_SIZE_EXCEEDED
    assert "Context too large" in error_handler.last_error_message.message
    assert not error_handler.success_called


@pytest.mark.asyncio
async def test_runner_generic_exception():
    """Test handling of generic exceptions."""
    exc = ValueError("Something went wrong")
    mock_manager = create_mock_agent_manager(exc)
    error_handler = MockErrorHandler()
    runner = AgentRunner(mock_manager, error_handler)

    result = await runner.run("test prompt", use_markdown=True)

    assert result is False
    assert error_handler.error_called
    assert error_handler.last_error_type == ErrorType.UNKNOWN
    assert "Something went wrong" in error_handler.last_error_message.message
    assert not error_handler.success_called


@pytest.mark.asyncio
async def test_runner_budget_exceeded():
    """Test handling of budget exceeded error."""

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

    error_handler = MockErrorHandler()
    runner = AgentRunner(mock_manager, error_handler)

    result = await runner.run("test prompt", use_markdown=True)

    assert result is False
    assert error_handler.error_called
    assert error_handler.last_error_type == ErrorType.BUDGET_EXCEEDED
    assert "budget" in error_handler.last_error_message.message.lower()


@pytest.mark.asyncio
async def test_runner_use_markdown_false():
    """Test that use_markdown parameter is respected."""
    exc = ValueError("Test error")
    mock_manager = create_mock_agent_manager(exc)
    error_handler = MockErrorHandler()
    runner = AgentRunner(mock_manager, error_handler)

    result = await runner.run("test prompt", use_markdown=False)

    assert result is False
    assert error_handler.error_called
    # Plain text should not have markdown formatting like backticks
    assert "**" not in error_handler.last_error_message.message


@pytest.mark.asyncio
async def test_runner_protocol_compliance():
    """Test that runner works with any AgentErrorHandler protocol implementation."""

    class CustomHandler:
        """Custom handler implementing the protocol."""

        def __init__(self):
            self.handled = []

        def handle_cancellation(self) -> None:
            self.handled.append("cancellation")

        def handle_error(
            self, error_type: ErrorType, error_message: ErrorMessage
        ) -> None:
            self.handled.append(("error", error_type))

        def handle_success(self) -> None:
            self.handled.append("success")

    mock_manager = create_mock_agent_manager()
    custom_handler = CustomHandler()
    runner = AgentRunner(mock_manager, custom_handler)

    result = await runner.run("test prompt")

    assert result is True
    assert "success" in custom_handler.handled


@pytest.mark.asyncio
async def test_runner_multiple_runs():
    """Test that runner can be reused for multiple runs."""
    mock_manager = create_mock_agent_manager()
    error_handler = MockErrorHandler()
    runner = AgentRunner(mock_manager, error_handler)

    # First run - success
    result1 = await runner.run("prompt 1")
    assert result1 is True

    # Second run - success
    result2 = await runner.run("prompt 2")
    assert result2 is True

    assert mock_manager.run.call_count == 2
    assert error_handler.success_called


@pytest.mark.asyncio
async def test_runner_error_context_includes_agent_info():
    """Test that error context includes agent type and model info."""
    exc = ValueError("Test error")
    mock_manager = create_mock_agent_manager(exc)
    mock_manager.agent_type = AgentType.TASKS
    mock_manager.deps.llm_model.name = "claude-3-opus"

    error_handler = MockErrorHandler()
    runner = AgentRunner(mock_manager, error_handler)

    result = await runner.run("test prompt")

    assert result is False
    assert error_handler.error_called
    # Error message should be generated with correct context
    assert error_handler.last_error_message is not None
