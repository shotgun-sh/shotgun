"""Tests for router agent delegation tools."""

from asyncio import Queue
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.tools import ToolDefinition

from shotgun.agents.config.constants import SUB_AGENT_MAX_OUTPUT_TOKENS
from shotgun.agents.config.models import KeyProvider, ModelConfig, ProviderType
from shotgun.agents.models import (
    AgentResponse,
    AgentType,
    FileOperationTracker,
)
from shotgun.agents.router.models import (
    DelegationInput,
    DelegationResult,
    ExecutionPlan,
    ExecutionStep,
    PendingApproval,
    RouterDeps,
    RouterMode,
)
from shotgun.agents.router.tools.delegation_tools import (
    _build_sub_agent_context,
    _create_agent_runtime_options,
    _get_or_create_sub_agent,
    _is_retryable_error,
    _run_sub_agent,
    delegate_to_export,
    delegate_to_plan,
    delegate_to_research,
    delegate_to_specification,
    delegate_to_tasks,
    prepare_delegation_tool,
)


@pytest.fixture
def mock_router_deps():
    """Create mock RouterDeps for testing.

    Uses DRAFTING mode by default to allow delegation without a plan.
    Tests that verify Planning mode behavior should explicitly set
    router_mode = RouterMode.PLANNING.
    """
    deps = MagicMock(spec=RouterDeps)
    deps.router_mode = RouterMode.DRAFTING  # Default to drafting to allow delegation
    deps.current_plan = None
    deps.file_tracker = FileOperationTracker()
    deps.active_sub_agent = None
    deps.sub_agent_cache = {}
    deps.interactive_mode = True
    deps.working_directory = Path("/test/dir")
    deps.is_tui_context = True
    deps.max_iterations = 100
    deps.queue = Queue()  # Must be a Queue instance
    deps.tasks = []
    deps.parent_stream_handler = None  # For streaming support
    deps.pending_approval = None  # No pending approval by default
    deps.cancellation_event = None  # For ESC cancellation support
    deps.usage_manager = MagicMock()
    deps.usage_manager.add_usage = AsyncMock()
    # Create a real ModelConfig for sub-agent inheritance testing
    deps.llm_model = ModelConfig(
        name="test-model",
        provider=ProviderType.OPENAI_COMPATIBLE,
        key_provider=KeyProvider.BYOK,
        max_input_tokens=128000,
        max_output_tokens=16000,
        api_key="test-key",
    )
    return deps


@pytest.fixture
def mock_context(mock_router_deps):
    """Create mock run context for testing."""
    ctx = MagicMock(spec=RunContext)
    ctx.deps = mock_router_deps
    return ctx


@pytest.fixture
def sample_plan():
    """Create a sample execution plan for testing."""
    return ExecutionPlan(
        goal="Implement OAuth",
        steps=[
            ExecutionStep(
                id="step-1", title="Research OAuth", objective="Find best practices"
            ),
            ExecutionStep(
                id="step-2", title="Write spec", objective="Create specification"
            ),
        ],
        current_step_index=0,
    )


@pytest.fixture
def mock_agent_result():
    """Create a mock agent run result."""
    result = MagicMock(spec=AgentRunResult)
    result.output = AgentResponse(
        response="Task completed successfully",
        clarifying_questions=[],
    )
    return result


# =============================================================================
# Tests for _is_retryable_error
# =============================================================================


def test_is_retryable_error_value_error_eof():
    """Test that EOF parsing errors are retryable."""
    error = ValueError("EOF while parsing")
    assert _is_retryable_error(error) is True


def test_is_retryable_error_value_error_json():
    """Test that JSON parsing errors are retryable."""
    error = ValueError("JSON parsing error")
    assert _is_retryable_error(error) is True


def test_is_retryable_error_non_retryable():
    """Test that generic errors are not retryable."""
    error = ValueError("Something else went wrong")
    assert _is_retryable_error(error) is False


