"""Test exception handling in agent functions."""

from unittest.mock import MagicMock, patch

import pytest

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
    deps = MagicMock()
    deps.interactive_mode = True
    return deps


@pytest.mark.asyncio
async def test_research_agent_exception_handling(mock_agent, mock_deps):
    """Test research agent exception handling and logging."""
    mock_agent.run.side_effect = Exception("Test error")

    with (
        patch("shotgun.agents.research.add_system_status_message") as mock_add_status,
        patch("shotgun.agents.research.create_usage_limits") as mock_limits,
    ):
        mock_add_status.return_value = []
        mock_limits.return_value = MagicMock()

        with pytest.raises(Exception, match="Test error"):
            await run_research_agent(mock_agent, "test query", mock_deps)


@pytest.mark.asyncio
async def test_plan_agent_exception_handling(mock_agent, mock_deps):
    """Test plan agent exception handling and logging."""
    mock_agent.run.side_effect = Exception("Plan error")

    with (
        patch("shotgun.agents.plan.add_system_status_message") as mock_add_status,
        patch("shotgun.agents.plan.create_usage_limits") as mock_limits,
    ):
        mock_add_status.return_value = []
        mock_limits.return_value = MagicMock()

        with pytest.raises(Exception, match="Plan error"):
            await run_plan_agent(mock_agent, "test goal", mock_deps)


@pytest.mark.asyncio
async def test_specify_agent_exception_handling(mock_agent, mock_deps):
    """Test specify agent exception handling and logging."""
    mock_agent.run.side_effect = Exception("Specify error")

    with (
        patch("shotgun.agents.specify.add_system_status_message") as mock_add_status,
        patch("shotgun.agents.specify.create_usage_limits") as mock_limits,
    ):
        mock_add_status.return_value = []
        mock_limits.return_value = MagicMock()

        with pytest.raises(Exception, match="Specify error"):
            await run_specify_agent(mock_agent, "test requirement", mock_deps)


@pytest.mark.asyncio
async def test_tasks_agent_exception_handling(mock_agent, mock_deps):
    """Test tasks agent exception handling and logging."""
    mock_agent.run.side_effect = Exception("Tasks error")

    with (
        patch("shotgun.agents.tasks.add_system_status_message") as mock_add_status,
        patch("shotgun.agents.tasks.create_usage_limits") as mock_limits,
    ):
        mock_add_status.return_value = []
        mock_limits.return_value = MagicMock()

        with pytest.raises(Exception, match="Tasks error"):
            await run_tasks_agent(mock_agent, "test instruction", mock_deps)
