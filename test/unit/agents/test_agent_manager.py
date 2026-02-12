"""Test agent manager functionality."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import Agent
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
)

from shotgun.agents.agent_manager import (
    AgentManager,
    AgentType,
    MessageHistoryUpdated,
    ModelConfigUpdated,
)
from shotgun.agents.config.models import KeyProvider, ModelName, ProviderType
from shotgun.agents.conversation import ConversationState
from shotgun.agents.models import AgentDeps, AgentResponse
from shotgun.agents.usage_manager import SessionUsageManager
from shotgun.tui.screens.chat_screen.hint_message import HintMessage


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
    deps.is_tui_context = False
    deps.has_codebase_indexed = False  # Add has_codebase_indexed
    # Add file_tracker mock
    file_tracker_mock = MagicMock()
    file_tracker_mock.clear = MagicMock()
    file_tracker_mock.operations = []
    file_tracker_mock.format_summary = MagicMock(return_value="No files modified")
    deps.file_tracker = file_tracker_mock

    # Add additional fields needed by _create_merged_deps
    llm_model_mock = MagicMock()
    llm_model_mock.provider = (
        ProviderType.ANTHROPIC
    )  # Set a valid provider for token counting
    deps.llm_model = llm_model_mock
    # Use AsyncMock for codebase_service with proper async methods
    deps.codebase_service = AsyncMock()
    deps.codebase_service.list_graphs_for_directory = AsyncMock(return_value=[])
    deps.artifact_service = MagicMock()
    deps.system_prompt_fn = MagicMock(return_value="Test system prompt")

    usage_manager_mock = MagicMock(spec=SessionUsageManager)
    usage_manager_mock.add_usage = AsyncMock()
    usage_manager_mock.build_usage_hint = MagicMock(
        return_value="| Model | Provider | Input | Output | Cached |\n| --- | --- | ---: | ---: | ---: |\n| `test-model` | anthropic | 10 | 5 | 2 |\n| **Total** |  | **10** | **5** | **2** |\n"
    )
    deps.usage_manager = usage_manager_mock

    # Ensure model_copy preserves the llm_model structure
    def mock_model_copy(update=None):
        """Mock model_copy that preserves llm_model structure."""
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
            "has_codebase_indexed",
        ]:
            setattr(copy_mock, attr_name, getattr(deps, attr_name))

        # Apply updates if provided
        if update:
            for key, value in update.items():
                setattr(copy_mock, key, value)

        return copy_mock

    deps.model_copy = mock_model_copy

    return deps


@pytest.fixture
def mock_agents():
    """Create mock agents."""
    research_agent = MagicMock(spec=Agent)
    plan_agent = MagicMock(spec=Agent)
    tasks_agent = MagicMock(spec=Agent)
    return research_agent, plan_agent, tasks_agent


@pytest.mark.asyncio
@patch("shotgun.agents.agent_manager.create_router_agent")
@patch("shotgun.agents.agent_manager.create_research_agent")
@patch("shotgun.agents.agent_manager.create_plan_agent")
@patch("shotgun.agents.agent_manager.create_tasks_agent")
@patch("shotgun.agents.agent_manager.create_specify_agent")
@patch("shotgun.agents.agent_manager.create_export_agent")
async def test_agent_manager_init(
    mock_create_export,
    mock_create_specify,
    mock_create_tasks,
    mock_create_plan,
    mock_create_research,
    mock_create_router,
    mock_agent_deps,
    mock_agents,
):
    """Test AgentManager initialization."""
    research_agent, plan_agent, tasks_agent = mock_agents

    # Mock the create_*_agent functions (create_research_agent is now async)
    mock_create_research.return_value = (research_agent, mock_agent_deps)
    mock_create_plan.return_value = (plan_agent, mock_agent_deps)
    mock_create_tasks.return_value = (tasks_agent, mock_agent_deps)
    mock_create_specify.return_value = (
        tasks_agent,
        mock_agent_deps,
    )  # Reuse tasks_agent mock
    mock_create_export.return_value = (tasks_agent, mock_agent_deps)
    mock_create_router.return_value = (tasks_agent, mock_agent_deps)

    manager = AgentManager(deps=mock_agent_deps, initial_type=AgentType.RESEARCH)

    # Initialize agents (lazy initialization)
    await manager._ensure_agents_initialized()

    assert manager.deps == mock_agent_deps
    assert manager._current_agent_type == AgentType.RESEARCH
    assert manager.research_agent == research_agent
    assert manager.plan_agent == plan_agent
    assert manager.tasks_agent == tasks_agent
    assert manager.ui_message_history == []
    assert manager.message_history == []


@patch("shotgun.agents.agent_manager.create_research_agent")
@patch("shotgun.agents.agent_manager.create_plan_agent")
@patch("shotgun.agents.agent_manager.create_tasks_agent")
@patch("shotgun.agents.agent_manager.create_specify_agent")
def test_agent_manager_init_no_deps(
    mock_create_specify, mock_create_tasks, mock_create_plan, mock_create_research
):
    """Test AgentManager initialization without deps raises ValueError."""
    with pytest.raises(ValueError, match="AgentDeps must be provided"):
        AgentManager(deps=None)


@pytest.mark.asyncio
@patch("shotgun.agents.agent_manager.create_router_agent")
@patch("shotgun.agents.agent_manager.create_research_agent")
@patch("shotgun.agents.agent_manager.create_plan_agent")
@patch("shotgun.agents.agent_manager.create_tasks_agent")
@patch("shotgun.agents.agent_manager.create_specify_agent")
@patch("shotgun.agents.agent_manager.create_export_agent")
async def test_agent_manager_current_agent(
    mock_create_export,
    mock_create_specify,
    mock_create_tasks,
    mock_create_plan,
    mock_create_research,
    mock_create_router,
    mock_agent_deps,
    mock_agents,
):
    """Test current_agent property."""
    research_agent, plan_agent, tasks_agent = mock_agents

    mock_create_research.return_value = (research_agent, mock_agent_deps)
    mock_create_plan.return_value = (plan_agent, mock_agent_deps)
    mock_create_tasks.return_value = (tasks_agent, mock_agent_deps)
    mock_create_specify.return_value = (tasks_agent, mock_agent_deps)
    mock_create_export.return_value = (tasks_agent, mock_agent_deps)
    mock_create_router.return_value = (tasks_agent, mock_agent_deps)

    manager = AgentManager(deps=mock_agent_deps, initial_type=AgentType.RESEARCH)

    # Initialize agents (lazy initialization)
    await manager._ensure_agents_initialized()

    assert manager.current_agent == research_agent

    manager._current_agent_type = AgentType.PLAN
    assert manager.current_agent == plan_agent

    manager._current_agent_type = AgentType.TASKS
    assert manager.current_agent == tasks_agent


@pytest.mark.asyncio
@patch("shotgun.agents.agent_manager.create_router_agent")
@patch("shotgun.agents.agent_manager.create_research_agent")
@patch("shotgun.agents.agent_manager.create_plan_agent")
@patch("shotgun.agents.agent_manager.create_tasks_agent")
@patch("shotgun.agents.agent_manager.create_specify_agent")
@patch("shotgun.agents.agent_manager.create_export_agent")
async def test_agent_manager_get_agent(
    mock_create_export,
    mock_create_specify,
    mock_create_tasks,
    mock_create_plan,
    mock_create_research,
    mock_create_router,
    mock_agent_deps,
    mock_agents,
):
    """Test _get_agent method."""
    research_agent, plan_agent, tasks_agent = mock_agents

    mock_create_research.return_value = (research_agent, mock_agent_deps)
    mock_create_plan.return_value = (plan_agent, mock_agent_deps)
    mock_create_tasks.return_value = (tasks_agent, mock_agent_deps)
    mock_create_specify.return_value = (tasks_agent, mock_agent_deps)
    mock_create_export.return_value = (tasks_agent, mock_agent_deps)
    mock_create_router.return_value = (tasks_agent, mock_agent_deps)

    manager = AgentManager(deps=mock_agent_deps)

    # Initialize agents before accessing them
    await manager._ensure_agents_initialized()

    assert manager._get_agent(AgentType.RESEARCH) == research_agent
    assert manager._get_agent(AgentType.PLAN) == plan_agent
    assert manager._get_agent(AgentType.TASKS) == tasks_agent


@pytest.mark.asyncio
@patch("shotgun.agents.agent_manager.create_router_agent")
@patch("shotgun.agents.agent_manager.create_research_agent")
@patch("shotgun.agents.agent_manager.create_plan_agent")
@patch("shotgun.agents.agent_manager.create_tasks_agent")
@patch("shotgun.agents.agent_manager.create_specify_agent")
@patch("shotgun.agents.agent_manager.create_export_agent")
async def test_agent_manager_set_agent(
    mock_create_export,
    mock_create_specify,
    mock_create_tasks,
    mock_create_plan,
    mock_create_research,
    mock_create_router,
    mock_agent_deps,
    mock_agents,
):
    """Test set_agent method."""
    research_agent, plan_agent, tasks_agent = mock_agents

    mock_create_research.return_value = (research_agent, mock_agent_deps)
    mock_create_plan.return_value = (plan_agent, mock_agent_deps)
    mock_create_tasks.return_value = (tasks_agent, mock_agent_deps)
    mock_create_specify.return_value = (tasks_agent, mock_agent_deps)
    mock_create_export.return_value = (tasks_agent, mock_agent_deps)
    mock_create_router.return_value = (tasks_agent, mock_agent_deps)

    manager = AgentManager(deps=mock_agent_deps, initial_type=AgentType.RESEARCH)

    # Initialize agents
    await manager._ensure_agents_initialized()

    # Test setting valid agent types
    manager.set_agent(AgentType.PLAN)
    assert manager._current_agent_type == AgentType.PLAN

    manager.set_agent(AgentType.TASKS)
    assert manager._current_agent_type == AgentType.TASKS

    # Test string values
    manager.set_agent("research")
    assert manager._current_agent_type == AgentType.RESEARCH


@pytest.mark.asyncio
@patch("shotgun.agents.agent_manager.create_router_agent")
@patch("shotgun.agents.agent_manager.create_research_agent")
@patch("shotgun.agents.agent_manager.create_plan_agent")
@patch("shotgun.agents.agent_manager.create_tasks_agent")
@patch("shotgun.agents.agent_manager.create_specify_agent")
@patch("shotgun.agents.agent_manager.create_export_agent")
async def test_agent_manager_set_agent_invalid(
    mock_create_export,
    mock_create_specify,
    mock_create_tasks,
    mock_create_plan,
    mock_create_research,
    mock_create_router,
    mock_agent_deps,
    mock_agents,
):
    """Test set_agent method with invalid agent type."""
    research_agent, plan_agent, tasks_agent = mock_agents

    mock_create_research.return_value = (research_agent, mock_agent_deps)
    mock_create_plan.return_value = (plan_agent, mock_agent_deps)
    mock_create_tasks.return_value = (tasks_agent, mock_agent_deps)
    mock_create_specify.return_value = (tasks_agent, mock_agent_deps)
    mock_create_export.return_value = (tasks_agent, mock_agent_deps)
    mock_create_router.return_value = (tasks_agent, mock_agent_deps)

    manager = AgentManager(deps=mock_agent_deps)

    # Initialize agents
    await manager._ensure_agents_initialized()

    with pytest.raises(ValueError, match="Invalid agent type: invalid"):
        manager.set_agent("invalid")


@pytest.mark.asyncio
@patch("shotgun.agents.agent_manager.add_system_status_message")
@patch("shotgun.agents.agent_manager.create_router_agent")
@patch("shotgun.agents.agent_manager.create_export_agent")
@patch("shotgun.agents.agent_manager.create_research_agent")
@patch("shotgun.agents.agent_manager.create_plan_agent")
@patch("shotgun.agents.agent_manager.create_tasks_agent")
@patch("shotgun.agents.agent_manager.create_specify_agent")
async def test_agent_manager_run(
    mock_create_specify,
    mock_create_tasks,
    mock_create_plan,
    mock_create_research,
    mock_create_export,
    mock_create_router,
    mock_add_system_status,
    mock_agent_deps,
    mock_agents,
):
    """Test run method."""
    research_agent, plan_agent, tasks_agent = mock_agents

    # Create separate deps for each agent with different system prompt functions
    research_deps = MagicMock(spec=AgentDeps)
    research_deps.system_prompt_fn = MagicMock(return_value="Research system prompt")

    plan_deps = MagicMock(spec=AgentDeps)
    plan_deps.system_prompt_fn = MagicMock(return_value="Plan system prompt")

    tasks_deps = MagicMock(spec=AgentDeps)
    tasks_deps.system_prompt_fn = MagicMock(return_value="Tasks system prompt")

    mock_create_research.return_value = (research_agent, research_deps)
    mock_create_plan.return_value = (plan_agent, plan_deps)
    mock_create_tasks.return_value = (tasks_agent, tasks_deps)
    mock_create_specify.return_value = (tasks_agent, tasks_deps)
    mock_create_export.return_value = (tasks_agent, tasks_deps)
    mock_create_router.return_value = (tasks_agent, tasks_deps)

    # Mock the agent run method
    mock_result = MagicMock(spec=AgentRunResult)
    mock_result.output = AgentResponse(
        response="Test response", clarifying_questions=None
    )
    mock_result.new_messages.return_value = [MagicMock()]
    mock_result.all_messages.return_value = [MagicMock(), MagicMock()]
    mock_result.usage.return_value = MagicMock()
    research_agent.run = AsyncMock(return_value=mock_result)

    # Mock add_system_status_message to return the message history unchanged
    async def mock_add_status(deps, history):
        return history if history else []

    mock_add_system_status.side_effect = mock_add_status

    manager = AgentManager(deps=mock_agent_deps, initial_type=AgentType.RESEARCH)

    # Mock the post_message method
    manager.post_message = MagicMock()

    result = await manager.run("test prompt")

    assert result == mock_result
    # Verify the agent was called with the correct parameters
    # Note: deps will be a merged copy, not the exact same object
    research_agent.run.assert_called_once()
    call_args = research_agent.run.call_args
    assert call_args[0] == ("test prompt",)  # positional args
    assert call_args[1]["usage_limits"] is None
    # Verify system prompt was injected (message_history should have at least 1 system message)
    message_history = call_args[1]["message_history"]
    assert len(message_history) >= 1
    # First message should be a system prompt
    from pydantic_ai.messages import ModelRequest, SystemPromptPart

    assert isinstance(message_history[0], ModelRequest)
    assert len(message_history[0].parts) == 1
    assert isinstance(message_history[0].parts[0], SystemPromptPart)
    assert (
        call_args[1]["event_stream_handler"] is not None
    )  # Streaming should be enabled
    # Verify that a merged deps object was passed (different from the original shared deps)
    passed_deps = call_args[1]["deps"]
    assert (
        passed_deps is not mock_agent_deps
    )  # Should be a merged copy, not the original

    # Verify message history was updated
    assert len(manager.ui_message_history) > 0
    assert len(manager.message_history) == 2

    # Verify post_message was called (for UI updates and compaction messages)
    # 4 calls: 1 initial UI update, 2 for compaction start/complete, 1 final UI update after compaction
    assert manager.post_message.call_count == 4


@pytest.mark.asyncio
@patch("shotgun.agents.agent_manager.add_system_status_message")
@patch("shotgun.agents.agent_manager.create_router_agent")
@patch("shotgun.agents.agent_manager.create_export_agent")
@patch("shotgun.agents.agent_manager.create_research_agent")
@patch("shotgun.agents.agent_manager.create_plan_agent")
@patch("shotgun.agents.agent_manager.create_tasks_agent")
@patch("shotgun.agents.agent_manager.create_specify_agent")
async def test_agent_manager_run_no_prompt(
    mock_create_specify,
    mock_create_tasks,
    mock_create_plan,
    mock_create_research,
    mock_create_export,
    mock_create_router,
    mock_add_system_status,
    mock_agent_deps,
    mock_agents,
):
    """Test run method without prompt."""
    research_agent, plan_agent, tasks_agent = mock_agents

    # Create separate deps for each agent with different system prompt functions
    research_deps = MagicMock(spec=AgentDeps)
    research_deps.system_prompt_fn = MagicMock(return_value="Research system prompt")

    plan_deps = MagicMock(spec=AgentDeps)
    plan_deps.system_prompt_fn = MagicMock(return_value="Plan system prompt")

    tasks_deps = MagicMock(spec=AgentDeps)
    tasks_deps.system_prompt_fn = MagicMock(return_value="Tasks system prompt")

    mock_create_research.return_value = (research_agent, research_deps)
    mock_create_plan.return_value = (plan_agent, plan_deps)
    mock_create_tasks.return_value = (tasks_agent, tasks_deps)
    mock_create_specify.return_value = (tasks_agent, tasks_deps)
    mock_create_export.return_value = (tasks_agent, tasks_deps)
    mock_create_router.return_value = (tasks_agent, tasks_deps)

    # Mock the agent run method
    mock_result = MagicMock(spec=AgentRunResult)
    mock_result.output = AgentResponse(
        response="Test response", clarifying_questions=None
    )
    mock_result.new_messages.return_value = []
    mock_result.all_messages.return_value = []
    mock_result.usage.return_value = MagicMock()
    research_agent.run = AsyncMock(return_value=mock_result)

    # Mock add_system_status_message to return the message history unchanged
    async def mock_add_status(deps, history):
        return history if history else []

    mock_add_system_status.side_effect = mock_add_status

    manager = AgentManager(deps=mock_agent_deps, initial_type=AgentType.RESEARCH)

    # Mock the post_message method
    manager.post_message = MagicMock()

    result = await manager.run()

    assert result == mock_result

    # Verify post_message was called (for UI updates and compaction messages)
    # 4 calls: 1 initial UI update, 2 for compaction start/complete, 1 final UI update after compaction
    assert manager.post_message.call_count == 4


@pytest.mark.asyncio
@patch("shotgun.agents.agent_manager.add_system_status_message")
@patch("shotgun.agents.agent_manager.create_router_agent")
@patch("shotgun.agents.agent_manager.create_research_agent")
@patch("shotgun.agents.agent_manager.create_plan_agent")
@patch("shotgun.agents.agent_manager.create_tasks_agent")
@patch("shotgun.agents.agent_manager.create_specify_agent")
@patch("shotgun.agents.agent_manager.create_export_agent")
async def test_agent_manager_run_with_custom_deps(
    mock_create_export,
    mock_create_specify,
    mock_create_tasks,
    mock_create_plan,
    mock_create_research,
    mock_create_router,
    mock_add_system_status,
    mock_agent_deps,
    mock_agents,
):
    """Test run method with custom deps."""
    research_agent, plan_agent, tasks_agent = mock_agents

    mock_create_research.return_value = (research_agent, mock_agent_deps)
    mock_create_plan.return_value = (plan_agent, mock_agent_deps)
    mock_create_tasks.return_value = (tasks_agent, mock_agent_deps)
    mock_create_specify.return_value = (tasks_agent, mock_agent_deps)
    mock_create_export.return_value = (tasks_agent, mock_agent_deps)
    mock_create_router.return_value = (tasks_agent, mock_agent_deps)

    # Mock the agent run method
    mock_result = MagicMock(spec=AgentRunResult)
    mock_result.output = AgentResponse(
        response="Test response", clarifying_questions=None
    )
    mock_result.new_messages.return_value = []
    mock_result.all_messages.return_value = []
    mock_result.usage.return_value = MagicMock()
    research_agent.run = AsyncMock(return_value=mock_result)

    # Mock add_system_status_message to return the message history unchanged
    async def mock_add_status(deps, history):
        return history if history else []

    mock_add_system_status.side_effect = mock_add_status

    manager = AgentManager(deps=mock_agent_deps, initial_type=AgentType.RESEARCH)

    # Mock the post_message method
    manager.post_message = MagicMock()

    custom_deps = MagicMock(spec=AgentDeps)
    # Add required attributes for custom_deps
    file_tracker_mock = MagicMock()
    file_tracker_mock.clear = MagicMock()
    file_tracker_mock.operations = []
    file_tracker_mock.format_summary = MagicMock(return_value="No files modified")
    custom_deps.file_tracker = file_tracker_mock
    custom_deps.system_prompt_fn = MagicMock(return_value="Custom system prompt")
    custom_deps.is_tui_context = False
    custom_deps.has_codebase_indexed = False
    custom_deps.codebase_service = AsyncMock()
    custom_deps.codebase_service.list_graphs_for_directory = AsyncMock(return_value=[])
    custom_deps.llm_model = MagicMock()
    custom_deps.llm_model.name = "custom-model"
    custom_deps.llm_model.provider = ProviderType.OPENAI
    custom_deps.usage_manager = MagicMock(spec=SessionUsageManager)
    await manager.run("test", deps=custom_deps)

    # Should use custom deps instead of manager deps
    research_agent.run.assert_called_once()
    call_kwargs = research_agent.run.call_args[1]
    assert call_kwargs["deps"] == custom_deps


@pytest.mark.asyncio
@patch("shotgun.agents.agent_manager.create_router_agent")
@patch("shotgun.agents.agent_manager.create_research_agent")
@patch("shotgun.agents.agent_manager.create_plan_agent")
@patch("shotgun.agents.agent_manager.create_tasks_agent")
@patch("shotgun.agents.agent_manager.create_specify_agent")
@patch("shotgun.agents.agent_manager.create_export_agent")
async def test_agent_manager_post_messages_updated(
    mock_create_export,
    mock_create_specify,
    mock_create_tasks,
    mock_create_plan,
    mock_create_research,
    mock_create_router,
    mock_agent_deps,
    mock_agents,
):
    """Test _post_messages_updated method."""
    research_agent, plan_agent, tasks_agent = mock_agents

    mock_create_research.return_value = (research_agent, mock_agent_deps)
    mock_create_plan.return_value = (plan_agent, mock_agent_deps)
    mock_create_tasks.return_value = (tasks_agent, mock_agent_deps)
    mock_create_specify.return_value = (tasks_agent, mock_agent_deps)
    mock_create_export.return_value = (tasks_agent, mock_agent_deps)
    mock_create_router.return_value = (tasks_agent, mock_agent_deps)

    manager = AgentManager(deps=mock_agent_deps, initial_type=AgentType.RESEARCH)

    # Initialize agents
    await manager._ensure_agents_initialized()

    manager.post_message = MagicMock()

    manager._post_messages_updated()

    manager.post_message.assert_called_once()
    call_args = manager.post_message.call_args[0][0]
    assert isinstance(call_args, MessageHistoryUpdated)
    assert call_args.messages == manager.ui_message_history
    assert call_args.agent_type == AgentType.RESEARCH


def test_agent_type_enum():
    """Test AgentType enum."""
    assert AgentType.RESEARCH.value == "research"
    assert AgentType.PLAN.value == "plan"
    assert AgentType.TASKS.value == "tasks"

    # Test enum can be created from string values
    assert AgentType("research") == AgentType.RESEARCH
    assert AgentType("plan") == AgentType.PLAN
    assert AgentType("tasks") == AgentType.TASKS


def test_message_history_updated():
    """Test MessageHistoryUpdated message."""
    messages = [MagicMock(spec=ModelMessage)]
    event = MessageHistoryUpdated(messages, AgentType.RESEARCH)

    assert event.messages == messages
    assert event.agent_type == AgentType.RESEARCH


def test_model_config_updated():
    """Test ModelConfigUpdated message."""
    mock_model_config = MagicMock()
    mock_model_config.provider = ProviderType.ANTHROPIC
    mock_model_config.key_provider = KeyProvider.BYOK

    event = ModelConfigUpdated(
        old_model=ModelName.CLAUDE_OPUS_4_5,
        new_model=ModelName.CLAUDE_SONNET_4_5,
        provider=ProviderType.ANTHROPIC,
        key_provider=KeyProvider.BYOK,
        model_config=mock_model_config,
    )

    assert event.old_model == ModelName.CLAUDE_OPUS_4_5
    assert event.new_model == ModelName.CLAUDE_SONNET_4_5
    assert event.provider == ProviderType.ANTHROPIC
    assert event.key_provider == KeyProvider.BYOK
    assert event.model_config == mock_model_config


def test_model_config_updated_no_old_model():
    """Test ModelConfigUpdated message with no old model (first selection)."""
    mock_model_config = MagicMock()
    mock_model_config.provider = ProviderType.OPENAI
    mock_model_config.key_provider = KeyProvider.SHOTGUN

    event = ModelConfigUpdated(
        old_model=None,
        new_model=ModelName.GPT_5_1,
        provider=ProviderType.OPENAI,
        key_provider=KeyProvider.SHOTGUN,
        model_config=mock_model_config,
    )

    assert event.old_model is None
    assert event.new_model == ModelName.GPT_5_1
    assert event.provider == ProviderType.OPENAI
    assert event.key_provider == KeyProvider.SHOTGUN
    assert event.model_config == mock_model_config


@pytest.mark.asyncio
@patch("shotgun.agents.agent_manager.create_router_agent")
@patch("shotgun.agents.agent_manager.create_export_agent")
@patch("shotgun.agents.agent_manager.create_research_agent")
@patch("shotgun.agents.agent_manager.create_plan_agent")
@patch("shotgun.agents.agent_manager.create_tasks_agent")
@patch("shotgun.agents.agent_manager.create_specify_agent")
async def test_restore_conversation_state_filters_system_prompt(
    mock_create_specify,
    mock_create_tasks,
    mock_create_plan,
    mock_create_research,
    mock_create_export,
    mock_create_router,
    mock_agent_deps,
    mock_agents,
):
    """System messages should remain hidden from the UI after restore."""
    research_agent, plan_agent, tasks_agent = mock_agents

    mock_create_research.return_value = (research_agent, mock_agent_deps)
    mock_create_plan.return_value = (plan_agent, mock_agent_deps)
    mock_create_tasks.return_value = (tasks_agent, mock_agent_deps)
    mock_create_specify.return_value = (tasks_agent, mock_agent_deps)
    mock_create_export.return_value = (tasks_agent, mock_agent_deps)
    mock_create_router.return_value = (tasks_agent, mock_agent_deps)

    manager = AgentManager(deps=mock_agent_deps, initial_type=AgentType.RESEARCH)

    # Initialize agents
    await manager._ensure_agents_initialized()

    system_message = ModelRequest(parts=[SystemPromptPart(content="sys")])
    user_message = ModelRequest.user_text_prompt("Hi")
    response_message = ModelResponse(parts=[TextPart(content="Hello")])
    hint_message = HintMessage(message="Remember to sync docs")

    state = ConversationState(
        agent_messages=[system_message, user_message, response_message],
        ui_messages=[system_message, user_message, response_message, hint_message],
        agent_type="research",
    )

    manager.restore_conversation_state(state)

    # Ensure system message remains available for subsequent runs
    restored_first_message = manager.message_history[0]
    assert any(
        isinstance(part, SystemPromptPart)
        for part in getattr(restored_first_message, "parts", [])
    )

    # UI history should exclude the system prompt entirely
    assert len(manager.ui_message_history) == 3
    assert any(isinstance(msg, HintMessage) for msg in manager.ui_message_history)
    assert all(
        not any(
            isinstance(part, SystemPromptPart) for part in getattr(msg, "parts", [])
        )
        for msg in manager.ui_message_history
        if not isinstance(msg, HintMessage)
    )

    # Hint messages should not appear in the agent message history
    assert all(not isinstance(msg, HintMessage) for msg in manager.message_history)


@pytest.mark.asyncio
@patch("shotgun.agents.agent_manager.add_system_status_message")
@patch("shotgun.agents.agent_manager.create_router_agent")
@patch("shotgun.agents.agent_manager.create_export_agent")
@patch("shotgun.agents.agent_manager.create_research_agent")
@patch("shotgun.agents.agent_manager.create_plan_agent")
@patch("shotgun.agents.agent_manager.create_tasks_agent")
@patch("shotgun.agents.agent_manager.create_specify_agent")
async def test_qa_mode_hint_ordering_with_file_operations(
    mock_create_specify,
    mock_create_tasks,
    mock_create_plan,
    mock_create_research,
    mock_create_export,
    mock_create_router,
    mock_add_system_status,
    mock_agent_deps,
    mock_agents,
):
    """Test that file operation hints appear before QA questions."""
    from shotgun.agents.models import FileOperation, FileOperationType

    research_agent, plan_agent, tasks_agent = mock_agents

    # Add file operations to the shared deps' file_tracker
    mock_agent_deps.file_tracker.operations = [
        FileOperation(
            file_path="/test/file.py",
            operation=FileOperationType.UPDATED,
        )
    ]

    # Create separate deps for each agent
    research_deps = MagicMock(spec=AgentDeps)
    research_deps.system_prompt_fn = MagicMock(return_value="Research system prompt")

    mock_create_research.return_value = (research_agent, research_deps)
    mock_create_plan.return_value = (plan_agent, research_deps)
    mock_create_tasks.return_value = (tasks_agent, research_deps)
    mock_create_specify.return_value = (tasks_agent, research_deps)
    mock_create_export.return_value = (tasks_agent, research_deps)
    mock_create_router.return_value = (tasks_agent, research_deps)

    # Mock the agent run method with clarifying questions
    mock_result = MagicMock(spec=AgentRunResult)
    mock_result.output = AgentResponse(
        response="Initial response",
        clarifying_questions=["Question 1?", "Question 2?"],
    )
    mock_result.new_messages.return_value = [MagicMock()]
    mock_result.all_messages.return_value = [MagicMock(), MagicMock()]
    mock_result.usage.return_value = MagicMock()
    research_agent.run = AsyncMock(return_value=mock_result)

    # Mock add_system_status_message
    async def mock_add_status(deps, history):
        return history if history else []

    mock_add_system_status.side_effect = mock_add_status

    manager = AgentManager(deps=mock_agent_deps, initial_type=AgentType.RESEARCH)
    manager.post_message = MagicMock()

    # Run the agent
    await manager.run("test prompt")

    # Verify UI message history order
    # Expected order:
    # 1. Initial response hint
    # 2. File operation hint (should come before questions)
    # 3. Questions intro
    # 4. Q1
    ui_messages = manager.ui_message_history
    assert len(ui_messages) >= 4

    # Find the file operation hint
    file_hint_idx = None
    for i, msg in enumerate(ui_messages):
        if isinstance(msg, HintMessage) and (
            msg.message.startswith("📝 Modified:")
            or msg.message.startswith("📁 Modified")
        ):
            file_hint_idx = i
            break

    assert file_hint_idx is not None, "File operation hint should be present"

    # Find the first QA question
    q1_idx = None
    for i, msg in enumerate(ui_messages):
        if isinstance(msg, HintMessage) and msg.message.startswith("**Q1:**"):
            q1_idx = i
            break

    assert q1_idx is not None, "Q1 should be present"

    # Verify file hint comes before Q1
    assert file_hint_idx < q1_idx, (
        "File operation hint should appear before first question"
    )


def test_tool_execution_started_message():
    """Test ToolExecutionStartedMessage initialization and attributes."""
    from shotgun.agents.agent_manager import ToolExecutionStartedMessage

    # Test with default spinner text
    msg_default = ToolExecutionStartedMessage()
    assert msg_default.spinner_text == "Processing..."

    # Test with custom spinner text
    msg_custom = ToolExecutionStartedMessage("Pontificating...")
    assert msg_custom.spinner_text == "Pontificating..."


def test_tool_streaming_progress_message():
    """Test ToolStreamingProgressMessage initialization and attributes."""
    from shotgun.agents.agent_manager import ToolStreamingProgressMessage

    msg = ToolStreamingProgressMessage(
        streamed_tokens=150, spinner_text="Ruminating..."
    )
    assert msg.streamed_tokens == 150
    assert msg.spinner_text == "Ruminating..."


def test_partial_stream_state_token_tracking():
    """Test _PartialStreamState tracks token counts and spinner text."""
    from shotgun.agents.agent_manager import _PartialStreamState

    state = _PartialStreamState()

    # Check default values
    assert state.streamed_tokens == 0
    assert state.current_spinner_text == "Processing..."
    assert state.last_reported_tokens == 0

    # Test updating values
    state.streamed_tokens = 100
    state.current_spinner_text = "Contemplating..."
    state.last_reported_tokens = 75

    assert state.streamed_tokens == 100
    assert state.current_spinner_text == "Contemplating..."
    assert state.last_reported_tokens == 75


@pytest.mark.asyncio
@patch("shotgun.agents.agent_manager.add_system_status_message")
@patch("shotgun.agents.agent_manager.create_router_agent")
@patch("shotgun.agents.agent_manager.create_export_agent")
@patch("shotgun.agents.agent_manager.create_research_agent")
@patch("shotgun.agents.agent_manager.create_plan_agent")
@patch("shotgun.agents.agent_manager.create_tasks_agent")
@patch("shotgun.agents.agent_manager.create_specify_agent")
async def test_user_prompt_deduplication_with_different_timestamps(
    mock_create_specify,
    mock_create_tasks,
    mock_create_plan,
    mock_create_research,
    mock_create_export,
    mock_create_router,
    mock_add_system_status,
    mock_agent_deps,
    mock_agents,
):
    """Test that user prompts are deduplicated even when they have different timestamps.

    This tests the fix for the bug where user prompts were shown twice because
    UserPromptPart has a timestamp field that differs between instances,
    causing direct comparison to fail.
    """
    from pydantic_ai.messages import UserPromptPart

    research_agent, plan_agent, tasks_agent = mock_agents

    # Create deps for each agent
    research_deps = MagicMock(spec=AgentDeps)
    research_deps.system_prompt_fn = MagicMock(return_value="Research system prompt")

    mock_create_research.return_value = (research_agent, research_deps)
    mock_create_plan.return_value = (plan_agent, research_deps)
    mock_create_tasks.return_value = (tasks_agent, research_deps)
    mock_create_specify.return_value = (tasks_agent, research_deps)
    mock_create_export.return_value = (tasks_agent, research_deps)
    mock_create_router.return_value = (tasks_agent, research_deps)

    # Create TWO different ModelRequest objects with the same content but different timestamps
    # This simulates what happens when:
    # 1. TUI adds user message to ui_message_history before running agent
    # 2. Agent returns new_messages() which includes another ModelRequest with same content
    user_prompt_content = "Hello, this is my test prompt"

    # Create the user message that the TUI adds first
    tui_user_message = ModelRequest.user_text_prompt(user_prompt_content)

    # Simulate a small time delay, then create another message with the same content
    # (this simulates what pydantic_ai returns from result.new_messages())
    import asyncio

    await asyncio.sleep(0.01)  # Small delay to ensure different timestamp
    agent_user_message = ModelRequest.user_text_prompt(user_prompt_content)

    # Verify the two messages have the same content but different timestamps
    tui_part = next(p for p in tui_user_message.parts if isinstance(p, UserPromptPart))
    agent_part = next(
        p for p in agent_user_message.parts if isinstance(p, UserPromptPart)
    )

    assert tui_part.content == agent_part.content  # Same content
    assert tui_part.timestamp != agent_part.timestamp  # Different timestamps
    # Without the fix, this comparison would have been used and failed:
    assert (
        tui_user_message.parts != agent_user_message.parts
    )  # Direct comparison fails!

    # Mock the agent run method to return the duplicate user message
    mock_result = MagicMock(spec=AgentRunResult)
    mock_result.output = AgentResponse(
        response="Test response", clarifying_questions=None
    )
    # Return a list with the agent's version of the user message plus a response
    agent_response = ModelResponse(parts=[TextPart(content="Hello!")])
    mock_result.new_messages.return_value = [agent_user_message, agent_response]
    mock_result.all_messages.return_value = [agent_user_message, agent_response]
    mock_result.usage.return_value = MagicMock()
    research_agent.run = AsyncMock(return_value=mock_result)

    # Mock add_system_status_message
    async def mock_add_status(deps, history):
        return history if history else []

    mock_add_system_status.side_effect = mock_add_status

    manager = AgentManager(deps=mock_agent_deps, initial_type=AgentType.RESEARCH)
    manager.post_message = MagicMock()

    # Pre-populate ui_message_history with the TUI's version of the user message
    # (simulating what chat_screen.py does before calling run_agent)
    manager.ui_message_history = [tui_user_message]

    # Run the agent
    await manager.run(user_prompt_content)

    # Check that the user message appears only ONCE in ui_message_history
    user_messages = [
        msg
        for msg in manager.ui_message_history
        if isinstance(msg, ModelRequest)
        and any(isinstance(p, UserPromptPart) for p in msg.parts)
    ]

    assert len(user_messages) == 1, (
        f"Expected 1 user message but found {len(user_messages)}. "
        "User prompt deduplication failed - prompts with different timestamps were not detected as duplicates."
    )