def test_is_retryable_error_key_error():
    """Test that KeyError is not retryable."""
    error = KeyError("missing key")
    assert _is_retryable_error(error) is False


# =============================================================================
# Tests for _create_agent_runtime_options
# =============================================================================


def test_create_agent_runtime_options_openai_compatible_inherits_model(
    mock_router_deps,
):
    """Test that OPENAI_COMPATIBLE provider inherits model config for sub-agents."""
    # Fixture default is OPENAI_COMPATIBLE
    assert mock_router_deps.llm_model.provider == ProviderType.OPENAI_COMPATIBLE

    options = _create_agent_runtime_options(mock_router_deps)

    assert options.interactive_mode == mock_router_deps.interactive_mode
    assert options.working_directory == mock_router_deps.working_directory
    assert options.is_tui_context == mock_router_deps.is_tui_context
    assert options.max_iterations == mock_router_deps.max_iterations
    # OPENAI_COMPATIBLE should inherit model config (can't resolve via get_provider_model)
    assert options.inherited_model_config == mock_router_deps.llm_model


def test_create_agent_runtime_options_anthropic_does_not_inherit_model(
    mock_router_deps,
):
    """Test that ANTHROPIC provider does NOT inherit model config, allowing sub-agent substitution."""
    mock_router_deps.llm_model = ModelConfig(
        name="claude-sonnet-4-5",
        provider=ProviderType.ANTHROPIC,
        key_provider=KeyProvider.BYOK,
        max_input_tokens=200000,
        max_output_tokens=16000,
        api_key="test-key",
    )

    options = _create_agent_runtime_options(mock_router_deps)

    # Standard providers should NOT inherit so get_provider_model(for_sub_agent=True) applies
    assert options.inherited_model_config is None


# =============================================================================
# Tests for _build_sub_agent_context
# =============================================================================


def test_build_sub_agent_context_no_plan(mock_router_deps):
    """Test building context when no plan exists."""
    mock_router_deps.current_plan = None

    context = _build_sub_agent_context(mock_router_deps)

    assert context.is_router_delegated is True
    assert context.plan_goal == ""
    assert context.current_step_id == ""
    assert context.current_step_title == ""


def test_build_sub_agent_context_with_plan(mock_router_deps, sample_plan):
    """Test building context with an active plan."""
    mock_router_deps.current_plan = sample_plan

    context = _build_sub_agent_context(mock_router_deps)

    assert context.is_router_delegated is True
    assert context.plan_goal == "Implement OAuth"
    assert context.current_step_id == "step-1"
    assert context.current_step_title == "Research OAuth"


# =============================================================================
# Tests for _get_or_create_sub_agent
# =============================================================================


@pytest.mark.asyncio
async def test_get_or_create_sub_agent_cached(mock_router_deps):
    """Test that cached agents are returned."""
    mock_agent = MagicMock()
    mock_deps = MagicMock()
    mock_router_deps.sub_agent_cache = {AgentType.RESEARCH: (mock_agent, mock_deps)}

    agent, deps = await _get_or_create_sub_agent(mock_router_deps, AgentType.RESEARCH)

    assert agent is mock_agent
    assert deps is mock_deps


@pytest.mark.asyncio
async def test_get_or_create_sub_agent_creates_new(mock_router_deps):
    """Test that new agents are created when not cached."""
    mock_router_deps.sub_agent_cache = {}
    mock_agent = MagicMock()
    mock_deps = MagicMock()

    with patch.dict(
        "shotgun.agents.router.tools.delegation_tools.AGENT_FACTORIES",
        {
            AgentType.RESEARCH: (
                AsyncMock(return_value=(mock_agent, mock_deps)),
                AsyncMock(),
            )
        },
    ):
        agent, deps = await _get_or_create_sub_agent(
            mock_router_deps, AgentType.RESEARCH
        )

    assert agent is mock_agent
    assert deps is mock_deps
    # Should be cached now
    assert AgentType.RESEARCH in mock_router_deps.sub_agent_cache


