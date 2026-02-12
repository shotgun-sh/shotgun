"""Tests for the tiered Router → Planner escalation architecture."""

from asyncio import Queue
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import RunContext

from shotgun.agents.config.models import KeyProvider, ModelConfig, ProviderType
from shotgun.agents.models import AgentRuntimeOptions, AgentType, FileOperationTracker
from shotgun.agents.router.models import RouterDeps, RouterMode
from shotgun.agents.router.tools.escalation_tool import (
    EscalationInput,
    escalate_to_planner,
)
from shotgun.codebase.service import CodebaseService


def _make_model_config(name: str = "test-model") -> ModelConfig:
    """Create a ModelConfig with a test model_instance."""
    from pydantic_ai.models.test import TestModel

    config = ModelConfig(
        name=name,
        provider=ProviderType.ANTHROPIC,
        key_provider=KeyProvider.BYOK,
        max_input_tokens=128000,
        max_output_tokens=16000,
        api_key="test-key",
    )
    # Use pydantic_ai's TestModel to avoid real provider initialization
    config._model_instance = TestModel()
    return config


@pytest.fixture
def mock_router_deps():
    """Create mock RouterDeps for escalation testing."""
    deps = MagicMock(spec=RouterDeps)
    deps.router_mode = RouterMode.PLANNING
    deps.current_plan = None
    deps.file_tracker = FileOperationTracker()
    deps.active_sub_agent = None
    deps.sub_agent_cache = {}
    deps.interactive_mode = True
    deps.working_directory = Path("/test/dir")
    deps.is_tui_context = True
    deps.max_iterations = 100
    deps.queue = Queue()
    deps.tasks = []
    deps.parent_stream_handler = None
    deps.pending_approval = None
    deps.cancellation_event = None
    deps.usage_manager = MagicMock()
    deps.usage_manager.add_usage = AsyncMock()
    deps.escalation_requested = False
    deps.escalation_reason = ""
    deps.llm_model = _make_model_config()
    return deps


@pytest.fixture
def mock_context(mock_router_deps):
    """Create mock run context for testing."""
    ctx = MagicMock(spec=RunContext)
    ctx.deps = mock_router_deps
    return ctx


@pytest.mark.asyncio
async def test_escalate_to_planner_sets_flag(mock_context):
    """Test that escalate_to_planner sets the escalation_requested flag."""
    input_data = EscalationInput(reason="needs multi-step plan creation")

    result = await escalate_to_planner(mock_context, input_data)

    assert result.success is True
    assert mock_context.deps.escalation_requested is True
    assert mock_context.deps.escalation_reason == "needs multi-step plan creation"


@pytest.mark.asyncio
async def test_escalate_to_planner_returns_confirmation(mock_context):
    """Test that escalate_to_planner returns a confirmation message."""
    input_data = EscalationInput(reason="requires delegation to sub-agents")

    result = await escalate_to_planner(mock_context, input_data)

    assert result.success is True
    assert "Escalating" in result.message


@pytest.mark.asyncio
async def test_planner_agent_type_exists():
    """Test that PLANNER is a valid AgentType."""
    assert AgentType.PLANNER == "planner"
    assert AgentType.PLANNER.value == "planner"


@pytest.mark.asyncio
async def test_router_agent_tiered_mode():
    """Test that Router creates in tiered mode when cheap != expensive model."""
    cheap_config = _make_model_config("haiku-model")
    expensive_config = _make_model_config("opus-model")

    async def mock_get_provider_model(provider=None, for_sub_agent=False):
        return cheap_config if for_sub_agent else expensive_config

    with (
        patch(
            "shotgun.agents.router.router.get_provider_model",
            side_effect=mock_get_provider_model,
        ),
        patch("shotgun.agents.router.router.get_codebase_service", return_value=MagicMock(spec=CodebaseService)),
        patch("shotgun.agents.router.router.ensure_shotgun_directory_exists"),
    ):
        from shotgun.agents.router.router import create_router_agent

        options = AgentRuntimeOptions()
        agent, deps = await create_router_agent(options)

        # In tiered mode, Router uses cheap model
        assert deps.llm_model.name == "haiku-model"

        # Verify agent has escalation tool but not delegation tools
        tool_names = list(agent._function_toolset.tools.keys())
        assert "escalate_to_planner" in tool_names
        assert "delegate_to_research" not in tool_names
        assert "create_plan" not in tool_names


@pytest.mark.asyncio
async def test_router_agent_single_tier_mode():
    """Test that Router falls back to single-tier when cheap == expensive model."""
    same_config = _make_model_config("haiku-model")

    async def mock_get_provider_model(provider=None, for_sub_agent=False):
        return same_config

    with (
        patch(
            "shotgun.agents.router.router.get_provider_model",
            side_effect=mock_get_provider_model,
        ),
        patch("shotgun.agents.router.router.get_codebase_service", return_value=MagicMock(spec=CodebaseService)),
        patch("shotgun.agents.router.router.ensure_shotgun_directory_exists"),
    ):
        from shotgun.agents.router.router import create_router_agent

        options = AgentRuntimeOptions()
        agent, deps = await create_router_agent(options)

        # In single-tier mode, Router uses the same model
        assert deps.llm_model.name == "haiku-model"

        # Verify agent has full tools (no escalation tool)
        tool_names = list(agent._function_toolset.tools.keys())
        assert "escalate_to_planner" not in tool_names
        assert "create_plan" in tool_names
        assert "read_file" in tool_names


@pytest.mark.asyncio
async def test_planner_agent_uses_expensive_model():
    """Test that Planner agent uses the expensive model."""
    expensive_config = _make_model_config("opus-model")

    async def mock_get_provider_model(provider=None):
        return expensive_config

    with (
        patch(
            "shotgun.agents.planner.planner.get_provider_model",
            side_effect=mock_get_provider_model,
        ),
        patch("shotgun.agents.planner.planner.get_codebase_service", return_value=MagicMock(spec=CodebaseService)),
        patch("shotgun.agents.planner.planner.ensure_shotgun_directory_exists"),
    ):
        from shotgun.agents.planner.planner import create_planner_agent

        options = AgentRuntimeOptions()
        agent, deps = await create_planner_agent(options)

        # Planner uses expensive model
        assert deps.llm_model.name == "opus-model"

        # Planner has delegation tools and plan management tools
        tool_names = list(agent._function_toolset.tools.keys())
        assert "create_plan" in tool_names
        assert "mark_step_done" in tool_names
        assert "read_file" in tool_names
        # No escalation tool on Planner
        assert "escalate_to_planner" not in tool_names
