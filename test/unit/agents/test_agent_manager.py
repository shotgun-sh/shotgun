"""Test agent manager functionality."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import Agent
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.messages import ModelMessage

from shotgun.agents.agent_manager import AgentManager, AgentType, MessageHistoryUpdated
from shotgun.agents.models import AgentDeps


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
    # Add file_tracker mock
    file_tracker_mock = MagicMock()
    file_tracker_mock.clear = MagicMock()
    file_tracker_mock.operations = []
    file_tracker_mock.format_summary = MagicMock(return_value="No files modified")
    deps.file_tracker = file_tracker_mock

    # Add additional fields needed by _create_merged_deps
    llm_model_mock = MagicMock()
    llm_model_mock.provider = "anthropic"  # Set a valid provider for token counting
    deps.llm_model = llm_model_mock
    deps.codebase_service = MagicMock()
    deps.artifact_service = MagicMock()
    deps.system_prompt_fn = MagicMock(return_value="Test system prompt")

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


@pytest.fixture
def mock_agents():
    """Create mock agents."""
    research_agent = MagicMock(spec=Agent)
    plan_agent = MagicMock(spec=Agent)
    tasks_agent = MagicMock(spec=Agent)
    return research_agent, plan_agent, tasks_agent


@patch("shotgun.agents.agent_manager.create_research_agent")
@patch("shotgun.agents.agent_manager.create_plan_agent")
@patch("shotgun.agents.agent_manager.create_tasks_agent")
@patch("shotgun.agents.agent_manager.create_specify_agent")
@patch("shotgun.agents.agent_manager.create_export_agent")
def test_agent_manager_init(
    mock_create_export,
    mock_create_specify,
    mock_create_tasks,
    mock_create_plan,
    mock_create_research,
    mock_agent_deps,
    mock_agents,
):
    """Test AgentManager initialization."""
    research_agent, plan_agent, tasks_agent = mock_agents

    # Mock the create_*_agent functions
    mock_create_research.return_value = (research_agent, mock_agent_deps)
    mock_create_plan.return_value = (plan_agent, mock_agent_deps)
    mock_create_tasks.return_value = (tasks_agent, mock_agent_deps)
    mock_create_specify.return_value = (
        tasks_agent,
        mock_agent_deps,
    )  # Reuse tasks_agent mock
    mock_create_export.return_value = (tasks_agent, mock_agent_deps)

    manager = AgentManager(deps=mock_agent_deps, initial_type=AgentType.RESEARCH)

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


@patch("shotgun.agents.agent_manager.create_research_agent")
@patch("shotgun.agents.agent_manager.create_plan_agent")
@patch("shotgun.agents.agent_manager.create_tasks_agent")
@patch("shotgun.agents.agent_manager.create_specify_agent")
@patch("shotgun.agents.agent_manager.create_export_agent")
def test_agent_manager_current_agent(
    mock_create_export,
    mock_create_specify,
    mock_create_tasks,
    mock_create_plan,
    mock_create_research,
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

    manager = AgentManager(deps=mock_agent_deps, initial_type=AgentType.RESEARCH)
    assert manager.current_agent == research_agent

    manager._current_agent_type = AgentType.PLAN
    assert manager.current_agent == plan_agent

    manager._current_agent_type = AgentType.TASKS
    assert manager.current_agent == tasks_agent


@patch("shotgun.agents.agent_manager.create_research_agent")
@patch("shotgun.agents.agent_manager.create_plan_agent")
@patch("shotgun.agents.agent_manager.create_tasks_agent")
@patch("shotgun.agents.agent_manager.create_specify_agent")
@patch("shotgun.agents.agent_manager.create_export_agent")
def test_agent_manager_get_agent(
    mock_create_export,
    mock_create_specify,
    mock_create_tasks,
    mock_create_plan,
    mock_create_research,
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

    manager = AgentManager(deps=mock_agent_deps)

    assert manager._get_agent(AgentType.RESEARCH) == research_agent
    assert manager._get_agent(AgentType.PLAN) == plan_agent
    assert manager._get_agent(AgentType.TASKS) == tasks_agent


@patch("shotgun.agents.agent_manager.create_research_agent")
@patch("shotgun.agents.agent_manager.create_plan_agent")
@patch("shotgun.agents.agent_manager.create_tasks_agent")
@patch("shotgun.agents.agent_manager.create_specify_agent")
@patch("shotgun.agents.agent_manager.create_export_agent")
def test_agent_manager_set_agent(
    mock_create_export,
    mock_create_specify,
    mock_create_tasks,
    mock_create_plan,
    mock_create_research,
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

    manager = AgentManager(deps=mock_agent_deps, initial_type=AgentType.RESEARCH)

    # Test setting valid agent types
    manager.set_agent(AgentType.PLAN)
    assert manager._current_agent_type == AgentType.PLAN

    manager.set_agent(AgentType.TASKS)
    assert manager._current_agent_type == AgentType.TASKS

    # Test string values
    manager.set_agent("research")
    assert manager._current_agent_type == AgentType.RESEARCH


@patch("shotgun.agents.agent_manager.create_research_agent")
@patch("shotgun.agents.agent_manager.create_plan_agent")
@patch("shotgun.agents.agent_manager.create_tasks_agent")
@patch("shotgun.agents.agent_manager.create_specify_agent")
@patch("shotgun.agents.agent_manager.create_export_agent")
def test_agent_manager_set_agent_invalid(
    mock_create_export,
    mock_create_specify,
    mock_create_tasks,
    mock_create_plan,
    mock_create_research,
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

    manager = AgentManager(deps=mock_agent_deps)

    with pytest.raises(ValueError, match="Invalid agent type: invalid"):
        manager.set_agent("invalid")


@pytest.mark.asyncio
@patch("shotgun.agents.agent_manager.add_system_status_message")
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

    # Mock the agent run method
    mock_result = MagicMock(spec=AgentRunResult)
    mock_result.new_messages.return_value = [MagicMock()]
    mock_result.all_messages.return_value = [MagicMock(), MagicMock()]
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
    assert call_args[1]["deferred_tool_results"] is None
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

    # Verify post_message was called twice (before and after run)
    assert manager.post_message.call_count == 2


@pytest.mark.asyncio
@patch("shotgun.agents.agent_manager.add_system_status_message")
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

    # Mock the agent run method
    mock_result = MagicMock(spec=AgentRunResult)
    mock_result.new_messages.return_value = []
    mock_result.all_messages.return_value = []
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
    # Two post_message calls - one before run, one after (even without prompt)
    assert manager.post_message.call_count == 2


@pytest.mark.asyncio
@patch("shotgun.agents.agent_manager.add_system_status_message")
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

    # Mock the agent run method
    mock_result = MagicMock(spec=AgentRunResult)
    mock_result.new_messages.return_value = []
    mock_result.all_messages.return_value = []
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
    custom_deps.codebase_service = AsyncMock()
    custom_deps.codebase_service.list_graphs.return_value = []
    await manager.run("test", deps=custom_deps)

    # Should use custom deps instead of manager deps
    research_agent.run.assert_called_once()
    call_kwargs = research_agent.run.call_args[1]
    assert call_kwargs["deps"] == custom_deps


@patch("shotgun.agents.agent_manager.create_research_agent")
@patch("shotgun.agents.agent_manager.create_plan_agent")
@patch("shotgun.agents.agent_manager.create_tasks_agent")
@patch("shotgun.agents.agent_manager.create_specify_agent")
@patch("shotgun.agents.agent_manager.create_export_agent")
def test_agent_manager_post_messages_updated(
    mock_create_export,
    mock_create_specify,
    mock_create_tasks,
    mock_create_plan,
    mock_create_research,
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

    manager = AgentManager(deps=mock_agent_deps, initial_type=AgentType.RESEARCH)
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
