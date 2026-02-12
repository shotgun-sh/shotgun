"""Tests for router agent PostHog metrics."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import RunContext

from shotgun.agents.models import (
    AgentDeps,
    AgentResponse,
    AgentType,
    FileOperationTracker,
)
from shotgun.agents.router.models import (
    AddStepInput,
    CreatePlanInput,
    ExecutionPlan,
    ExecutionStep,
    ExecutionStepInput,
    MarkStepDoneInput,
    RemoveStepInput,
    RouterDeps,
    RouterMode,
)
from shotgun.agents.router.tools.delegation_tools import _run_sub_agent
from shotgun.agents.router.tools.plan_tools import (
    add_step,
    create_plan,
    mark_step_done,
    remove_step,
)


@pytest.fixture
def mock_router_deps():
    """Create a mock RouterDeps for testing."""
    deps = MagicMock(spec=RouterDeps)
    deps.router_mode = RouterMode.PLANNING
    deps.current_plan = None
    deps.pending_approval = None
    deps.approval_status = None
    deps.is_executing = False
    deps.on_plan_changed = None
    return deps


@pytest.fixture
def mock_ctx(mock_router_deps):
    """Create a mock RunContext with RouterDeps."""
    ctx = MagicMock(spec=RunContext)
    ctx.deps = mock_router_deps
    return ctx


@pytest.mark.asyncio
async def test_plan_created_metric(mock_ctx):
    """Test that plan_created metric is tracked when creating a plan."""
    with patch(
        "shotgun.agents.router.tools.plan_tools.track_event"
    ) as mock_track_event:
        input_data = CreatePlanInput(
            goal="Test goal for the plan",
            steps=[
                ExecutionStepInput(id="step-1", title="Step 1", objective="Do step 1"),
                ExecutionStepInput(id="step-2", title="Step 2", objective="Do step 2"),
            ],
        )

        await create_plan(mock_ctx, input_data)

        mock_track_event.assert_called_once_with(
            "plan_created",
            {
                "step_count": 2,
                "goal_preview": "Test goal for the plan",
                "requires_approval": True,
                "router_mode": "planning",
            },
        )


@pytest.mark.asyncio
async def test_plan_step_completed_metric(mock_ctx):
    """Test that plan_step_completed metric is tracked when marking a step done."""
    # Set up a plan with steps
    mock_ctx.deps.current_plan = ExecutionPlan(
        goal="Test goal",
        steps=[
            ExecutionStep(
                id="step-1", title="Step 1", objective="Do step 1", done=False
            ),
            ExecutionStep(
                id="step-2", title="Step 2", objective="Do step 2", done=False
            ),
        ],
        current_step_index=0,
    )

    with patch(
        "shotgun.agents.router.tools.plan_tools.track_event"
    ) as mock_track_event:
        input_data = MarkStepDoneInput(step_id="step-1")

        await mark_step_done(mock_ctx, input_data)

        mock_track_event.assert_called_once_with(
            "plan_step_completed",
            {
                "step_position": 1,
                "total_steps": 2,
                "steps_remaining": 1,
            },
        )


@pytest.mark.asyncio
async def test_plan_completed_metric(mock_ctx):
    """Test that plan_completed metric is tracked when all steps are done."""
    # Set up a plan with one step remaining
    mock_ctx.deps.current_plan = ExecutionPlan(
        goal="Test goal",
        steps=[
            ExecutionStep(
                id="step-1", title="Step 1", objective="Do step 1", done=True
            ),
            ExecutionStep(
                id="step-2", title="Step 2", objective="Do step 2", done=False
            ),
        ],
        current_step_index=1,
    )

    with patch(
        "shotgun.agents.router.tools.plan_tools.track_event"
    ) as mock_track_event:
        input_data = MarkStepDoneInput(step_id="step-2")

        await mark_step_done(mock_ctx, input_data)

        # Should have two calls: plan_step_completed and plan_completed
        assert mock_track_event.call_count == 2

        # Check plan_step_completed call
        first_call = mock_track_event.call_args_list[0]
        assert first_call[0][0] == "plan_step_completed"
        assert first_call[0][1]["step_position"] == 2
        assert first_call[0][1]["steps_remaining"] == 0

        # Check plan_completed call
        second_call = mock_track_event.call_args_list[1]
        assert second_call[0][0] == "plan_completed"
        assert second_call[0][1]["step_count"] == 2


@pytest.mark.asyncio
async def test_plan_step_added_metric_append(mock_ctx):
    """Test that plan_step_added metric is tracked when appending a step."""
    mock_ctx.deps.current_plan = ExecutionPlan(
        goal="Test goal",
        steps=[
            ExecutionStep(
                id="step-1", title="Step 1", objective="Do step 1", done=False
            ),
        ],
        current_step_index=0,
    )

    with patch(
        "shotgun.agents.router.tools.plan_tools.track_event"
    ) as mock_track_event:
        input_data = AddStepInput(
            step=ExecutionStepInput(id="step-2", title="Step 2", objective="Do step 2"),
            after_step_id=None,  # Append to end
        )

        await add_step(mock_ctx, input_data)

        mock_track_event.assert_called_once_with(
            "plan_step_added",
            {
                "new_step_count": 2,
                "position": 2,
            },
        )


@pytest.mark.asyncio
async def test_plan_step_added_metric_insert(mock_ctx):
    """Test that plan_step_added metric is tracked when inserting a step."""
    mock_ctx.deps.current_plan = ExecutionPlan(
        goal="Test goal",
        steps=[
            ExecutionStep(
                id="step-1", title="Step 1", objective="Do step 1", done=False
            ),
            ExecutionStep(
                id="step-3", title="Step 3", objective="Do step 3", done=False
            ),
        ],
        current_step_index=0,
    )

    with patch(
        "shotgun.agents.router.tools.plan_tools.track_event"
    ) as mock_track_event:
        input_data = AddStepInput(
            step=ExecutionStepInput(id="step-2", title="Step 2", objective="Do step 2"),
            after_step_id="step-1",  # Insert after step-1
        )

        await add_step(mock_ctx, input_data)

        mock_track_event.assert_called_once_with(
            "plan_step_added",
            {
                "new_step_count": 3,
                "position": 2,
            },
        )


@pytest.mark.asyncio
async def test_plan_step_removed_metric(mock_ctx):
    """Test that plan_step_removed metric is tracked when removing a step."""
    mock_ctx.deps.current_plan = ExecutionPlan(
        goal="Test goal",
        steps=[
            ExecutionStep(
                id="step-1", title="Step 1", objective="Do step 1", done=False
            ),
            ExecutionStep(
                id="step-2", title="Step 2", objective="Do step 2", done=False
            ),
        ],
        current_step_index=0,
    )

    with patch(
        "shotgun.agents.router.tools.plan_tools.track_event"
    ) as mock_track_event:
        input_data = RemoveStepInput(step_id="step-2")

        await remove_step(mock_ctx, input_data)

        mock_track_event.assert_called_once_with(
            "plan_step_removed",
            {
                "new_step_count": 1,
            },
        )


@pytest.fixture
def mock_delegation_deps():
    """Create mock RouterDeps with all attributes needed for delegation tests."""
    deps = MagicMock(spec=RouterDeps)
    deps.current_plan = None
    deps.active_sub_agent = None
    deps.parent_stream_handler = None
    deps.cancellation_event = None
    deps.usage_manager = AsyncMock()
    deps.sub_agent_cache = {}
    deps.sub_agent_tool_calls = {}
    return deps


@pytest.mark.asyncio
async def test_delegation_started_metric(mock_delegation_deps):
    """Test that delegation_started metric is tracked when delegating."""
    mock_ctx = MagicMock(spec=RunContext)
    mock_ctx.deps = mock_delegation_deps

    with patch(
        "shotgun.agents.router.tools.delegation_tools.track_event"
    ) as mock_track_event:
        with patch(
            "shotgun.agents.router.tools.delegation_tools._get_or_create_sub_agent"
        ) as mock_get_agent:
            # Create mock sub-agent and deps
            mock_agent = MagicMock()
            mock_sub_deps = MagicMock(spec=AgentDeps)
            mock_sub_deps.file_tracker = FileOperationTracker()
            mock_sub_deps.sub_agent_context = None
            mock_sub_deps.llm_model = MagicMock()
            mock_sub_deps.llm_model.name = "test-model"
            mock_sub_deps.llm_model.provider = "anthropic"
            mock_get_agent.return_value = (mock_agent, mock_sub_deps)

            with patch(
                "shotgun.agents.router.tools.delegation_tools.AGENT_FACTORIES"
            ) as mock_factories:
                # Mock the run function to return a successful result
                mock_result = MagicMock()
                mock_result.output = AgentResponse(
                    response="Success", clarifying_questions=[]
                )
                mock_run_fn = AsyncMock(return_value=mock_result)
                mock_factories.__getitem__ = MagicMock(
                    return_value=(MagicMock(), mock_run_fn)
                )

                await _run_sub_agent(
                    mock_ctx,
                    AgentType.RESEARCH,
                    "Test task for research",
                    context_hint="Some context",
                )

                # Check delegation_started was called
                calls = [
                    c
                    for c in mock_track_event.call_args_list
                    if c[0][0] == "delegation_started"
                ]
                assert len(calls) == 1
                assert calls[0][0][1]["target_agent"] == "research"
                assert calls[0][0][1]["task_length"] == len("Test task for research")
                assert calls[0][0][1]["has_context_hint"] is True


@pytest.mark.asyncio
async def test_delegation_completed_metric(mock_delegation_deps):
    """Test that delegation_completed metric is tracked on successful delegation."""
    mock_ctx = MagicMock(spec=RunContext)
    mock_ctx.deps = mock_delegation_deps

    with patch(
        "shotgun.agents.router.tools.delegation_tools.track_event"
    ) as mock_track_event:
        with patch(
            "shotgun.agents.router.tools.delegation_tools._get_or_create_sub_agent"
        ) as mock_get_agent:
            # Create mock sub-agent and deps
            mock_agent = MagicMock()
            mock_sub_deps = MagicMock(spec=AgentDeps)
            mock_sub_deps.file_tracker = FileOperationTracker()
            mock_sub_deps.sub_agent_context = None
            mock_sub_deps.llm_model = MagicMock()
            mock_sub_deps.llm_model.name = "test-model"
            mock_sub_deps.llm_model.provider = "anthropic"
            mock_get_agent.return_value = (mock_agent, mock_sub_deps)

            with patch(
                "shotgun.agents.router.tools.delegation_tools.AGENT_FACTORIES"
            ) as mock_factories:
                # Mock the run function to return a successful result
                mock_result = MagicMock()
                mock_result.output = AgentResponse(
                    response="Success", clarifying_questions=[]
                )
                mock_run_fn = AsyncMock(return_value=mock_result)
                mock_factories.__getitem__ = MagicMock(
                    return_value=(MagicMock(), mock_run_fn)
                )

                result = await _run_sub_agent(
                    mock_ctx,
                    AgentType.RESEARCH,
                    "Test task",
                    context_hint=None,
                )

                assert result.success is True

                # Check delegation_completed was called
                calls = [
                    c
                    for c in mock_track_event.call_args_list
                    if c[0][0] == "delegation_completed"
                ]
                assert len(calls) == 1
                assert calls[0][0][1]["target_agent"] == "research"
                assert calls[0][0][1]["files_modified_count"] == 0
                assert calls[0][0][1]["has_questions"] is False
                assert "duration_seconds" in calls[0][0][1]
