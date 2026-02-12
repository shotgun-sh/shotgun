"""Test agent manager system prompt filtering."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from shotgun.agents.agent_manager import AgentManager
from shotgun.agents.config.models import ProviderType
from shotgun.agents.messages import AgentSystemPrompt, SystemStatusPrompt
from shotgun.agents.models import AgentDeps, AgentType
from shotgun.agents.usage_manager import SessionUsageManager


@pytest.fixture
def mock_agent_deps():
    """Create mock AgentDeps for testing."""
    deps = MagicMock(spec=AgentDeps)
    deps.interactive_mode = True
    deps.working_directory = Path("/test")
    deps.max_iterations = 10
    deps.queue = asyncio.Queue()
    deps.tasks = []
    deps.llm_model = MagicMock()
    deps.llm_model.name = "test-model"
    deps.llm_model.provider = ProviderType.ANTHROPIC
    deps.is_tui_context = False

    # Add file_tracker mock
    file_tracker_mock = MagicMock()
    file_tracker_mock.clear = MagicMock()
    file_tracker_mock.operations = []
    file_tracker_mock.format_summary = MagicMock(return_value="No files modified")
    deps.file_tracker = file_tracker_mock

    # Add additional fields needed by agent creation
    deps.codebase_service = AsyncMock()
    deps.codebase_service.list_graphs_for_directory = AsyncMock(return_value=[])
    deps.artifact_service = MagicMock()
    deps.system_prompt_fn = MagicMock(return_value="Test system prompt")
    deps.usage_manager = MagicMock(spec=SessionUsageManager)

    # Ensure model_copy preserves the structure
    def mock_model_copy(update=None):
        """Mock model_copy that preserves structure."""
        copy_mock = MagicMock(spec=AgentDeps)
        # Copy all attributes from original
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
        ]:
            setattr(copy_mock, attr_name, getattr(deps, attr_name))

        # Apply updates if provided
        if update:
            for key, value in update.items():
                setattr(copy_mock, key, value)

        return copy_mock

    deps.model_copy = mock_model_copy

    return deps


@pytest.mark.asyncio
@patch("shotgun.agents.agent_manager.apply_persistent_compaction")
@patch("shotgun.agents.agent_manager.add_system_prompt_message")
@patch("shotgun.agents.agent_manager.add_system_status_message")
@patch("shotgun.agents.agent_manager.create_router_agent")
@patch("shotgun.agents.agent_manager.create_research_agent")
@patch("shotgun.agents.agent_manager.create_plan_agent")
@patch("shotgun.agents.agent_manager.create_tasks_agent")
@patch("shotgun.agents.agent_manager.create_specify_agent")
@patch("shotgun.agents.agent_manager.create_export_agent")
async def test_filters_system_prompts_from_other_agents(
    mock_create_export,
    mock_create_specify,
    mock_create_tasks,
    mock_create_plan,
    mock_create_research,
    mock_create_router,
    mock_add_system_status,
    mock_add_system_prompt,
    mock_apply_compaction,
    mock_agent_deps,
):
    """Test that system prompts from other agent types are filtered out."""

    # Mock the agent creation functions to return coroutines that yield (agent, deps) tuples
    async def async_create_agent(*args, **kwargs):
        return (MagicMock(), mock_agent_deps)

    mock_create_research.side_effect = async_create_agent
    mock_create_plan.side_effect = async_create_agent
    mock_create_tasks.side_effect = async_create_agent
    mock_create_specify.side_effect = async_create_agent
    mock_create_export.side_effect = async_create_agent
    mock_create_router.side_effect = async_create_agent

    # Mock the system message functions to just return the messages as-is
    mock_add_system_status.side_effect = lambda deps, msgs: msgs
    mock_add_system_prompt.side_effect = lambda deps, msgs: (
        msgs
        + [
            ModelRequest(
                parts=[
                    AgentSystemPrompt(
                        content="Research agent prompt", agent_mode=AgentType.RESEARCH
                    )
                ]
            )
        ]
    )
    mock_apply_compaction.side_effect = lambda msgs, deps: msgs

    manager = AgentManager(deps=mock_agent_deps)

    # Create message history with system prompts from different agents
    messages = [
        ModelRequest(
            parts=[
                AgentSystemPrompt(
                    content="Research agent prompt",
                    agent_mode=AgentType.RESEARCH,
                ),
                UserPromptPart(content="Initial user request"),
            ]
        ),
        ModelResponse(parts=[TextPart(content="Research response")]),
        ModelRequest(
            parts=[
                AgentSystemPrompt(
                    content="Plan agent prompt",
                    agent_mode=AgentType.PLAN,
                ),
                UserPromptPart(content="Switch to planning"),
            ]
        ),
        ModelResponse(parts=[TextPart(content="Plan response")]),
    ]

    manager.message_history = messages

    # Switch to research agent
    manager._current_agent_type = AgentType.RESEARCH

    # Ensure agents are initialized
    await manager._ensure_agents_initialized()

    # Mock the agent run to capture the filtered message history
    captured_messages = None

    async def mock_run(*args, message_history=None, **kwargs):
        nonlocal captured_messages
        captured_messages = message_history
        # Return a minimal valid result
        from pydantic_ai.agent import AgentRunResult

        from shotgun.agents.models import AgentResponse

        mock_result = MagicMock(spec=AgentRunResult)
        mock_result.output = AgentResponse(
            response="test response", clarifying_questions=None
        )
        mock_result.messages = message_history + [
            ModelResponse(parts=[TextPart(content="test response")])
        ]
        mock_result.all_messages.return_value = mock_result.messages
        mock_result.new_messages.return_value = [mock_result.messages[-1]]
        mock_result.usage.return_value = MagicMock()
        return mock_result

    # Patch the research agent's run method
    import unittest.mock

    with unittest.mock.patch.object(
        manager.research_agent, "run", side_effect=mock_run
    ):
        await manager.run(prompt="Test prompt", deps=manager.research_deps)

    # Verify that only the research agent's system prompt is present
    assert captured_messages is not None

    # Check that we have the research system prompt
    has_research_prompt = False
    has_plan_prompt = False

    for msg in captured_messages:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, AgentSystemPrompt):
                    if part.agent_mode == AgentType.RESEARCH:
                        has_research_prompt = True
                        assert "Research agent prompt" in part.content
                    elif part.agent_mode == AgentType.PLAN:
                        has_plan_prompt = True

    assert has_research_prompt, "Research agent prompt should be present"
    assert not has_plan_prompt, "Plan agent prompt should be filtered out"


@pytest.mark.asyncio
@patch("shotgun.agents.agent_manager.apply_persistent_compaction")
@patch("shotgun.agents.agent_manager.add_system_prompt_message")
@patch("shotgun.agents.agent_manager.add_system_status_message")
@patch("shotgun.agents.agent_manager.create_router_agent")
@patch("shotgun.agents.agent_manager.create_research_agent")
@patch("shotgun.agents.agent_manager.create_plan_agent")
@patch("shotgun.agents.agent_manager.create_tasks_agent")
@patch("shotgun.agents.agent_manager.create_specify_agent")
@patch("shotgun.agents.agent_manager.create_export_agent")
async def test_preserves_non_agent_system_prompts(
    mock_create_export,
    mock_create_specify,
    mock_create_tasks,
    mock_create_plan,
    mock_create_research,
    mock_create_router,
    mock_add_system_status,
    mock_add_system_prompt,
    mock_apply_compaction,
    mock_agent_deps,
):
    """Test that SystemStatusPrompt and other parts are preserved."""

    # Mock the agent creation functions to return coroutines that yield (agent, deps) tuples
    async def async_create_agent(*args, **kwargs):
        return (MagicMock(), mock_agent_deps)

    mock_create_research.side_effect = async_create_agent
    mock_create_plan.side_effect = async_create_agent
    mock_create_tasks.side_effect = async_create_agent
    mock_create_specify.side_effect = async_create_agent
    mock_create_export.side_effect = async_create_agent
    mock_create_router.side_effect = async_create_agent

    # Mock the system message functions
    mock_add_system_status.side_effect = lambda deps, msgs: (
        msgs + [ModelRequest(parts=[SystemStatusPrompt(content="New status")])]
    )
    mock_add_system_prompt.side_effect = lambda deps, msgs: msgs
    mock_apply_compaction.side_effect = lambda msgs, deps: msgs

    manager = AgentManager(deps=mock_agent_deps)

    # Create message history with mixed prompt types
    messages = [
        ModelRequest(
            parts=[
                AgentSystemPrompt(
                    content="Research agent prompt",
                    agent_mode=AgentType.RESEARCH,
                ),
                SystemStatusPrompt(
                    content="System status information",
                ),
                UserPromptPart(content="User request"),
            ]
        ),
        ModelResponse(parts=[TextPart(content="Response")]),
    ]

    manager.message_history = messages
    manager._current_agent_type = AgentType.RESEARCH

    # Ensure agents are initialized
    await manager._ensure_agents_initialized()

    # Mock the agent run to capture the filtered message history
    captured_messages = None

    async def mock_run(*args, message_history=None, **kwargs):
        nonlocal captured_messages
        captured_messages = message_history
        from pydantic_ai.agent import AgentRunResult

        from shotgun.agents.models import AgentResponse

        mock_result = MagicMock(spec=AgentRunResult)
        mock_result.output = AgentResponse(
            response="test response", clarifying_questions=None
        )
        mock_result.messages = message_history + [
            ModelResponse(parts=[TextPart(content="test response")])
        ]
        mock_result.all_messages.return_value = mock_result.messages
        mock_result.new_messages.return_value = [mock_result.messages[-1]]
        mock_result.usage.return_value = MagicMock()
        return mock_result

    import unittest.mock

    with unittest.mock.patch.object(
        manager.research_agent, "run", side_effect=mock_run
    ):
        await manager.run(prompt="Test prompt", deps=manager.research_deps)

    # Verify all non-AgentSystemPrompt parts are preserved
    assert captured_messages is not None

    has_system_status = False
    has_user_prompt = False
    has_research_prompt = False

    for msg in captured_messages:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, SystemStatusPrompt):
                    has_system_status = True
                elif isinstance(part, UserPromptPart):
                    has_user_prompt = True
                elif isinstance(part, AgentSystemPrompt):
                    if part.agent_mode == AgentType.RESEARCH:
                        has_research_prompt = True

    assert has_research_prompt, "Research agent prompt should be present"
    assert has_system_status, "System status should be preserved"
    assert has_user_prompt, "User prompts should be preserved"


@pytest.mark.asyncio
@patch("shotgun.agents.agent_manager.apply_persistent_compaction")
@patch("shotgun.agents.agent_manager.add_system_prompt_message")
@patch("shotgun.agents.agent_manager.add_system_status_message")
@patch("shotgun.agents.agent_manager.create_router_agent")
@patch("shotgun.agents.agent_manager.create_research_agent")
@patch("shotgun.agents.agent_manager.create_plan_agent")
@patch("shotgun.agents.agent_manager.create_tasks_agent")
@patch("shotgun.agents.agent_manager.create_specify_agent")
@patch("shotgun.agents.agent_manager.create_export_agent")
async def test_filters_mixed_agent_prompts(
    mock_create_export,
    mock_create_specify,
    mock_create_tasks,
    mock_create_plan,
    mock_create_research,
    mock_create_router,
    mock_add_system_status,
    mock_add_system_prompt,
    mock_apply_compaction,
    mock_agent_deps,
):
    """Test filtering when multiple agent prompts are mixed in history."""

    # Mock the agent creation functions to return coroutines that yield (agent, deps) tuples
    async def async_create_agent(*args, **kwargs):
        return (MagicMock(), mock_agent_deps)

    mock_create_research.side_effect = async_create_agent
    mock_create_plan.side_effect = async_create_agent
    mock_create_tasks.side_effect = async_create_agent
    mock_create_specify.side_effect = async_create_agent
    mock_create_export.side_effect = async_create_agent
    mock_create_router.side_effect = async_create_agent

    # Mock the system message functions
    mock_add_system_status.side_effect = lambda deps, msgs: msgs
    mock_add_system_prompt.side_effect = lambda deps, msgs: msgs
    mock_apply_compaction.side_effect = lambda msgs, deps: msgs

    manager = AgentManager(deps=mock_agent_deps)

    # Create complex message history
    messages = [
        ModelRequest(
            parts=[
                AgentSystemPrompt(
                    content="Research prompt 1",
                    agent_mode=AgentType.RESEARCH,
                ),
                UserPromptPart(content="Request 1"),
            ]
        ),
        ModelRequest(
            parts=[
                AgentSystemPrompt(
                    content="Plan prompt",
                    agent_mode=AgentType.PLAN,
                ),
                AgentSystemPrompt(
                    content="Research prompt 2",
                    agent_mode=AgentType.RESEARCH,
                ),
                SystemStatusPrompt(content="Status"),
            ]
        ),
    ]

    manager.message_history = messages
    manager._current_agent_type = AgentType.RESEARCH

    # Ensure agents are initialized
    await manager._ensure_agents_initialized()

    # Mock the agent run
    captured_messages = None

    async def mock_run(*args, message_history=None, **kwargs):
        nonlocal captured_messages
        captured_messages = message_history
        from pydantic_ai.agent import AgentRunResult

        from shotgun.agents.models import AgentResponse

        mock_result = MagicMock(spec=AgentRunResult)
        mock_result.output = AgentResponse(response="test", clarifying_questions=None)
        mock_result.messages = message_history + [
            ModelResponse(parts=[TextPart(content="test")])
        ]
        mock_result.all_messages.return_value = mock_result.messages
        mock_result.new_messages.return_value = [mock_result.messages[-1]]
        mock_result.usage.return_value = MagicMock()
        return mock_result

    import unittest.mock

    with unittest.mock.patch.object(
        manager.research_agent, "run", side_effect=mock_run
    ):
        await manager.run(prompt="Test", deps=manager.research_deps)

    # Count research vs plan prompts
    research_count = 0
    plan_count = 0

    for msg in captured_messages:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, AgentSystemPrompt):
                    if part.agent_mode == AgentType.RESEARCH:
                        research_count += 1
                    elif part.agent_mode == AgentType.PLAN:
                        plan_count += 1

    assert research_count == 2, "Both research prompts should be present"
    assert plan_count == 0, "Plan prompt should be filtered out"
