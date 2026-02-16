"""Test cleanup_agents() in AgentManager."""

from unittest.mock import MagicMock

import pytest

from shotgun.agents.agent_manager import AgentManager
from shotgun.agents.models import AgentType


@pytest.fixture
def agent_manager():
    """Create a minimal AgentManager with agent/deps fields set."""
    manager = AgentManager.__new__(AgentManager)
    manager._research_agent = MagicMock()
    manager._research_deps = MagicMock()
    manager._plan_agent = MagicMock()
    manager._plan_deps = MagicMock()
    manager._tasks_agent = MagicMock()
    manager._tasks_deps = MagicMock()
    manager._specify_agent = MagicMock()
    manager._specify_deps = MagicMock()
    manager._export_agent = MagicMock()
    manager._export_deps = MagicMock()
    manager._router_agent = MagicMock()
    manager._router_deps = MagicMock()
    manager._router_deps.sub_agent_cache = {AgentType.RESEARCH: MagicMock()}
    manager._router_deps.parent_stream_handler = MagicMock()
    manager._router_deps.on_plan_changed = MagicMock()
    manager._agents_initialized = True
    return manager


@pytest.fixture
def uninitialized_agent_manager():
    """Create a minimal AgentManager that was never initialized."""
    manager = AgentManager.__new__(AgentManager)
    manager._research_agent = None
    manager._research_deps = None
    manager._plan_agent = None
    manager._plan_deps = None
    manager._tasks_agent = None
    manager._tasks_deps = None
    manager._specify_agent = None
    manager._specify_deps = None
    manager._export_agent = None
    manager._export_deps = None
    manager._router_agent = None
    manager._router_deps = None
    manager._agents_initialized = False
    return manager


@pytest.mark.asyncio
async def test_cleanup_sets_all_agents_to_none(agent_manager):
    """cleanup_agents() should null all agent and deps references."""
    await agent_manager.cleanup_agents()

    assert agent_manager._research_agent is None
    assert agent_manager._research_deps is None
    assert agent_manager._plan_agent is None
    assert agent_manager._plan_deps is None
    assert agent_manager._tasks_agent is None
    assert agent_manager._tasks_deps is None
    assert agent_manager._specify_agent is None
    assert agent_manager._specify_deps is None
    assert agent_manager._export_agent is None
    assert agent_manager._export_deps is None
    assert agent_manager._router_agent is None
    assert agent_manager._router_deps is None
    assert agent_manager._agents_initialized is False


@pytest.mark.asyncio
async def test_cleanup_clears_router_deps_cache_and_callbacks(agent_manager):
    """cleanup_agents() should clear sub_agent_cache and nullify callbacks."""
    router_deps = agent_manager._router_deps

    await agent_manager.cleanup_agents()

    assert len(router_deps.sub_agent_cache) == 0
    assert router_deps.parent_stream_handler is None
    assert router_deps.on_plan_changed is None


@pytest.mark.asyncio
async def test_cleanup_safe_when_not_initialized(uninitialized_agent_manager):
    """cleanup_agents() should be a no-op when agents were never initialized."""
    await uninitialized_agent_manager.cleanup_agents()

    assert uninitialized_agent_manager._agents_initialized is False
    assert uninitialized_agent_manager._router_deps is None
