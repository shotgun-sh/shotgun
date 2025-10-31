"""Test agent creation functions."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai import Agent
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.messages import ModelMessage

from shotgun.agents.models import AgentDeps, AgentRuntimeOptions
from shotgun.agents.plan import create_plan_agent, run_plan_agent
from shotgun.agents.research import create_research_agent, run_research_agent
from shotgun.agents.specify import create_specify_agent, run_specify_agent
from shotgun.agents.tasks import create_tasks_agent, run_tasks_agent


@pytest.fixture
def mock_agent_runtime_options():
    """Create mock AgentRuntimeOptions for testing."""
    return AgentRuntimeOptions(interactive_mode=True, output_file="test_output.md")


@pytest.fixture
def mock_agent_deps():
    """Create mock AgentDeps for testing."""
    deps = MagicMock(spec=AgentDeps)
    deps.interactive_mode = True
    deps.output_file = "test_output.md"
    deps.codebase_service = MagicMock()
    deps.llm_model = MagicMock()
    deps.system_prompt_fn = MagicMock()
    return deps


@patch("shotgun.agents.plan.create_base_agent")
def test_create_plan_agent(mock_create_base, mock_agent_runtime_options):
    """Test create_plan_agent function."""
    mock_agent = MagicMock(spec=Agent)
    mock_deps = MagicMock(spec=AgentDeps)
    mock_create_base.return_value = (mock_agent, mock_deps)

    agent, deps = create_plan_agent(mock_agent_runtime_options)

    assert agent == mock_agent
    assert deps == mock_deps

    # Verify create_base_agent was called with correct parameters
    mock_create_base.assert_called_once()
    call_args = mock_create_base.call_args

    # Check that system_prompt_fn is a partial function for "plan"
    system_prompt_fn = call_args[0][0]
    assert callable(system_prompt_fn)

    # Check other arguments
    assert call_args[0][1] == mock_agent_runtime_options  # agent_runtime_options
    assert call_args[1]["load_codebase_understanding_tools"] is False
    assert call_args[1]["load_codebase_agent_tool"] is True
    assert call_args[1]["additional_tools"] is None
    assert call_args[1]["provider"] is None


@patch("shotgun.agents.plan.create_base_agent")
def test_create_plan_agent_with_provider(mock_create_base, mock_agent_runtime_options):
    """Test create_plan_agent function with custom provider."""
    mock_agent = MagicMock(spec=Agent)
    mock_deps = MagicMock(spec=AgentDeps)
    mock_create_base.return_value = (mock_agent, mock_deps)

    agent, deps = create_plan_agent(mock_agent_runtime_options, provider="anthropic")

    # Verify provider was passed through
    call_kwargs = mock_create_base.call_args[1]
    assert call_kwargs["provider"] == "anthropic"


@patch("shotgun.agents.tasks.create_base_agent")
def test_create_tasks_agent(mock_create_base, mock_agent_runtime_options):
    """Test create_tasks_agent function."""
    mock_agent = MagicMock(spec=Agent)
    mock_deps = MagicMock(spec=AgentDeps)
    mock_create_base.return_value = (mock_agent, mock_deps)

    agent, deps = create_tasks_agent(mock_agent_runtime_options)

    assert agent == mock_agent
    assert deps == mock_deps

    # Verify create_base_agent was called with correct parameters
    mock_create_base.assert_called_once()
    call_args = mock_create_base.call_args

    # Check that system_prompt_fn is a partial function for "tasks"
    system_prompt_fn = call_args[0][0]
    assert callable(system_prompt_fn)

    # Check other arguments
    assert call_args[0][1] == mock_agent_runtime_options
    # tasks agent uses default parameters for create_base_agent


@patch("shotgun.agents.tasks.create_base_agent")
def test_create_tasks_agent_with_provider(mock_create_base, mock_agent_runtime_options):
    """Test create_tasks_agent function with custom provider."""
    mock_agent = MagicMock(spec=Agent)
    mock_deps = MagicMock(spec=AgentDeps)
    mock_create_base.return_value = (mock_agent, mock_deps)

    agent, deps = create_tasks_agent(mock_agent_runtime_options, provider="openai")

    # Verify provider was passed through
    call_kwargs = mock_create_base.call_args[1]
    assert call_kwargs["provider"] == "openai"


@patch("shotgun.agents.specify.create_base_agent")
def test_create_specify_agent(mock_create_base, mock_agent_runtime_options):
    """Test create_specify_agent function."""
    mock_agent = MagicMock(spec=Agent)
    mock_deps = MagicMock(spec=AgentDeps)
    mock_create_base.return_value = (mock_agent, mock_deps)

    agent, deps = create_specify_agent(mock_agent_runtime_options)

    assert agent == mock_agent
    assert deps == mock_deps

    # Verify create_base_agent was called with correct parameters
    mock_create_base.assert_called_once()
    call_args = mock_create_base.call_args

    # Check that system_prompt_fn is a partial function for "specify"
    system_prompt_fn = call_args[0][0]
    assert callable(system_prompt_fn)

    # Check other arguments
    assert call_args[0][1] == mock_agent_runtime_options
    assert call_args[1]["load_codebase_understanding_tools"] is False
    assert call_args[1]["load_codebase_agent_tool"] is True
    assert call_args[1]["additional_tools"] is None
    assert call_args[1]["provider"] is None


@patch("shotgun.agents.specify.create_base_agent")
def test_create_specify_agent_with_provider(
    mock_create_base, mock_agent_runtime_options
):
    """Test create_specify_agent function with custom provider."""
    mock_agent = MagicMock(spec=Agent)
    mock_deps = MagicMock(spec=AgentDeps)
    mock_create_base.return_value = (mock_agent, mock_deps)

    agent, deps = create_specify_agent(mock_agent_runtime_options, provider="gemini")

    # Verify provider was passed through
    call_kwargs = mock_create_base.call_args[1]
    assert call_kwargs["provider"] == "gemini"


@patch("shotgun.agents.research.get_available_web_search_tools")
@patch("shotgun.agents.research.create_base_agent")
def test_create_research_agent(
    mock_create_base, mock_get_tools, mock_agent_runtime_options
):
    """Test create_research_agent function."""
    mock_agent = MagicMock(spec=Agent)
    mock_deps = MagicMock(spec=AgentDeps)
    mock_create_base.return_value = (mock_agent, mock_deps)

    # Mock web search tools
    mock_tools = [MagicMock(), MagicMock()]
    mock_get_tools.return_value = mock_tools

    agent, deps = create_research_agent(mock_agent_runtime_options)

    assert agent == mock_agent
    assert deps == mock_deps

    # Verify web search tools were retrieved
    mock_get_tools.assert_called_once()

    # Verify create_base_agent was called with correct parameters
    mock_create_base.assert_called_once()
    call_args = mock_create_base.call_args

    # Check that system_prompt_fn is a partial function for "research"
    system_prompt_fn = call_args[0][0]
    assert callable(system_prompt_fn)

    # Check other arguments
    assert call_args[0][1] == mock_agent_runtime_options
    assert call_args[1]["load_codebase_understanding_tools"] is False
    assert call_args[1]["load_codebase_agent_tool"] is True
    assert call_args[1]["additional_tools"] == mock_tools
    assert call_args[1]["provider"] is None


@patch("shotgun.agents.research.get_available_web_search_tools")
@patch("shotgun.agents.research.create_base_agent")
def test_create_research_agent_no_web_tools(
    mock_create_base, mock_get_tools, mock_agent_runtime_options
):
    """Test create_research_agent function when no web search tools are available."""
    mock_agent = MagicMock(spec=Agent)
    mock_deps = MagicMock(spec=AgentDeps)
    mock_create_base.return_value = (mock_agent, mock_deps)

    # Mock no web search tools available
    mock_get_tools.return_value = []

    agent, deps = create_research_agent(mock_agent_runtime_options)

    # Should still create agent successfully
    assert agent == mock_agent
    assert deps == mock_deps

    # Verify additional_tools is empty list
    call_args = mock_create_base.call_args
    assert call_args[1]["additional_tools"] == []


def test_system_prompt_functions_are_callable():
    """Test that all system prompt functions created by partials are callable."""
    from functools import partial

    from shotgun.agents.common import build_agent_system_prompt

    # Test that partial functions work correctly
    research_fn = partial(build_agent_system_prompt, "research")
    plan_fn = partial(build_agent_system_prompt, "plan")
    tasks_fn = partial(build_agent_system_prompt, "tasks")
    specify_fn = partial(build_agent_system_prompt, "specify")

    # All should be callable
    assert callable(research_fn)
    assert callable(plan_fn)
    assert callable(tasks_fn)
    assert callable(specify_fn)

    # Test that they have the expected func attribute
    assert research_fn.func == build_agent_system_prompt
    assert plan_fn.func == build_agent_system_prompt
    assert tasks_fn.func == build_agent_system_prompt
    assert specify_fn.func == build_agent_system_prompt


# Test run_*_agent functions


@pytest.mark.asyncio
@patch("shotgun.agents.plan.add_system_status_message")
@patch("shotgun.agents.plan.create_usage_limits")
@patch("shotgun.agents.plan.run_agent")
async def test_run_plan_agent(
    mock_run_agent, mock_usage_limits, mock_add_status, mock_agent_deps
):
    """Test run_plan_agent function."""
    mock_agent = MagicMock(spec=Agent)
    mock_result = MagicMock(spec=AgentRunResult)
    mock_run_agent.return_value = mock_result

    mock_usage_limits.return_value = MagicMock()
    mock_add_status.return_value = []

    result = await run_plan_agent(mock_agent, "test goal", mock_agent_deps)

    assert result == mock_result
    mock_add_status.assert_called_once_with(mock_agent_deps, None)
    mock_usage_limits.assert_called_once()
    mock_run_agent.assert_called_once()

    # Check the call to run_agent
    call_kwargs = mock_run_agent.call_args[1]
    assert call_kwargs["agent"] == mock_agent
    assert call_kwargs["prompt"] == "Create a comprehensive plan for: test goal"
    assert call_kwargs["deps"] == mock_agent_deps


@pytest.mark.asyncio
@patch("shotgun.agents.plan.add_system_status_message")
@patch("shotgun.agents.plan.create_usage_limits")
@patch("shotgun.agents.plan.run_agent")
async def test_run_plan_agent_with_message_history(
    mock_run_agent, mock_usage_limits, mock_add_status, mock_agent_deps
):
    """Test run_plan_agent function with message history."""
    mock_agent = MagicMock(spec=Agent)
    mock_result = MagicMock(spec=AgentRunResult)
    mock_run_agent.return_value = mock_result

    mock_usage_limits.return_value = MagicMock()
    mock_add_status.return_value = []

    message_history = [MagicMock(spec=ModelMessage)]

    result = await run_plan_agent(
        mock_agent, "test goal", mock_agent_deps, message_history
    )

    assert result == mock_result
    mock_add_status.assert_called_once_with(mock_agent_deps, message_history)


@pytest.mark.asyncio
@patch("shotgun.agents.specify.add_system_status_message")
@patch("shotgun.agents.specify.create_usage_limits")
@patch("shotgun.agents.specify.run_agent")
async def test_run_specify_agent(
    mock_run_agent, mock_usage_limits, mock_add_status, mock_agent_deps
):
    """Test run_specify_agent function."""
    mock_agent = MagicMock(spec=Agent)
    mock_result = MagicMock(spec=AgentRunResult)
    mock_run_agent.return_value = mock_result

    mock_usage_limits.return_value = MagicMock()
    mock_add_status.return_value = []

    result = await run_specify_agent(mock_agent, "test requirement", mock_agent_deps)

    assert result == mock_result
    mock_add_status.assert_called_once_with(mock_agent_deps, None)
    mock_usage_limits.assert_called_once()
    mock_run_agent.assert_called_once()

    # Check the call to run_agent
    call_kwargs = mock_run_agent.call_args[1]
    assert call_kwargs["agent"] == mock_agent
    assert (
        call_kwargs["prompt"]
        == "Create a comprehensive specification for: test requirement"
    )
    assert call_kwargs["deps"] == mock_agent_deps


@pytest.mark.asyncio
@patch("shotgun.agents.tasks.add_system_status_message")
@patch("shotgun.agents.tasks.create_usage_limits")
@patch("shotgun.agents.tasks.run_agent")
async def test_run_tasks_agent(
    mock_run_agent, mock_usage_limits, mock_add_status, mock_agent_deps
):
    """Test run_tasks_agent function."""
    mock_agent = MagicMock(spec=Agent)
    mock_result = MagicMock(spec=AgentRunResult)
    mock_run_agent.return_value = mock_result

    mock_usage_limits.return_value = MagicMock()
    mock_add_status.return_value = []

    result = await run_tasks_agent(mock_agent, "test instruction", mock_agent_deps)

    assert result == mock_result
    mock_add_status.assert_called_once_with(mock_agent_deps, None)
    mock_usage_limits.assert_called_once()
    mock_run_agent.assert_called_once()

    # Check the call to run_agent
    call_kwargs = mock_run_agent.call_args[1]
    assert call_kwargs["agent"] == mock_agent
    assert call_kwargs["prompt"] == "Create or update tasks based on: test instruction"
    assert call_kwargs["deps"] == mock_agent_deps


@pytest.mark.asyncio
@patch("shotgun.agents.research.add_system_status_message")
@patch("shotgun.agents.research.create_usage_limits")
@patch("shotgun.agents.research.run_agent")
async def test_run_research_agent(
    mock_run_agent, mock_usage_limits, mock_add_status, mock_agent_deps
):
    """Test run_research_agent function."""
    mock_agent = MagicMock(spec=Agent)
    mock_result = MagicMock(spec=AgentRunResult)
    mock_run_agent.return_value = mock_result

    mock_usage_limits.return_value = MagicMock()
    mock_add_status.return_value = []

    result = await run_research_agent(mock_agent, "test query", mock_agent_deps)

    assert result == mock_result
    mock_add_status.assert_called_once_with(mock_agent_deps, None)
    mock_usage_limits.assert_called_once()
    mock_run_agent.assert_called_once()

    # Check the call to run_agent
    call_kwargs = mock_run_agent.call_args[1]
    assert call_kwargs["agent"] == mock_agent
    assert call_kwargs["prompt"] == "test query"
    assert call_kwargs["deps"] == mock_agent_deps


@pytest.mark.asyncio
@patch("shotgun.agents.plan.create_usage_limits")
@patch("shotgun.agents.plan.add_system_status_message")
@patch("shotgun.agents.plan.run_agent")
async def test_run_plan_agent_exception_handling(
    mock_run_agent, mock_add_status, mock_usage_limits, mock_agent_deps
):
    """Test run_plan_agent exception handling."""
    mock_agent = MagicMock(spec=Agent)
    mock_usage_limits.return_value = MagicMock()
    mock_add_status.return_value = []
    mock_run_agent.side_effect = Exception("Test error")

    with pytest.raises(Exception, match="Test error"):
        await run_plan_agent(mock_agent, "test goal", mock_agent_deps)
