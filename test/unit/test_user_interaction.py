"""Unit tests for agents.tools.user_interaction module."""

import asyncio
from asyncio import Queue
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic_ai import CallDeferred

from shotgun.agents.models import AgentDeps, ModelConfig, UserAnswer, UserQuestion
from shotgun.agents.tools.user_interaction import ask_user


@pytest.fixture
def mock_deps():
    """Create mock dependencies for testing."""
    deps = Mock(spec=AgentDeps)
    deps.queue = AsyncMock(spec=Queue)
    deps.tasks = []
    deps.llm_model = Mock(spec=ModelConfig)
    return deps


@pytest.fixture
def mock_context(mock_deps):
    """Create mock RunContext for testing."""
    ctx = Mock()
    ctx.deps = mock_deps
    ctx.tool_call_id = "test-tool-call-123"
    return ctx


@pytest.mark.asyncio
async def test_ask_user_creates_question_and_defers(mock_context):
    """Test that ask_user creates a UserQuestion and raises CallDeferred."""
    question = "Do you want to proceed?"

    with pytest.raises(CallDeferred) as exc_info:
        await ask_user(mock_context, question)

    # Verify CallDeferred was raised with the question
    assert str(exc_info.value) == question

    # Verify queue.put was called with correct UserQuestion
    mock_context.deps.queue.put.assert_called_once()
    call_args = mock_context.deps.queue.put.call_args[0][0]

    assert isinstance(call_args, UserQuestion)
    assert call_args.question == question
    assert call_args.tool_call_id == "test-tool-call-123"
    assert isinstance(call_args.result, asyncio.Future)

    # Verify future was added to tasks
    assert len(mock_context.deps.tasks) == 1
    assert mock_context.deps.tasks[0] == call_args.result


@pytest.mark.asyncio
async def test_ask_user_handles_different_questions(mock_context):
    """Test ask_user with various question types."""
    questions = [
        "Yes or no?",
        "Enter a number:",
        "What's your name?",
        "🤔 Unicode question?",
        "",
        "Multi\nline\nquestion?",
    ]

    for question in questions:
        mock_context.deps.tasks.clear()
        mock_context.deps.queue.put.reset_mock()

        with pytest.raises(CallDeferred) as exc_info:
            await ask_user(mock_context, question)

        assert str(exc_info.value) == question
        mock_context.deps.queue.put.assert_called_once()


@pytest.mark.asyncio
async def test_ask_user_with_none_tool_call_id():
    """Test that ask_user raises AssertionError when tool_call_id is None."""
    ctx = Mock()
    ctx.tool_call_id = None
    ctx.deps = Mock(spec=AgentDeps)
    ctx.deps.queue = AsyncMock(spec=Queue)
    ctx.deps.tasks = []

    with pytest.raises(AssertionError):
        await ask_user(ctx, "Test question")


@pytest.mark.asyncio
async def test_ask_user_handles_eof_error(mock_context):
    """Test handling of EOFError during execution."""
    mock_context.deps.queue.put.side_effect = EOFError("End of file")

    result = await ask_user(mock_context, "Test question")

    assert result == "User input not available or interrupted"
    mock_context.deps.queue.put.assert_called_once()


@pytest.mark.asyncio
async def test_ask_user_handles_keyboard_interrupt(mock_context):
    """Test handling of KeyboardInterrupt during execution."""
    mock_context.deps.queue.put.side_effect = KeyboardInterrupt("Interrupted")

    result = await ask_user(mock_context, "Test question")

    assert result == "User input not available or interrupted"
    mock_context.deps.queue.put.assert_called_once()


@pytest.mark.asyncio
async def test_ask_user_logging(mock_context):
    """Test that questions are logged properly."""
    question = "What is your favorite color?"

    with patch("shotgun.agents.tools.user_interaction.logger") as mock_logger:
        with pytest.raises(CallDeferred):
            await ask_user(mock_context, question)

        mock_logger.debug.assert_called_once_with("\n👉 %s\n", question)


@pytest.mark.asyncio
async def test_ask_user_exception_logging(mock_context):
    """Test that exceptions are logged properly."""
    mock_context.deps.queue.put.side_effect = EOFError("Test EOF")

    with patch("shotgun.agents.tools.user_interaction.logger") as mock_logger:
        result = await ask_user(mock_context, "Test question")

        assert result == "User input not available or interrupted"
        mock_logger.warning.assert_called_once_with(
            "User input interrupted or unavailable"
        )