@pytest.mark.asyncio
async def test_get_or_create_sub_agent_unsupported_type(mock_router_deps):
    """Test that unsupported agent types raise ValueError."""
    with pytest.raises(ValueError, match="not supported for delegation"):
        await _get_or_create_sub_agent(mock_router_deps, AgentType.ROUTER)


# =============================================================================
# Tests for _run_sub_agent
# =============================================================================


def _create_mock_sub_agent_deps():
    """Helper to create properly configured mock sub-agent deps."""
    mock_sub_deps = MagicMock()
    # Create a real FileOperationTracker
    mock_sub_deps.file_tracker = FileOperationTracker()
    mock_sub_deps.sub_agent_context = None
    return mock_sub_deps


@pytest.mark.asyncio
async def test_run_sub_agent_success(mock_context, mock_agent_result):
    """Test successful sub-agent execution."""
    mock_agent = MagicMock()
    mock_sub_deps = _create_mock_sub_agent_deps()
    mock_context.deps.sub_agent_cache = {}

    # The run function will add a file operation during execution
    async def mock_run_with_file_op(*args, **kwargs):
        # Simulate sub-agent modifying a file
        mock_sub_deps.file_tracker.add_operation("/test/file.md", "created")
        return mock_agent_result

    with patch.dict(
        "shotgun.agents.router.tools.delegation_tools.AGENT_FACTORIES",
        {
            AgentType.RESEARCH: (
                AsyncMock(return_value=(mock_agent, mock_sub_deps)),
                mock_run_with_file_op,
            )
        },
    ):
        result = await _run_sub_agent(
            mock_context,
            AgentType.RESEARCH,
            "Find OAuth best practices",
            "Focus on security",
        )

    assert result.success is True
    assert result.response == "Task completed successfully"
    # File path is resolved to absolute, just check it was tracked
    assert len(result.files_modified) == 1
    assert result.error is None
    # active_sub_agent should be cleared after completion
    assert mock_context.deps.active_sub_agent is None


@pytest.mark.asyncio
async def test_prepare_delegation_tool_hidden_when_no_plan_in_planning_mode(
    mock_context,
):
    """Test that delegation tools are hidden in Planning mode when no plan exists."""
    mock_context.deps.router_mode = RouterMode.PLANNING
    mock_context.deps.current_plan = None
    mock_context.deps.pending_approval = None

    tool_def = ToolDefinition(name="delegate_to_research")

    # Tool should be hidden (prepare returns None)
    result = await prepare_delegation_tool(mock_context, tool_def)
    assert result is None


@pytest.mark.asyncio
async def test_prepare_delegation_tool_hidden_when_pending_approval(
    mock_context, sample_plan
):
    """Test that delegation tools are hidden when pending approval is set."""
    mock_context.deps.router_mode = RouterMode.PLANNING
    mock_context.deps.current_plan = sample_plan
    mock_context.deps.pending_approval = PendingApproval(plan=sample_plan)

    tool_def = ToolDefinition(name="delegate_to_research")

    # Tool should be hidden (prepare returns None)
    result = await prepare_delegation_tool(mock_context, tool_def)
    assert result is None


@pytest.mark.asyncio
async def test_prepare_delegation_tool_visible_when_plan_approved(
    mock_context, sample_plan
):
    """Test that delegation tools are visible when plan is approved."""
    mock_context.deps.router_mode = RouterMode.PLANNING
    mock_context.deps.current_plan = sample_plan
    mock_context.deps.pending_approval = None  # Approved

    tool_def = ToolDefinition(name="delegate_to_research")

    # Tool should be visible (prepare returns tool_def)
    result = await prepare_delegation_tool(mock_context, tool_def)
    assert result is tool_def


@pytest.mark.asyncio
async def test_prepare_delegation_tool_always_visible_in_drafting_mode(mock_context):
    """Test that delegation tools are always visible in Drafting mode."""
    mock_context.deps.router_mode = RouterMode.DRAFTING
    mock_context.deps.current_plan = None  # No plan
    mock_context.deps.pending_approval = None

    tool_def = ToolDefinition(name="delegate_to_research")

    # Tool should be visible in Drafting mode regardless of plan state
    result = await prepare_delegation_tool(mock_context, tool_def)
    assert result is tool_def


