"""Tests for the tiered Router → Planner escalation architecture."""

from unittest.mock import MagicMock, patch

import pytest

from shotgun.agents.config.models import KeyProvider, ModelConfig, ProviderType
from shotgun.agents.models import AgentResponse, AgentRuntimeOptions, AgentType
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


def test_agent_response_escalation_fields_default():
    """Test that AgentResponse escalation fields default to False/None."""
    response = AgentResponse(response="Hello")
    assert response.escalation_requested is False
    assert response.escalation_reason is None
    assert response.escalation_synopsis is None


def test_agent_response_escalation_fields_set():
    """Test that AgentResponse escalation fields can be set."""
    response = AgentResponse(
        response="Escalating to Planner.",
        escalation_requested=True,
        escalation_reason="needs multi-step plan creation",
        escalation_synopsis="User wants OAuth2. They need Google + GitHub providers.",
    )
    assert response.escalation_requested is True
    assert response.escalation_reason == "needs multi-step plan creation"
    assert "OAuth2" in response.escalation_synopsis


def test_agent_response_escalation_invisible_to_non_router():
    """Test that non-escalation responses are unaffected by escalation fields."""
    response = AgentResponse(
        response="Here's the research summary.",
        clarifying_questions=["What framework?"],
    )
    assert response.escalation_requested is False
    assert response.escalation_reason is None
    assert response.escalation_synopsis is None
    assert response.clarifying_questions == ["What framework?"]


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
        patch(
            "shotgun.agents.router.router.get_codebase_service",
            return_value=MagicMock(spec=CodebaseService),
        ),
        patch("shotgun.agents.router.router.ensure_shotgun_directory_exists"),
    ):
        from shotgun.agents.router.router import create_router_agent

        options = AgentRuntimeOptions()
        agent, deps = await create_router_agent(options)

        # In tiered mode, Router uses cheap model
        assert deps.llm_model.name == "haiku-model"

        # Verify agent has read_file but NOT escalation tool or delegation tools
        tool_names = list(agent._function_toolset.tools.keys())
        assert "read_file" in tool_names
        assert "escalate_to_planner" not in tool_names
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
        patch(
            "shotgun.agents.router.router.get_codebase_service",
            return_value=MagicMock(spec=CodebaseService),
        ),
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
        patch(
            "shotgun.agents.planner.planner.get_codebase_service",
            return_value=MagicMock(spec=CodebaseService),
        ),
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


def test_router_deps_no_escalation_fields():
    """Test that RouterDeps no longer has escalation fields."""
    from shotgun.agents.router.models import RouterDeps

    field_names = set(RouterDeps.model_fields.keys())
    assert "escalation_requested" not in field_names
    assert "escalation_reason" not in field_names