@pytest.mark.asyncio
async def test_future_creation_and_tracking(mock_context):
    """Test that futures are properly created and tracked."""
    questions = ["Q1", "Q2", "Q3"]
    futures = []

    for question in questions:
        try:
            await ask_user(mock_context, question)
        except CallDeferred:
            pass

        # Get the future from the last call
        call_args = mock_context.deps.queue.put.call_args[0][0]
        futures.append(call_args.result)

    # Verify all futures are tracked
    assert len(mock_context.deps.tasks) == 3
    for future in futures:
        assert isinstance(future, asyncio.Future)
        assert future in mock_context.deps.tasks


@pytest.mark.asyncio
async def test_unique_tool_call_ids(mock_context):
    """Test that different tool_call_ids are preserved correctly."""
    tool_call_ids = ["id-1", "id-2", "id-3"]

    for tool_id in tool_call_ids:
        mock_context.tool_call_id = tool_id
        mock_context.deps.queue.put.reset_mock()

        with pytest.raises(CallDeferred):
            await ask_user(mock_context, "Question")

        call_args = mock_context.deps.queue.put.call_args[0][0]
        assert call_args.tool_call_id == tool_id


@pytest.mark.asyncio
async def test_integration_with_real_queue():
    """Test integration with actual Queue and Future objects."""
    # Create real dependencies
    deps = Mock(spec=AgentDeps)
    deps.queue = Queue()
    deps.tasks = []

    ctx = Mock()
    ctx.deps = deps
    ctx.tool_call_id = "real-test-id"

    question = "Real question?"

    # Call ask_user
    with pytest.raises(CallDeferred):
        await ask_user(ctx, question)

    # Verify question was queued
    assert not deps.queue.empty()
    user_question = await deps.queue.get()

    assert isinstance(user_question, UserQuestion)
    assert user_question.question == question
    assert user_question.tool_call_id == "real-test-id"

    # Simulate user answering
    answer = UserAnswer(answer="User response", tool_call_id="real-test-id")
    user_question.result.set_result(answer)

    # Verify future resolves correctly
    resolved_answer = await user_question.result
    assert resolved_answer == answer
    assert resolved_answer.answer == "User response"


@pytest.mark.asyncio
async def test_concurrent_questions():
    """Test handling multiple concurrent questions."""
    deps = Mock(spec=AgentDeps)
    deps.queue = Queue()
    deps.tasks = []

    contexts = []
    questions = ["Q1", "Q2", "Q3"]

    for i, question in enumerate(questions):
        ctx = Mock()
        ctx.deps = deps
        ctx.tool_call_id = f"id-{i}"
        contexts.append(ctx)

        with pytest.raises(CallDeferred):
            await ask_user(ctx, question)

    # Verify all questions are queued
    assert deps.queue.qsize() == 3

    # Process all questions
    for i in range(3):
        user_question = await deps.queue.get()
        assert user_question.question == questions[i]
        assert user_question.tool_call_id == f"id-{i}"


@pytest.mark.asyncio
async def test_queue_put_failure_scenarios():
    """Test various queue.put failure scenarios."""
    scenarios = [
        (EOFError, "EOF during queue operation"),
        (KeyboardInterrupt, "Interrupted during queue operation"),
        (RuntimeError, "Queue runtime error"),
        (asyncio.CancelledError, "Task cancelled"),
    ]

    for exception_type, message in scenarios[
        :2
    ]:  # Only test EOFError and KeyboardInterrupt
        deps = Mock(spec=AgentDeps)
        deps.queue = AsyncMock(spec=Queue)
        deps.queue.put.side_effect = exception_type(message)
        deps.tasks = []

        ctx = Mock()
        ctx.deps = deps
        ctx.tool_call_id = "error-test"

        result = await ask_user(ctx, "Will fail")
        assert result == "User input not available or interrupted"


@pytest.mark.asyncio
async def test_special_characters_in_questions():
    """Test questions with special characters are handled correctly."""
    special_questions = [
        "Hello! @#$%^&*()",
        "émojis 🚀 and unicode ñ",
        "line with\ttabs",
        "\"quotes\" and 'apostrophes'",
        "<html>tags</html>",
        "path/to/file.txt",
        "email@example.com",
    ]

    deps = Mock(spec=AgentDeps)
    deps.queue = Queue()
    deps.tasks = []

    for question in special_questions:
        ctx = Mock()
        ctx.deps = deps
        ctx.tool_call_id = "special-test"

        with pytest.raises(CallDeferred) as exc_info:
            await ask_user(ctx, question)

        assert str(exc_info.value) == question

        # Verify question is queued correctly
        user_question = await deps.queue.get()
        assert user_question.question == question
