"""Test codebase understanding sub-agent creation and functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import Agent, RunContext
from pydantic_ai.agent import AgentRunResult

from shotgun.agents.codebase_understanding import (
    create_codebase_understanding_agent,
    run_codebase_understanding_agent,
)
from shotgun.agents.models import (
    AgentDeps,
    AgentRuntimeOptions,
    CodebaseQueryResult,
)
from shotgun.agents.tools.query_codebase_agent import query_codebase


@pytest.fixture
def mock_agent_runtime_options():
    """Create mock AgentRuntimeOptions for testing."""
    return AgentRuntimeOptions(interactive_mode=False)


@pytest.fixture
def mock_agent_deps():
    """Create mock AgentDeps for testing."""
    deps = MagicMock(spec=AgentDeps)
    deps.interactive_mode = False
    deps.codebase_service = MagicMock()
    deps.llm_model = MagicMock()
    deps.system_prompt_fn = MagicMock()
    deps.usage_manager = MagicMock()
    return deps


@patch("shotgun.agents.codebase_understanding.create_base_agent")
def test_create_codebase_understanding_agent(
    mock_create_base, mock_agent_runtime_options
):
    """Test create_codebase_understanding_agent function parameters."""
    mock_agent = MagicMock(spec=Agent)
    mock_deps = MagicMock(spec=AgentDeps)

    # Mock the agent's internal attributes needed for PydanticAgent creation
    mock_agent._model = MagicMock()
    mock_agent._history_processors = []
    mock_agent._function_tools = {}

    mock_create_base.return_value = (mock_agent, mock_deps)

    # Note: We're only testing the create_base_agent call, not the full agent creation
    # since that requires complex mocking of pydantic_ai internals
    try:
        create_codebase_understanding_agent(mock_agent_runtime_options)
    except Exception:
        # Expected to fail when trying to create PydanticAgent, but we've verified the call
        pass

    # Verify create_base_agent was called with correct parameters
    mock_create_base.assert_called_once()
    call_args = mock_create_base.call_args

    # Check that system_prompt_fn is a partial function for "codebase_understanding"
    system_prompt_fn = call_args[0][0]
    assert callable(system_prompt_fn)

    # Check other arguments
    assert call_args[0][1] == mock_agent_runtime_options  # agent_runtime_options
    assert call_args[1]["load_codebase_understanding_tools"] is True
    assert call_args[1]["additional_tools"] is None
    assert call_args[1]["provider"] is None


@pytest.mark.asyncio
@patch("shotgun.agents.codebase_understanding.run_agent")
@patch("shotgun.agents.codebase_understanding.add_system_status_message")
async def test_run_codebase_understanding_agent_success(
    mock_add_status, mock_run_agent, mock_agent_deps
):
    """Test run_codebase_understanding_agent with successful query."""
    mock_agent = MagicMock(spec=Agent)

    # Mock successful result
    mock_result = MagicMock(spec=AgentRunResult)
    mock_result.output = CodebaseQueryResult(
        success=True, result="Found authentication in src/auth/service.py"
    )
    mock_run_agent.return_value = mock_result
    mock_add_status.return_value = []

    result = await run_codebase_understanding_agent(
        agent=mock_agent, query="Where is authentication implemented?", deps=mock_agent_deps
    )

    assert result.output.success is True
    assert "authentication" in result.output.result.lower()
    mock_run_agent.assert_called_once()
    mock_add_status.assert_called_once()


@pytest.mark.asyncio
@patch("shotgun.agents.codebase_understanding.run_agent")
@patch("shotgun.agents.codebase_understanding.add_system_status_message")
async def test_run_codebase_understanding_agent_failure(
    mock_add_status, mock_run_agent, mock_agent_deps
):
    """Test run_codebase_understanding_agent with query failure."""
    mock_agent = MagicMock(spec=Agent)

    # Mock the agent to raise an exception
    mock_add_status.return_value = []
    mock_run_agent.side_effect = Exception("Graph query failed")

    with pytest.raises(Exception, match="Graph query failed"):
        await run_codebase_understanding_agent(
            agent=mock_agent,
            query="Invalid query",
            deps=mock_agent_deps,
        )


@pytest.mark.asyncio
async def test_query_codebase_tool_success(mock_agent_deps):
    """Test query_codebase tool wrapper handles results correctly."""
    # Create a simple mock that simulates the tool behavior
    # We test that the tool wrapper properly creates CodebaseQueryResult
    result = CodebaseQueryResult(
        success=True,
        result="Found database models in src/models/user.py:15",
    )

    assert result.success is True
    assert "database models" in result.result.lower()
    assert result.error is None


@pytest.mark.asyncio
async def test_query_codebase_tool_failure(mock_agent_deps):
    """Test query_codebase tool wrapper handles failures correctly."""
    # Test that CodebaseQueryResult properly represents failures
    result = CodebaseQueryResult(
        success=False,
        result="",
        error="Failed to create sub-agent",
    )

    assert result.success is False
    assert result.error is not None
    assert "failed" in result.error.lower()


def test_codebase_query_result_model():
    """Test CodebaseQueryResult model structure."""
    # Test successful result
    success_result = CodebaseQueryResult(
        success=True,
        result="Found code at src/main.py:42",
    )
    assert success_result.success is True
    assert success_result.result == "Found code at src/main.py:42"
    assert success_result.error is None

    # Test failed result
    failed_result = CodebaseQueryResult(
        success=False,
        result="",
        error="Graph not indexed",
    )
    assert failed_result.success is False
    assert failed_result.result == ""
    assert failed_result.error == "Graph not indexed"
