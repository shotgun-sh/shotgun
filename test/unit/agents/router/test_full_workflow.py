"""Integration tests for Router agent full workflow.

These tests verify the complete router workflow including:
- Plan creation and state management
- Planning vs Drafting mode behavior
- is_executing flag lifecycle
- Checkpoint and approval handling

Note: These tests use real RouterDeps but mock the LLM to focus on
workflow mechanics. They test the end-to-end plan workflow.
"""

from unittest.mock import MagicMock

import pytest
from pydantic_ai import RunContext

from shotgun.agents.models import FileOperationTracker
from shotgun.agents.router.models import (
    CreatePlanInput,
    ExecutionPlan,
    ExecutionStep,
    ExecutionStepInput,
    MarkStepDoneInput,
    PlanApprovalStatus,
    RouterDeps,
    RouterMode,
)
from shotgun.agents.router.tools.plan_tools import create_plan, mark_step_done


@pytest.fixture
def router_deps():
    """Create mock RouterDeps for testing."""
    deps = MagicMock(spec=RouterDeps)
    deps.router_mode = RouterMode.PLANNING
    deps.current_plan = None
    deps.file_tracker = FileOperationTracker()
    deps.pending_approval = None
    deps.pending_checkpoint = None
    deps.is_executing = False
    deps.active_sub_agent = None
    deps.on_plan_changed = None
    deps.approval_status = PlanApprovalStatus.SKIPPED  # Default
    return deps


@pytest.fixture
def run_context(router_deps):
    """Create a mock RunContext with mock RouterDeps."""
    ctx = MagicMock(spec=RunContext)
    ctx.deps = router_deps
    return ctx


@pytest.mark.asyncio
async def test_router_creates_execution_plan(run_context):
    """Router creates an ExecutionPlan from user request."""
    input_data = CreatePlanInput(
        goal="Implement user authentication",
        steps=[
            ExecutionStepInput(
                id="research",
                title="Research auth patterns",
                objective="Find best practices for auth",
            ),
            ExecutionStepInput(
                id="spec",
                title="Write specification",
                objective="Document auth requirements",
            ),
            ExecutionStepInput(
                id="tasks",
                title="Create tasks",
                objective="Break down implementation",
            ),
        ],
    )

    result = await create_plan(run_context, input_data)

    assert result.success is True
    assert run_context.deps.current_plan is not None
    assert run_context.deps.current_plan.goal == "Implement user authentication"
    assert len(run_context.deps.current_plan.steps) == 3
    assert run_context.deps.current_plan.current_step_index == 0


@pytest.mark.asyncio
async def test_router_planning_mode_creates_pending_approval(run_context):
    """Planning mode creates pending approval for multi-step plans."""
    run_context.deps.router_mode = RouterMode.PLANNING

    input_data = CreatePlanInput(
        goal="Build feature",
        steps=[
            ExecutionStepInput(id="step-1", title="Step 1", objective="First"),
            ExecutionStepInput(id="step-2", title="Step 2", objective="Second"),
        ],
    )

    await create_plan(run_context, input_data)

    # Should have pending approval
    assert run_context.deps.pending_approval is not None
    assert run_context.deps.approval_status == PlanApprovalStatus.PENDING
    # Should NOT be executing yet (waiting for approval)
    assert run_context.deps.is_executing is False


@pytest.mark.asyncio
async def test_router_planning_mode_creates_checkpoints(run_context):
    """Planning mode creates checkpoints after completing steps."""
    run_context.deps.router_mode = RouterMode.PLANNING
    run_context.deps.is_executing = True

    # Create a plan
    plan = ExecutionPlan(
        goal="Test plan",
        steps=[
            ExecutionStep(id="step-1", title="First", objective="Do first"),
            ExecutionStep(id="step-2", title="Second", objective="Do second"),
            ExecutionStep(id="step-3", title="Third", objective="Do third"),
        ],
        current_step_index=0,
    )
    run_context.deps.current_plan = plan

    # Mark first step done
    result = await mark_step_done(run_context, MarkStepDoneInput(step_id="step-1"))

    assert result.success is True
    # Should have pending checkpoint
    assert run_context.deps.pending_checkpoint is not None
    checkpoint = run_context.deps.pending_checkpoint
    assert checkpoint.completed_step.id == "step-1"
    assert checkpoint.next_step is not None
    assert checkpoint.next_step.id == "step-3"


