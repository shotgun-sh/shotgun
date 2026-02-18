"""Test Anthropic prompt caching settings on agents."""

from functools import partial
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai.models.test import TestModel

from shotgun.agents.common import build_agent_system_prompt, create_base_agent
from shotgun.agents.config.models import (
    ModelConfig,
    ModelName,
    ProviderType,
)
from shotgun.agents.models import AgentRuntimeOptions
from shotgun.agents.router.router import create_router_agent
from shotgun.codebase.service import CodebaseService


@pytest.fixture
def mock_model_config():
    """Create a mock ModelConfig that returns a real TestModel instance."""
    config = MagicMock(spec=ModelConfig)
    config.name = ModelName.CLAUDE_SONNET_4_6
    config.provider = ProviderType.ANTHROPIC
    config.max_input_tokens = 200000
    config.max_output_tokens = 8192
    config.supports_streaming = True
    config.supports_pdf = True
    config.supports_images = True
    config.base_url = None
    config.model_instance = TestModel()
    return config


@pytest.fixture
def mock_runtime_options():
    """Create mock AgentRuntimeOptions."""
    return AgentRuntimeOptions(interactive_mode=True, output_file="test.md")


@pytest.fixture
def mock_codebase_service():
    """Create a mock CodebaseService that passes Pydantic validation."""
    return MagicMock(spec=CodebaseService)


@patch("shotgun.agents.common.get_codebase_service")
@patch("shotgun.agents.common.get_provider_model", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_sub_agent_caches_messages_at_5m(
    mock_get_model,
    mock_get_codebase,
    mock_model_config,
    mock_runtime_options,
    mock_codebase_service,
):
    """Sub-agents should cache messages at 5m TTL for short task-scoped conversations."""
    mock_get_model.return_value = mock_model_config
    mock_get_codebase.return_value = mock_codebase_service

    system_prompt_fn = partial(build_agent_system_prompt, "research")

    agent, _deps = await create_base_agent(
        system_prompt_fn,
        mock_runtime_options,
    )

    settings = agent.model_settings
    assert settings is not None
    assert settings.get("anthropic_cache_tool_definitions") == "1h"
    assert settings.get("anthropic_cache_instructions") == "1h"
    assert settings.get("anthropic_cache_messages") == "5m"


@patch("shotgun.agents.router.router.get_codebase_service")
@patch("shotgun.agents.router.router.get_provider_model", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_router_agent_caches_messages_at_1h(
    mock_get_model,
    mock_get_codebase,
    mock_model_config,
    mock_runtime_options,
    mock_codebase_service,
):
    """Router agent should cache messages at 1h TTL for long-lived conversations."""
    mock_get_model.return_value = mock_model_config
    mock_get_codebase.return_value = mock_codebase_service

    agent, _deps = await create_router_agent(mock_runtime_options)

    settings = agent.model_settings
    assert settings is not None
    assert settings.get("anthropic_cache_tool_definitions") == "1h"
    assert settings.get("anthropic_cache_instructions") == "1h"
    assert settings.get("anthropic_cache_messages") == "1h"


@patch("shotgun.agents.router.router.get_codebase_service")
@patch("shotgun.agents.router.router.get_provider_model", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_router_cache_settings_do_not_include_parallel_tool_calls(
    mock_get_model,
    mock_get_codebase,
    mock_model_config,
    mock_runtime_options,
    mock_codebase_service,
):
    """Router default model_settings should only have cache settings, not parallel_tool_calls."""
    mock_get_model.return_value = mock_model_config
    mock_get_codebase.return_value = mock_codebase_service

    agent, _deps = await create_router_agent(mock_runtime_options)

    # parallel_tool_calls is set at run-time in run_router_agent, not on the agent default
    settings = agent.model_settings
    assert settings is not None
    assert "parallel_tool_calls" not in settings


@patch("shotgun.agents.common.get_codebase_service")
@patch("shotgun.agents.common.get_provider_model", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_router_and_sub_agents_have_different_message_cache_ttls(
    mock_get_model,
    mock_get_codebase,
    mock_model_config,
    mock_runtime_options,
    mock_codebase_service,
):
    """Router uses 1h message caching, sub-agents use 5m."""
    mock_get_model.return_value = mock_model_config
    mock_get_codebase.return_value = mock_codebase_service

    system_prompt_fn = partial(build_agent_system_prompt, "research")
    sub_agent, _ = await create_base_agent(system_prompt_fn, mock_runtime_options)

    sub_settings = sub_agent.model_settings
    assert sub_settings is not None
    assert sub_settings.get("anthropic_cache_tool_definitions") == "1h"
    assert sub_settings.get("anthropic_cache_instructions") == "1h"
    assert sub_settings.get("anthropic_cache_messages") == "5m"