@pytest.mark.asyncio
async def test_run_sub_agent_sets_active_sub_agent(mock_context, mock_agent_result):
    """Test that active_sub_agent is set during execution."""
    mock_agent = MagicMock()
    mock_sub_deps = _create_mock_sub_agent_deps()
    mock_context.deps.sub_agent_cache = {}
    active_agent_during_run = None

    async def capture_active_agent(*args, **kwargs):
        nonlocal active_agent_during_run
        active_agent_during_run = mock_context.deps.active_sub_agent
        return mock_agent_result

    with patch.dict(
        "shotgun.agents.router.tools.delegation_tools.AGENT_FACTORIES",
        {
            AgentType.RESEARCH: (
                AsyncMock(return_value=(mock_agent, mock_sub_deps)),
                capture_active_agent,
            )
        },
    ):
        await _run_sub_agent(mock_context, AgentType.RESEARCH, "Test task")

    assert active_agent_during_run == AgentType.RESEARCH


@pytest.mark.asyncio
async def test_run_sub_agent_error_non_retryable(mock_context):
    """Test that non-retryable errors return failure immediately."""
    mock_agent = MagicMock()
    mock_sub_deps = _create_mock_sub_agent_deps()
    mock_context.deps.sub_agent_cache = {}

    async def raise_error(*args, **kwargs):
        raise RuntimeError("Something broke")

    with patch.dict(
        "shotgun.agents.router.tools.delegation_tools.AGENT_FACTORIES",
        {
            AgentType.RESEARCH: (
                AsyncMock(return_value=(mock_agent, mock_sub_deps)),
                raise_error,
            )
        },
    ):
        result = await _run_sub_agent(mock_context, AgentType.RESEARCH, "Test task")

    assert result.success is False
    assert "Something broke" in result.error
    assert mock_context.deps.active_sub_agent is None