@pytest.mark.asyncio
async def test_router_drafting_mode_skips_approval(run_context):
    """Drafting mode skips approval and starts executing immediately."""
    run_context.deps.router_mode = RouterMode.DRAFTING

    input_data = CreatePlanInput(
        goal="Quick task",
        steps=[
            ExecutionStepInput(id="step-1", title="Step 1", objective="First"),
            ExecutionStepInput(id="step-2", title="Step 2", objective="Second"),
        ],
    )

    await create_plan(run_context, input_data)

    # Should NOT have pending approval in Drafting mode
    assert run_context.deps.pending_approval is None
    assert run_context.deps.approval_status == PlanApprovalStatus.SKIPPED
    # Should be executing immediately
    assert run_context.deps.is_executing is True


@pytest.mark.asyncio
async def test_router_drafting_mode_skips_checkpoints(run_context):
    """Drafting mode executes without checkpoints."""
    run_context.deps.router_mode = RouterMode.DRAFTING
    run_context.deps.is_executing = True

    # Create a plan
    plan = ExecutionPlan(
        goal="Quick plan",
        steps=[
            ExecutionStep(id="step-1", title="First", objective="Do first"),
            ExecutionStep(id="step-2", title="Second", objective="Do second"),
        ],
        current_step_index=0,
    )
    run_context.deps.current_plan = plan

    # Mark first step done
    await mark_step_done(run_context, MarkStepDoneInput(step_id="step-1"))

    # Should NOT have pending checkpoint in Drafting mode
    assert run_context.deps.pending_checkpoint is None


@pytest.mark.asyncio
async def test_is_executing_flag_lifecycle_single_step(run_context):
    """is_executing flag is set correctly for single-step plans."""
    run_context.deps.router_mode = RouterMode.PLANNING

    # Create single-step plan (auto-approved)
    input_data = CreatePlanInput(
        goal="Simple task",
        steps=[
            ExecutionStepInput(id="step-1", title="Do it", objective="Just do it"),
        ],
    )

    await create_plan(run_context, input_data)

    # Single-step plans start executing immediately
    assert run_context.deps.is_executing is True

    # Complete the step
    await mark_step_done(run_context, MarkStepDoneInput(step_id="step-1"))

    # Should be false after plan completes
    assert run_context.deps.is_executing is False


@pytest.mark.asyncio
async def test_is_executing_flag_lifecycle_multi_step(run_context):
    """is_executing flag lifecycle for multi-step plans."""
    run_context.deps.router_mode = RouterMode.DRAFTING  # Auto-execute

    # Create multi-step plan
    input_data = CreatePlanInput(
        goal="Multi-step task",
        steps=[
            ExecutionStepInput(id="step-1", title="First", objective="Do first"),
            ExecutionStepInput(id="step-2", title="Second", objective="Do second"),
        ],
    )

    await create_plan(run_context, input_data)

    # Should be executing (drafting mode auto-approves)
    assert run_context.deps.is_executing is True

    # Complete first step
    await mark_step_done(run_context, MarkStepDoneInput(step_id="step-1"))

    # Should still be executing (not complete)
    assert run_context.deps.is_executing is True

    # Complete second step
    await mark_step_done(run_context, MarkStepDoneInput(step_id="step-2"))

    # Should be false after plan completes
    assert run_context.deps.is_executing is False


@pytest.mark.asyncio
async def test_plan_complete_detection(run_context):
    """Test that plan completion is properly detected."""
    run_context.deps.router_mode = RouterMode.DRAFTING
    run_context.deps.is_executing = True

    # Create a 3-step plan
    plan = ExecutionPlan(
        goal="Test completion",
        steps=[
            ExecutionStep(id="step-1", title="Step 1", objective="First"),
            ExecutionStep(id="step-2", title="Step 2", objective="Second"),
            ExecutionStep(id="step-3", title="Step 3", objective="Third"),
        ],
        current_step_index=0,
    )
    run_context.deps.current_plan = plan

    # Verify plan is not complete
    assert plan.is_complete() is False

    # Complete all steps
    await mark_step_done(run_context, MarkStepDoneInput(step_id="step-1"))
    assert plan.is_complete() is False

    await mark_step_done(run_context, MarkStepDoneInput(step_id="step-2"))
    assert plan.is_complete() is False

    await mark_step_done(run_context, MarkStepDoneInput(step_id="step-3"))
    assert plan.is_complete() is True
    assert run_context.deps.is_executing is False


@pytest.mark.asyncio
async def test_plan_panel_callback_invoked(run_context):
    """Test that on_plan_changed callback is invoked on plan modifications."""
    callback = MagicMock()
    run_context.deps.on_plan_changed = callback

    # Create plan
    input_data = CreatePlanInput(
        goal="Test callback",
        steps=[
            ExecutionStepInput(id="step-1", title="Step", objective="Test"),
        ],
    )

    await create_plan(run_context, input_data)

    # Callback should have been invoked with the plan
    callback.assert_called_once()
    call_args = callback.call_args[0]
    assert call_args[0] is not None
    assert call_args[0].goal == "Test callback"
