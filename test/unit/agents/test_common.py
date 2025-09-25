"""Test common agent functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import DeferredToolRequests
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.messages import ModelRequest, ModelResponse, SystemPromptPart, TextPart

from shotgun.agents.common import (
    add_system_prompt_message,
    add_system_status_message,
    build_agent_system_prompt,
    run_agent,
)
from shotgun.agents.models import AgentDeps, AgentRuntimeOptions


@pytest.fixture
def mock_agent_runtime_options():
    """Create mock AgentRuntimeOptions for testing."""
    return AgentRuntimeOptions(interactive_mode=True, output_file="test_output.md")


@pytest.fixture
def mock_deps():
    """Create mock AgentDeps for testing."""
    deps = MagicMock(spec=AgentDeps)
    deps.interactive_mode = True
    deps.codebase_service = AsyncMock()
    deps.codebase_service.list_graphs.return_value = ["graph1", "graph2"]
    deps.system_prompt_fn = MagicMock(return_value="Test system prompt content")
    deps.queue = AsyncMock()
    deps.tasks = []
    deps.is_tui_context = False
    deps.agent_mode = None  # Add agent_mode attribute
    # Add file_tracker mock
    file_tracker_mock = MagicMock()
    file_tracker_mock.clear = MagicMock()
    file_tracker_mock.operations = []
    file_tracker_mock.format_summary = MagicMock(return_value="No files modified")
    deps.file_tracker = file_tracker_mock
    return deps


@pytest.fixture
def mock_agent():
    """Create mock agent for testing."""
    agent = MagicMock()
    agent.run = AsyncMock()
    return agent


@pytest.mark.asyncio
async def test_add_system_status_message_empty_history(mock_deps):
    """Test add_system_status_message with empty message history."""
    with patch("shotgun.agents.common.prompt_loader") as mock_loader:
        with patch("shotgun.agents.common.get_agent_existing_files") as mock_get_files:
            with patch(
                "shotgun.agents.common.extract_markdown_toc"
            ) as mock_extract_toc:
                mock_loader.render.return_value = "System state content"
                mock_get_files.return_value = []
                mock_extract_toc.return_value = None

                result = await add_system_status_message(mock_deps)

                assert len(result) == 1
                assert isinstance(result[0], ModelRequest)
                assert len(result[0].parts) == 1
                assert isinstance(result[0].parts[0], SystemPromptPart)
                assert result[0].parts[0].content == "System state content"

                mock_get_files.assert_called_once_with(None)
                mock_extract_toc.assert_called_once_with(None)
                mock_loader.render.assert_called_once_with(
                    "agents/state/system_state.j2",
                    codebase_understanding_graphs=["graph1", "graph2"],
                    is_tui_context=False,
                    existing_files=[],
                    markdown_toc=None,
                )


@pytest.mark.asyncio
async def test_add_system_status_message_existing_history(mock_deps):
    """Test add_system_status_message with existing message history."""
    existing_message = ModelRequest(parts=[TextPart(content="Existing message")])
    existing_history = [existing_message]

    with patch("shotgun.agents.common.prompt_loader") as mock_loader:
        with patch("shotgun.agents.common.get_agent_existing_files") as mock_get_files:
            with patch(
                "shotgun.agents.common.extract_markdown_toc"
            ) as mock_extract_toc:
                mock_loader.render.return_value = "System state content"
                mock_get_files.return_value = []
                mock_extract_toc.return_value = None

                result = await add_system_status_message(mock_deps, existing_history)

                assert len(result) == 2
                assert result[0] == existing_message  # Original message preserved
                assert isinstance(result[1], ModelRequest)


@pytest.mark.asyncio
async def test_add_system_prompt_message_empty_history(mock_deps):
    """Test add_system_prompt_message with empty message history."""
    result = await add_system_prompt_message(mock_deps)

    assert len(result) == 1
    assert isinstance(result[0], ModelRequest)
    assert len(result[0].parts) == 1
    assert isinstance(result[0].parts[0], SystemPromptPart)
    assert result[0].parts[0].content == "Test system prompt content"

    # Verify system_prompt_fn was called with a mock RunContext
    mock_deps.system_prompt_fn.assert_called_once()
    call_args = mock_deps.system_prompt_fn.call_args[0][0]
    assert hasattr(call_args, "deps")
    assert call_args.deps == mock_deps


@pytest.mark.asyncio
async def test_add_system_prompt_message_existing_history(mock_deps):
    """Test add_system_prompt_message with existing message history."""
    existing_message = ModelResponse(parts=[TextPart(content="Existing message")])
    existing_history = [existing_message]

    result = await add_system_prompt_message(mock_deps, existing_history)

    assert len(result) == 2
    assert isinstance(result[0], ModelRequest)  # System prompt inserted first
    assert isinstance(result[0].parts[0], SystemPromptPart)
    assert result[1] == existing_message  # Original message preserved


@pytest.mark.asyncio
async def test_run_agent_simple_string_output(mock_agent, mock_deps):
    """Test run_agent with simple string output (no deferred tools)."""
    mock_run_result = MagicMock(spec=AgentRunResult)
    mock_run_result.output = "Simple response"
    mock_run_result.all_messages.return_value = []
    mock_agent.run.return_value = mock_run_result

    result = await run_agent(mock_agent, "Test prompt", mock_deps)

    assert result == mock_run_result
    assert mock_agent.run.call_count == 1

    # Verify system prompt was added to message history
    call_kwargs = mock_agent.run.call_args.kwargs
    assert "message_history" in call_kwargs
    assert len(call_kwargs["message_history"]) == 1
    assert isinstance(call_kwargs["message_history"][0], ModelRequest)


@pytest.mark.asyncio
async def test_run_agent_with_deferred_tool_requests(mock_agent, mock_deps):
    """Test run_agent with deferred tool requests."""
    # Mock the first run result with deferred tool requests
    mock_deferred_requests = MagicMock(spec=DeferredToolRequests)
    mock_deferred_requests.calls = [MagicMock(tool_call_id="test_call_id")]

    mock_first_result = MagicMock(spec=AgentRunResult)
    mock_first_result.output = mock_deferred_requests
    mock_first_result.all_messages.return_value = [
        ModelRequest(parts=[TextPart(content="First message")])
    ]

    # Mock the final run result
    mock_final_result = MagicMock(spec=AgentRunResult)
    mock_final_result.output = "Final response"
    mock_final_result.all_messages.return_value = [
        ModelRequest(parts=[TextPart(content="First message")]),
        ModelResponse(parts=[TextPart(content="Final response")]),
    ]

    # Set up the agent to return different results on each call
    mock_agent.run.side_effect = [mock_first_result, mock_final_result]

    # Mock task completion
    mock_task = MagicMock()
    mock_task_result = MagicMock()
    mock_task_result.tool_call_id = "test_call_id"
    mock_task_result.answer = "Tool result"
    mock_task.result.return_value = mock_task_result
    mock_deps.tasks = [mock_task]

    # Mock asyncio.wait to return our mock task as done
    with patch("asyncio.wait") as mock_wait:
        mock_wait.return_value = ([mock_task], [])

        result = await run_agent(mock_agent, "Test prompt", mock_deps)

        assert result == mock_final_result
        assert mock_agent.run.call_count == 2

        # Verify queue.join was called
        mock_deps.queue.join.assert_called_once()


def test_build_agent_system_prompt_research_agent():
    """Test build_agent_system_prompt for research agent type."""
    mock_context = MagicMock()
    mock_context.deps.interactive_mode = True

    with patch("shotgun.agents.common.PromptLoader") as mock_loader_class:
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.render.return_value = "Research system prompt"

        result = build_agent_system_prompt("research", mock_context)

        assert result == "Research system prompt"
        mock_loader.render.assert_called_once_with(
            "agents/research.j2",
            interactive_mode=True,
            mode="research",
        )


def test_build_agent_system_prompt_custom_context():
    """Test build_agent_system_prompt with custom context name."""
    mock_context = MagicMock()
    mock_context.deps.interactive_mode = False

    with patch("shotgun.agents.common.PromptLoader") as mock_loader_class:
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.render.return_value = "Custom context prompt"

        result = build_agent_system_prompt("plan", mock_context)

        assert result == "Custom context prompt"
        mock_loader.render.assert_called_once_with(
            "agents/plan.j2",
            interactive_mode=False,
            mode="plan",
        )


def test_build_agent_system_prompt_unknown_agent_type():
    """Test build_agent_system_prompt with unknown agent type."""
    mock_context = MagicMock()
    mock_context.deps.interactive_mode = True

    with patch("shotgun.agents.common.PromptLoader") as mock_loader_class:
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.render.return_value = "Unknown agent prompt"

        result = build_agent_system_prompt("unknown", mock_context)

        assert result == "Unknown agent prompt"
        mock_loader.render.assert_called_once_with(
            "agents/unknown.j2",
            interactive_mode=True,
            mode="unknown",
        )


def test_create_usage_limits():
    """Test create_usage_limits function."""
    from shotgun.agents.common import create_usage_limits

    limits = create_usage_limits()

    assert limits.request_limit == 100
    assert limits.tool_calls_limit == 100


@patch("shotgun.agents.common.get_provider_model")
def test_create_base_agent_provider_failure(
    mock_get_provider, mock_agent_runtime_options
):
    """Test create_base_agent when provider configuration fails."""
    from functools import partial

    from shotgun.agents.common import build_agent_system_prompt, create_base_agent

    # Mock provider configuration to raise exception
    mock_get_provider.side_effect = Exception("Provider config failed")

    system_prompt_fn = partial(build_agent_system_prompt, "research")

    with pytest.raises(ValueError, match="Configured model is required"):
        create_base_agent(system_prompt_fn, mock_agent_runtime_options)