@pytest.mark.asyncio
async def test_run_sub_agent_error_retries(mock_context, mock_agent_result):
    """Test that retryable errors are retried."""
    mock_agent = MagicMock()
    mock_sub_deps = _create_mock_sub_agent_deps()
    mock_context.deps.sub_agent_cache = {}
    call_count = 0

    async def fail_then_succeed(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ValueError("EOF while parsing")  # Retryable
        return mock_agent_result

    with patch.dict(
        "shotgun.agents.router.tools.delegation_tools.AGENT_FACTORIES",
        {
            AgentType.RESEARCH: (
                AsyncMock(return_value=(mock_agent, mock_sub_deps)),
                fail_then_succeed,
            )
        },
    ):
        result = await _run_sub_agent(mock_context, AgentType.RESEARCH, "Test task")

    assert result.success is True
    assert call_count == 2  # First call failed, second succeeded


@pytest.mark.asyncio
async def test_run_sub_agent_with_clarifying_questions(mock_context):
    """Test that clarifying questions are extracted from result."""
    mock_agent = MagicMock()
    mock_sub_deps = _create_mock_sub_agent_deps()
    mock_context.deps.sub_agent_cache = {}

    result_with_questions = MagicMock(spec=AgentRunResult)
    result_with_questions.output = AgentResponse(
        response="I need more info",
        clarifying_questions=["What is the scope?", "What about edge cases?"],
    )

    with patch.dict(
        "shotgun.agents.router.tools.delegation_tools.AGENT_FACTORIES",
        {
            AgentType.RESEARCH: (
                AsyncMock(return_value=(mock_agent, mock_sub_deps)),
                AsyncMock(return_value=result_with_questions),
            )
        },
    ):
        result = await _run_sub_agent(mock_context, AgentType.RESEARCH, "Test task")

    assert result.success is True
    assert result.has_questions is True
    assert len(result.questions) == 2
    assert "What is the scope?" in result.questions


@pytest.mark.asyncio
async def test_run_sub_agent_passes_sub_agent_context(mock_context, mock_agent_result):
    """Test that SubAgentContext is passed to sub-agent deps."""
    mock_agent = MagicMock()
    mock_sub_deps = _create_mock_sub_agent_deps()
    mock_context.deps.sub_agent_cache = {}
    mock_context.deps.current_plan = ExecutionPlan(
        goal="Test Goal",
        steps=[ExecutionStep(id="s1", title="Step 1", objective="Obj 1")],
    )

    with patch.dict(
        "shotgun.agents.router.tools.delegation_tools.AGENT_FACTORIES",
        {
            AgentType.RESEARCH: (
                AsyncMock(return_value=(mock_agent, mock_sub_deps)),
                AsyncMock(return_value=mock_agent_result),
            )
        },
    ):
        await _run_sub_agent(mock_context, AgentType.RESEARCH, "Test task")

    # Check that sub_agent_context was set
    assert mock_sub_deps.sub_agent_context is not None
    assert mock_sub_deps.sub_agent_context.is_router_delegated is True
    assert mock_sub_deps.sub_agent_context.plan_goal == "Test Goal"


# =============================================================================
# Tests for delegation tool wrappers
# =============================================================================


@pytest.mark.asyncio
async def test_delegate_to_research(mock_context, mock_agent_result):
    """Test delegate_to_research calls _run_sub_agent correctly."""
    with patch(
        "shotgun.agents.router.tools.delegation_tools._run_sub_agent",
        new_callable=AsyncMock,
        return_value=DelegationResult(success=True, response="Research done"),
    ) as mock_run:
        input_data = DelegationInput(task="Find OAuth docs", context_hint="Security")
        result = await delegate_to_research(mock_context, input_data)

    mock_run.assert_called_once_with(
        mock_context, AgentType.RESEARCH, "Find OAuth docs", "Security"
    )
    assert result.success is True


@pytest.mark.asyncio
async def test_delegate_to_specification(mock_context, mock_agent_result):
    """Test delegate_to_specification calls _run_sub_agent correctly."""
    with patch(
        "shotgun.agents.router.tools.delegation_tools._run_sub_agent",
        new_callable=AsyncMock,
        return_value=DelegationResult(success=True, response="Spec done"),
    ) as mock_run:
        input_data = DelegationInput(task="Write auth spec")
        result = await delegate_to_specification(mock_context, input_data)

    mock_run.assert_called_once_with(
        mock_context, AgentType.SPECIFY, "Write auth spec", None
    )
    assert result.success is True


@pytest.mark.asyncio
async def test_delegate_to_plan(mock_context, mock_agent_result):
    """Test delegate_to_plan calls _run_sub_agent correctly."""
    with patch(
        "shotgun.agents.router.tools.delegation_tools._run_sub_agent",
        new_callable=AsyncMock,
        return_value=DelegationResult(success=True, response="Plan done"),
    ) as mock_run:
        input_data = DelegationInput(task="Create implementation plan")
        result = await delegate_to_plan(mock_context, input_data)

    mock_run.assert_called_once_with(
        mock_context, AgentType.PLAN, "Create implementation plan", None
    )
    assert result.success is True


@pytest.mark.asyncio
async def test_delegate_to_tasks(mock_context, mock_agent_result):
    """Test delegate_to_tasks calls _run_sub_agent correctly."""
    with patch(
        "shotgun.agents.router.tools.delegation_tools._run_sub_agent",
        new_callable=AsyncMock,
        return_value=DelegationResult(success=True, response="Tasks done"),
    ) as mock_run:
        input_data = DelegationInput(task="Generate task list")
        result = await delegate_to_tasks(mock_context, input_data)

    mock_run.assert_called_once_with(
        mock_context, AgentType.TASKS, "Generate task list", None
    )
    assert result.success is True


@pytest.mark.asyncio
async def test_delegate_to_export(mock_context, mock_agent_result):
    """Test delegate_to_export calls _run_sub_agent correctly."""
    with patch(
        "shotgun.agents.router.tools.delegation_tools._run_sub_agent",
        new_callable=AsyncMock,
        return_value=DelegationResult(success=True, response="Export done"),
    ) as mock_run:
        input_data = DelegationInput(task="Export deliverables")
        result = await delegate_to_export(mock_context, input_data)

    mock_run.assert_called_once_with(
        mock_context, AgentType.EXPORT, "Export deliverables", None
    )
    assert result.success is True


# =============================================================================
# Tests for sub-agent caching
# =============================================================================


@pytest.mark.asyncio
async def test_sub_agent_cached_after_first_use(mock_context, mock_agent_result):
    """Test that sub-agents are cached after creation."""
    mock_agent = MagicMock()
    mock_sub_deps = _create_mock_sub_agent_deps()
    mock_context.deps.sub_agent_cache = {}
    create_call_count = 0

    async def mock_create_fn(*args, **kwargs):
        nonlocal create_call_count
        create_call_count += 1
        return (mock_agent, mock_sub_deps)

    with patch.dict(
        "shotgun.agents.router.tools.delegation_tools.AGENT_FACTORIES",
        {
            AgentType.RESEARCH: (
                mock_create_fn,
                AsyncMock(return_value=mock_agent_result),
            )
        },
    ):
        # First call - should create agent
        await _run_sub_agent(mock_context, AgentType.RESEARCH, "Task 1")
        assert create_call_count == 1
        assert AgentType.RESEARCH in mock_context.deps.sub_agent_cache

        # Second call - should reuse cached agent
        await _run_sub_agent(mock_context, AgentType.RESEARCH, "Task 2")
        assert create_call_count == 1  # Still 1 - no new creation


# =============================================================================
# Tests for streaming support (Stage 10)
# =============================================================================


@pytest.mark.asyncio
async def test_run_sub_agent_passes_stream_handler(mock_context, mock_agent_result):
    """Test that parent_stream_handler is passed to sub-agent run function."""
    mock_agent = MagicMock()
    mock_sub_deps = _create_mock_sub_agent_deps()
    mock_context.deps.sub_agent_cache = {}

    # Set up a mock stream handler
    mock_stream_handler = AsyncMock()
    mock_context.deps.parent_stream_handler = mock_stream_handler

    captured_kwargs = {}

    async def capture_run_kwargs(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return mock_agent_result

    with patch.dict(
        "shotgun.agents.router.tools.delegation_tools.AGENT_FACTORIES",
        {
            AgentType.RESEARCH: (
                AsyncMock(return_value=(mock_agent, mock_sub_deps)),
                capture_run_kwargs,
            )
        },
    ):
        await _run_sub_agent(mock_context, AgentType.RESEARCH, "Test task")

    # Verify that the event_stream_handler was passed
    assert "event_stream_handler" in captured_kwargs
    assert captured_kwargs["event_stream_handler"] is mock_stream_handler


@pytest.mark.asyncio
async def test_run_sub_agent_none_stream_handler(mock_context, mock_agent_result):
    """Test that None stream handler is passed when not set."""
    mock_agent = MagicMock()
    mock_sub_deps = _create_mock_sub_agent_deps()
    mock_context.deps.sub_agent_cache = {}
    mock_context.deps.parent_stream_handler = None

    captured_kwargs = {}

    async def capture_run_kwargs(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return mock_agent_result

    with patch.dict(
        "shotgun.agents.router.tools.delegation_tools.AGENT_FACTORIES",
        {
            AgentType.RESEARCH: (
                AsyncMock(return_value=(mock_agent, mock_sub_deps)),
                capture_run_kwargs,
            )
        },
    ):
        await _run_sub_agent(mock_context, AgentType.RESEARCH, "Test task")

    # Verify that event_stream_handler was passed but is None
    assert "event_stream_handler" in captured_kwargs
    assert captured_kwargs["event_stream_handler"] is None


# =============================================================================
# Tests for sub-agent usage tracking
# =============================================================================


@pytest.mark.asyncio
async def test_run_sub_agent_tracks_usage(mock_context, mock_agent_result):
    """Test that sub-agent usage is tracked via usage_manager after delegation."""
    mock_agent = MagicMock()
    mock_sub_deps = _create_mock_sub_agent_deps()
    mock_sub_deps.llm_model = ModelConfig(
        name="claude-haiku-4-5",
        provider=ProviderType.ANTHROPIC,
        key_provider=KeyProvider.BYOK,
        max_input_tokens=200000,
        max_output_tokens=8192,
        api_key="test-key",
    )
    mock_context.deps.sub_agent_cache = {}

    # Set up a real RunUsage on the mock result
    expected_usage = RunUsage(input_tokens=100, output_tokens=50, cache_read_tokens=10)
    mock_agent_result.usage.return_value = expected_usage

    with patch.dict(
        "shotgun.agents.router.tools.delegation_tools.AGENT_FACTORIES",
        {
            AgentType.RESEARCH: (
                AsyncMock(return_value=(mock_agent, mock_sub_deps)),
                AsyncMock(return_value=mock_agent_result),
            )
        },
    ):
        result = await _run_sub_agent(mock_context, AgentType.RESEARCH, "Test task")

    assert result.success is True
    mock_context.deps.usage_manager.add_usage.assert_awaited_once_with(
        expected_usage,
        model_name="claude-haiku-4-5",
        provider=ProviderType.ANTHROPIC,
    )


# =============================================================================
# Tests for sub-agent output token limit
# =============================================================================


@pytest.mark.asyncio
async def test_run_sub_agent_passes_model_settings_with_token_limit(
    mock_context, mock_agent_result
):
    """Test that sub-agents receive model_settings with max_tokens limit."""
    mock_agent = MagicMock()
    mock_sub_deps = _create_mock_sub_agent_deps()
    mock_context.deps.sub_agent_cache = {}

    captured_kwargs = {}

    async def capture_run_kwargs(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return mock_agent_result

    with patch.dict(
        "shotgun.agents.router.tools.delegation_tools.AGENT_FACTORIES",
        {
            AgentType.RESEARCH: (
                AsyncMock(return_value=(mock_agent, mock_sub_deps)),
                capture_run_kwargs,
            )
        },
    ):
        await _run_sub_agent(mock_context, AgentType.RESEARCH, "Test task")

    assert "model_settings" in captured_kwargs
    assert (
        captured_kwargs["model_settings"]["max_tokens"] == SUB_AGENT_MAX_OUTPUT_TOKENS
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "agent_type",
    [
        AgentType.RESEARCH,
        AgentType.SPECIFY,
        AgentType.PLAN,
        AgentType.TASKS,
        AgentType.EXPORT,
    ],
)
async def test_all_sub_agents_receive_token_limit(
    mock_context, mock_agent_result, agent_type
):
    """Test that all sub-agent types receive the output token limit."""
    mock_agent = MagicMock()
    mock_sub_deps = _create_mock_sub_agent_deps()
    mock_context.deps.sub_agent_cache = {}

    captured_kwargs = {}

    async def capture_run_kwargs(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return mock_agent_result

    with patch.dict(
        "shotgun.agents.router.tools.delegation_tools.AGENT_FACTORIES",
        {
            agent_type: (
                AsyncMock(return_value=(mock_agent, mock_sub_deps)),
                capture_run_kwargs,
            )
        },
    ):
        await _run_sub_agent(mock_context, agent_type, "Test task")

    assert (
        captured_kwargs["model_settings"]["max_tokens"] == SUB_AGENT_MAX_OUTPUT_TOKENS
    )


@pytest.mark.asyncio
async def test_sub_agent_token_limit_is_4096():
    """Test that the sub-agent token limit constant is 4096."""
    assert SUB_AGENT_MAX_OUTPUT_TOKENS == 4096
