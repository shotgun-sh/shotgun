"""Test AgentManager router integration."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import Agent

from shotgun.agents.agent_manager import AgentManager
from shotgun.agents.config.models import ProviderType
from shotgun.agents.models import AgentDeps, AgentType
from shotgun.agents.router.models import RouterDeps, RouterMode
from shotgun.agents.usage_manager import SessionUsageManager


@pytest.fixture
def mock_router_deps():
    """Create mock RouterDeps for testing."""
    deps = MagicMock(spec=RouterDeps)
    deps.interactive_mode = True
    deps.working_directory = Path("/test")
    deps.max_iterations = 10
    deps.queue = asyncio.Queue()
    deps.tasks = []
    deps.is_tui_context = False

    # Router-specific fields
    deps.router_mode = RouterMode.PLANNING
    deps.current_plan = None
    deps.approval_status = None
    deps.active_sub_agent = None
    deps.is_executing = False
    deps.sub_agent_cache = {}
    deps.pending_checkpoint = None
    deps.pending_cascade = None
    deps.parent_stream_handler = None

    # File tracker
    file_tracker_mock = MagicMock()
    file_tracker_mock.clear = MagicMock()
    file_tracker_mock.operations = []
    file_tracker_mock.format_summary = MagicMock(return_value="No files modified")
    deps.file_tracker = file_tracker_mock

    # LLM model
    llm_model_mock = MagicMock()
    llm_model_mock.name = "test-model"
    llm_model_mock.provider = ProviderType.ANTHROPIC
    deps.llm_model = llm_model_mock

    # Other required fields
    deps.codebase_service = MagicMock()
    deps.artifact_service = MagicMock()
    deps.system_prompt_fn = MagicMock(return_value="Test system prompt")

    usage_manager_mock = MagicMock(spec=SessionUsageManager)
    usage_manager_mock.add_usage = AsyncMock()
    usage_manager_mock.build_usage_hint = MagicMock(return_value="Usage hint")
    deps.usage_manager = usage_manager_mock

    # model_copy implementation
    def mock_model_copy(update=None):
        """Mock model_copy that preserves fields."""
        copy_mock = MagicMock(spec=RouterDeps)
        for attr_name in [
            "interactive_mode",
            "working_directory",
            "max_iterations",
            "queue",
            "tasks",
            "file_tracker",
            "llm_model",
            "codebase_service",
            "artifact_service",
            "system_prompt_fn",
            "usage_manager",
            "is_tui_context",
            "router_mode",
            "current_plan",
            "approval_status",
            "active_sub_agent",
            "is_executing",
            "sub_agent_cache",
            "pending_checkpoint",
            "pending_cascade",
            "parent_stream_handler",
        ]:
            setattr(copy_mock, attr_name, getattr(deps, attr_name, None))

        if update:
            for key, value in update.items():
                setattr(copy_mock, key, value)

        return copy_mock

    deps.model_copy = mock_model_copy

    return deps


@pytest.fixture
def mock_agent_deps():
    """Create mock AgentDeps for sub-agents."""
    deps = MagicMock(spec=AgentDeps)
    deps.system_prompt_fn = MagicMock(return_value="Sub-agent system prompt")
    return deps


@pytest.mark.asyncio
@patch("shotgun.agents.agent_manager.create_router_agent")
@patch("shotgun.agents.agent_manager.create_research_agent")
@patch("shotgun.agents.agent_manager.create_plan_agent")
@patch("shotgun.agents.agent_manager.create_tasks_agent")
@patch("shotgun.agents.agent_manager.create_specify_agent")
@patch("shotgun.agents.agent_manager.create_export_agent")
async def test_agent_manager_creates_router_agent(
    mock_create_export,
    mock_create_specify,
    mock_create_tasks,
    mock_create_plan,
    mock_create_research,
    mock_create_router,
    mock_router_deps,
    mock_agent_deps,
):
    """Verify AgentManager can create and access router agent."""
    # Create mock agents
    router_agent = MagicMock(spec=Agent)
    research_agent = MagicMock(spec=Agent)

    mock_create_router.return_value = (router_agent, mock_router_deps)
    mock_create_research.return_value = (research_agent, mock_agent_deps)
    mock_create_plan.return_value = (research_agent, mock_agent_deps)
    mock_create_tasks.return_value = (research_agent, mock_agent_deps)
    mock_create_specify.return_value = (research_agent, mock_agent_deps)
    mock_create_export.return_value = (research_agent, mock_agent_deps)

    manager = AgentManager(deps=mock_router_deps, initial_type=AgentType.ROUTER)
    await manager._ensure_agents_initialized()

    assert manager.router_agent is not None
    assert manager.router_agent == router_agent
    assert manager.router_deps is not None
    assert manager.router_deps == mock_router_deps


@pytest.mark.asyncio
@patch("shotgun.agents.agent_manager.create_router_agent")
@patch("shotgun.agents.agent_manager.create_research_agent")
@patch("shotgun.agents.agent_manager.create_plan_agent")
@patch("shotgun.agents.agent_manager.create_tasks_agent")
@patch("shotgun.agents.agent_manager.create_specify_agent")
@patch("shotgun.agents.agent_manager.create_export_agent")
async def test_agent_manager_get_agent_returns_router(
    mock_create_export,
    mock_create_specify,
    mock_create_tasks,
    mock_create_plan,
    mock_create_research,
    mock_create_router,
    mock_router_deps,
    mock_agent_deps,
):
    """Verify _get_agent returns router for ROUTER type."""
    router_agent = MagicMock(spec=Agent)
    research_agent = MagicMock(spec=Agent)

    mock_create_router.return_value = (router_agent, mock_router_deps)
    mock_create_research.return_value = (research_agent, mock_agent_deps)
    mock_create_plan.return_value = (research_agent, mock_agent_deps)
    mock_create_tasks.return_value = (research_agent, mock_agent_deps)
    mock_create_specify.return_value = (research_agent, mock_agent_deps)
    mock_create_export.return_value = (research_agent, mock_agent_deps)

    manager = AgentManager(deps=mock_router_deps, initial_type=AgentType.ROUTER)
    await manager._ensure_agents_initialized()

    agent = manager._get_agent(AgentType.ROUTER)
    assert agent is router_agent


@pytest.mark.asyncio
@patch("shotgun.agents.agent_manager.create_router_agent")
@patch("shotgun.agents.agent_manager.create_research_agent")
@patch("shotgun.agents.agent_manager.create_plan_agent")
@patch("shotgun.agents.agent_manager.create_tasks_agent")
@patch("shotgun.agents.agent_manager.create_specify_agent")
@patch("shotgun.agents.agent_manager.create_export_agent")
async def test_agent_manager_get_agent_deps_returns_router_deps(
    mock_create_export,
    mock_create_specify,
    mock_create_tasks,
    mock_create_plan,
    mock_create_research,
    mock_create_router,
    mock_router_deps,
    mock_agent_deps,
):
    """Verify _get_agent_deps returns RouterDeps for ROUTER type."""
    router_agent = MagicMock(spec=Agent)
    research_agent = MagicMock(spec=Agent)

    mock_create_router.return_value = (router_agent, mock_router_deps)
    mock_create_research.return_value = (research_agent, mock_agent_deps)
    mock_create_plan.return_value = (research_agent, mock_agent_deps)
    mock_create_tasks.return_value = (research_agent, mock_agent_deps)
    mock_create_specify.return_value = (research_agent, mock_agent_deps)
    mock_create_export.return_value = (research_agent, mock_agent_deps)

    manager = AgentManager(deps=mock_router_deps, initial_type=AgentType.ROUTER)
    await manager._ensure_agents_initialized()

    deps = manager._get_agent_deps(AgentType.ROUTER)
    assert deps == mock_router_deps


@pytest.mark.asyncio
@patch("shotgun.agents.agent_manager.create_router_agent")
@patch("shotgun.agents.agent_manager.create_research_agent")
@patch("shotgun.agents.agent_manager.create_plan_agent")
@patch("shotgun.agents.agent_manager.create_tasks_agent")
@patch("shotgun.agents.agent_manager.create_specify_agent")
@patch("shotgun.agents.agent_manager.create_export_agent")
async def test_agent_manager_set_agent_to_router(
    mock_create_export,
    mock_create_specify,
    mock_create_tasks,
    mock_create_plan,
    mock_create_research,
    mock_create_router,
    mock_router_deps,
    mock_agent_deps,
):
    """Verify set_agent works with ROUTER type."""
    router_agent = MagicMock(spec=Agent)
    research_agent = MagicMock(spec=Agent)

    mock_create_router.return_value = (router_agent, mock_router_deps)
    mock_create_research.return_value = (research_agent, mock_agent_deps)
    mock_create_plan.return_value = (research_agent, mock_agent_deps)
    mock_create_tasks.return_value = (research_agent, mock_agent_deps)
    mock_create_specify.return_value = (research_agent, mock_agent_deps)
    mock_create_export.return_value = (research_agent, mock_agent_deps)

    manager = AgentManager(deps=mock_router_deps, initial_type=AgentType.RESEARCH)
    await manager._ensure_agents_initialized()

    # Start with RESEARCH
    assert manager._current_agent_type == AgentType.RESEARCH

    # Switch to ROUTER
    manager.set_agent(AgentType.ROUTER)
    assert manager._current_agent_type == AgentType.ROUTER

    # Verify current_agent returns router
    assert manager.current_agent is router_agent


@pytest.mark.asyncio
@patch("shotgun.agents.agent_manager.create_router_agent")
@patch("shotgun.agents.agent_manager.create_research_agent")
@patch("shotgun.agents.agent_manager.create_plan_agent")
@patch("shotgun.agents.agent_manager.create_tasks_agent")
@patch("shotgun.agents.agent_manager.create_specify_agent")
@patch("shotgun.agents.agent_manager.create_export_agent")
async def test_agent_manager_current_agent_when_router(
    mock_create_export,
    mock_create_specify,
    mock_create_tasks,
    mock_create_plan,
    mock_create_research,
    mock_create_router,
    mock_router_deps,
    mock_agent_deps,
):
    """Verify current_agent returns router when ROUTER is active."""
    router_agent = MagicMock(spec=Agent)
    research_agent = MagicMock(spec=Agent)

    mock_create_router.return_value = (router_agent, mock_router_deps)
    mock_create_research.return_value = (research_agent, mock_agent_deps)
    mock_create_plan.return_value = (research_agent, mock_agent_deps)
    mock_create_tasks.return_value = (research_agent, mock_agent_deps)
    mock_create_specify.return_value = (research_agent, mock_agent_deps)
    mock_create_export.return_value = (research_agent, mock_agent_deps)

    manager = AgentManager(deps=mock_router_deps, initial_type=AgentType.ROUTER)
    await manager._ensure_agents_initialized()

    assert manager.current_agent is router_agent


def test_agent_type_router_enum():
    """Test that ROUTER is a valid AgentType."""
    assert AgentType.ROUTER.value == "router"
    assert AgentType("router") == AgentType.ROUTER
