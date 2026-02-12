"""Test exception handling in agent functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shotgun.agents.models import AgentDeps
from shotgun.agents.plan import run_plan_agent
from shotgun.agents.research import run_research_agent
from shotgun.agents.specify import run_specify_agent
from shotgun.agents.tasks import run_tasks_agent


@pytest.fixture
def mock_agent():
    """Create mock agent for testing."""
    agent = MagicMock()
    agent.run = MagicMock()
    return agent


@pytest.fixture
def mock_deps():
    """Create mock AgentDeps for testing."""
    deps = MagicMock(spec=AgentDeps)
    deps.interactive_mode = True
    deps.has_codebase_indexed = False
    # Add proper async mock for codebase_service
    deps.codebase_service = AsyncMock()
    deps.codebase_service.list_graphs_for_directory = AsyncMock(return_value=[])
    deps.system_prompt_fn = MagicMock(return_value="Test system prompt")
    deps.agent_mode = None
    # Add file_tracker mock
    deps.file_tracker = MagicMock()
    deps.file_tracker.clear = MagicMock()
    deps.file_tracker.operations = []
    return deps


@pytest.mark.asyncio
async def test_research_agent_exception_handling(mock_agent, mock_deps):
    """Test research agent exception handling and logging."""
    mock_agent.run.side_effect = Exception("Test error")

    with (
        patch("shotgun.agents.research.add_system_status_message") as mock_add_status,
        patch("shotgun.agents.research.create_usage_limits") as mock_limits,
        patch(
            "shotgun.agents.common.add_system_prompt_message"
        ) as mock_add_system_prompt,
    ):
        mock_add_status.return_value = []
        mock_limits.return_value = MagicMock()
        mock_add_system_prompt.return_value = []

        with pytest.raises(Exception, match="Test error"):
            await run_research_agent(mock_agent, "test query", mock_deps)


@pytest.mark.asyncio
async def test_plan_agent_exception_handling(mock_agent, mock_deps):
    """Test plan agent exception handling and logging."""
    mock_agent.run.side_effect = Exception("Plan error")

    with (
        patch("shotgun.agents.plan.add_system_status_message") as mock_add_status,
        patch("shotgun.agents.plan.create_usage_limits") as mock_limits,
        patch(
            "shotgun.agents.common.add_system_prompt_message"
        ) as mock_add_system_prompt,
    ):
        mock_add_status.return_value = []
        mock_limits.return_value = MagicMock()
        mock_add_system_prompt.return_value = []

        with pytest.raises(Exception, match="Plan error"):
            await run_plan_agent(mock_agent, "test goal", mock_deps)


@pytest.mark.asyncio
async def test_specify_agent_exception_handling(mock_agent, mock_deps):
    """Test specify agent exception handling and logging."""
    mock_agent.run.side_effect = Exception("Specify error")

    with (
        patch("shotgun.agents.specify.add_system_status_message") as mock_add_status,
        patch("shotgun.agents.specify.create_usage_limits") as mock_limits,
        patch(
            "shotgun.agents.common.add_system_prompt_message"
        ) as mock_add_system_prompt,
    ):
        mock_add_status.return_value = []
        mock_limits.return_value = MagicMock()
        mock_add_system_prompt.return_value = []

        with pytest.raises(Exception, match="Specify error"):
            await run_specify_agent(mock_agent, "test requirement", mock_deps)


@pytest.mark.asyncio
async def test_tasks_agent_exception_handling(mock_agent, mock_deps):
    """Test tasks agent exception handling and logging."""
    mock_agent.run.side_effect = Exception("Tasks error")

    with (
        patch("shotgun.agents.tasks.add_system_status_message") as mock_add_status,
        patch("shotgun.agents.tasks.create_usage_limits") as mock_limits,
        patch(
            "shotgun.agents.common.add_system_prompt_message"
        ) as mock_add_system_prompt,
    ):
        mock_add_status.return_value = []
        mock_limits.return_value = MagicMock()
        mock_add_system_prompt.return_value = []

        with pytest.raises(Exception, match="Tasks error"):
            await run_tasks_agent(mock_agent, "test instruction", mock_deps)
