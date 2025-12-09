"""Tests for router agent plan management tools."""

from unittest.mock import MagicMock

import pytest
from pydantic_ai import RunContext

from shotgun.agents.models import FileOperationTracker
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
from shotgun.agents.router.tools.plan_tools import (
    add_step,
    create_plan,
    mark_step_done,
    remove_step,
)


@pytest.fixture
def mock_router_deps():
    """Create mock RouterDeps for testing."""
    deps = MagicMock(spec=RouterDeps)
    deps.router_mode = RouterMode.PLANNING
    deps.current_plan = None
    deps.file_tracker = FileOperationTracker()
    deps.pending_checkpoint = None
    deps.on_plan_changed = None  # Plan panel callback (Stage 11)
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
            ExecutionStep(
                id="step-3", title="Create tasks", objective="Generate tasks"
            ),
        ],
        current_step_index=0,
    )


@pytest.mark.asyncio
async def test_create_plan_success(mock_context):
    """Test creating a new execution plan."""
    input_data = CreatePlanInput(
        goal="Implement OAuth",
        steps=[
            ExecutionStepInput(
                id="step-1", title="Research", objective="Research OAuth"
            ),
            ExecutionStepInput(id="step-2", title="Implement", objective="Write code"),
        ],
    )

    result = await create_plan(mock_context, input_data)

    assert result.success is True
    assert "Created plan with 2 steps" in result.message
    assert "Implement OAuth" in result.message
    assert mock_context.deps.current_plan is not None


@pytest.mark.asyncio
async def test_create_plan_single_step(mock_context):
    """Test creating a single-step plan."""
    input_data = CreatePlanInput(
        goal="Simple task",
        steps=[
            ExecutionStepInput(id="step-1", title="Do it", objective="Just do it"),
        ],
    )

    result = await create_plan(mock_context, input_data)

    assert result.success is True
    assert "Created plan with 1 steps" in result.message


@pytest.mark.asyncio
async def test_create_plan_empty_steps(mock_context):
    """Test creating a plan with no steps."""
    input_data = CreatePlanInput(
        goal="Empty task",
        steps=[],
    )

    result = await create_plan(mock_context, input_data)

    assert result.success is True
    assert "Created plan with 0 steps" in result.message


@pytest.mark.asyncio
async def test_mark_step_done_success(mock_context, sample_plan):
    """Test marking a step as done."""
    mock_context.deps.current_plan = sample_plan

    input_data = MarkStepDoneInput(step_id="step-1")
    result = await mark_step_done(mock_context, input_data)

    assert result.success is True
    assert "Research OAuth" in result.message
    assert sample_plan.steps[0].done is True
    # Current step should advance
    assert sample_plan.current_step_index == 1


@pytest.mark.asyncio
async def test_mark_step_done_no_plan(mock_context):
    """Test marking step done when no plan exists."""
    mock_context.deps.current_plan = None

    input_data = MarkStepDoneInput(step_id="step-1")
    result = await mark_step_done(mock_context, input_data)

    assert result.success is False
    assert "No execution plan exists" in result.message


@pytest.mark.asyncio
async def test_mark_step_done_not_found(mock_context, sample_plan):
    """Test marking a non-existent step as done."""
    mock_context.deps.current_plan = sample_plan

    input_data = MarkStepDoneInput(step_id="nonexistent-step")
    result = await mark_step_done(mock_context, input_data)

    assert result.success is False
    assert "not found" in result.message


@pytest.mark.asyncio
async def test_mark_step_done_advances_index(mock_context, sample_plan):
    """Test that marking done advances current_step_index correctly."""
    mock_context.deps.current_plan = sample_plan

    # Mark first step done
    await mark_step_done(mock_context, MarkStepDoneInput(step_id="step-1"))
    assert sample_plan.current_step_index == 1

    # Mark second step done
    await mark_step_done(mock_context, MarkStepDoneInput(step_id="step-2"))
    assert sample_plan.current_step_index == 2


@pytest.mark.asyncio
async def test_add_step_append(mock_context, sample_plan):
    """Test adding a step at the end."""
    mock_context.deps.current_plan = sample_plan

    new_step = ExecutionStepInput(
        id="step-4", title="Deploy", objective="Deploy to production"
    )
    input_data = AddStepInput(step=new_step, after_step_id=None)

    result = await add_step(mock_context, input_data)

    assert result.success is True
    assert "at end of plan" in result.message
    assert len(sample_plan.steps) == 4
    assert sample_plan.steps[3].id == "step-4"


@pytest.mark.asyncio
async def test_add_step_after_specific(mock_context, sample_plan):
    """Test adding a step after a specific step."""
    mock_context.deps.current_plan = sample_plan

    new_step = ExecutionStepInput(
        id="step-1.5", title="Review research", objective="Review findings"
    )
    input_data = AddStepInput(step=new_step, after_step_id="step-1")

    result = await add_step(mock_context, input_data)

    assert result.success is True
    assert len(sample_plan.steps) == 4
    assert sample_plan.steps[1].id == "step-1.5"
    assert sample_plan.steps[2].id == "step-2"


@pytest.mark.asyncio
async def test_add_step_no_plan(mock_context):
    """Test adding a step when no plan exists."""
    mock_context.deps.current_plan = None

    new_step = ExecutionStepInput(id="step-1", title="Do it", objective="Do something")
    input_data = AddStepInput(step=new_step)

    result = await add_step(mock_context, input_data)

    assert result.success is False
    assert "No execution plan exists" in result.message


@pytest.mark.asyncio
async def test_add_step_after_not_found(mock_context, sample_plan):
    """Test adding a step after a non-existent step."""
    mock_context.deps.current_plan = sample_plan

    new_step = ExecutionStepInput(id="step-new", title="New", objective="New step")
    input_data = AddStepInput(step=new_step, after_step_id="nonexistent")

    result = await add_step(mock_context, input_data)

    assert result.success is False
    assert "not found" in result.message


@pytest.mark.asyncio
async def test_add_step_duplicate_id(mock_context, sample_plan):
    """Test adding a step with duplicate ID."""
    mock_context.deps.current_plan = sample_plan

    new_step = ExecutionStepInput(
        id="step-1",  # Duplicate ID
        title="Duplicate",
        objective="Duplicate step",
    )
    input_data = AddStepInput(step=new_step)

    result = await add_step(mock_context, input_data)

    assert result.success is False
    assert "already exists" in result.message


@pytest.mark.asyncio
async def test_remove_step_success(mock_context, sample_plan):
    """Test removing a step."""
    mock_context.deps.current_plan = sample_plan
    original_length = len(sample_plan.steps)

    input_data = RemoveStepInput(step_id="step-2")
    result = await remove_step(mock_context, input_data)

    assert result.success is True
    assert "Write spec" in result.message
    assert len(sample_plan.steps) == original_length - 1
    # Verify step-2 is gone and step-3 is now at index 1
    assert sample_plan.steps[1].id == "step-3"


@pytest.mark.asyncio
async def test_remove_step_no_plan(mock_context):
    """Test removing a step when no plan exists."""
    mock_context.deps.current_plan = None

    input_data = RemoveStepInput(step_id="step-1")
    result = await remove_step(mock_context, input_data)

    assert result.success is False
    assert "No execution plan exists" in result.message


@pytest.mark.asyncio
async def test_remove_step_not_found(mock_context, sample_plan):
    """Test removing a non-existent step."""
    mock_context.deps.current_plan = sample_plan

    input_data = RemoveStepInput(step_id="nonexistent")
    result = await remove_step(mock_context, input_data)

    assert result.success is False
    assert "not found" in result.message


@pytest.mark.asyncio
async def test_remove_step_adjusts_current_index(mock_context, sample_plan):
    """Test that removing a step adjusts current_step_index."""
    mock_context.deps.current_plan = sample_plan
    sample_plan.current_step_index = 2  # Currently at step-3

    # Remove step-1 (before current)
    input_data = RemoveStepInput(step_id="step-1")
    await remove_step(mock_context, input_data)

    # Index should decrease by 1
    assert sample_plan.current_step_index == 1


@pytest.mark.asyncio
async def test_remove_step_at_end_adjusts_index(mock_context, sample_plan):
    """Test removing the last step adjusts index if necessary."""
    mock_context.deps.current_plan = sample_plan
    sample_plan.current_step_index = 2  # At last step

    # Remove current step (the last one)
    input_data = RemoveStepInput(step_id="step-3")
    await remove_step(mock_context, input_data)

    # Index should adjust to valid position
    assert sample_plan.current_step_index <= len(sample_plan.steps) - 1


@pytest.mark.asyncio
async def test_mark_step_done_sets_pending_checkpoint_in_planning_mode(
    mock_context, sample_plan
):
    """Test that mark_step_done sets pending_checkpoint in Planning mode."""
    mock_context.deps.current_plan = sample_plan
    mock_context.deps.router_mode = RouterMode.PLANNING
    mock_context.deps.pending_checkpoint = None

    input_data = MarkStepDoneInput(step_id="step-1")
    result = await mark_step_done(mock_context, input_data)

    assert result.success is True
    # Pending checkpoint should be set
    checkpoint = mock_context.deps.pending_checkpoint
    assert checkpoint is not None
    assert checkpoint.completed_step.id == "step-1"
    # After marking step-1 done, current_step_index advances to 1 (step-2)
    # So next_step() returns the step at index 2 (step-3)
    assert checkpoint.next_step is not None
    # The next step is the one after the current step (which is now step-2)
    assert checkpoint.next_step.id == "step-3"


@pytest.mark.asyncio
async def test_mark_step_done_sets_pending_checkpoint_with_none_for_last_step(
    mock_context, sample_plan
):
    """Test that mark_step_done sets next_step to None when completing last step."""
    mock_context.deps.current_plan = sample_plan
    mock_context.deps.router_mode = RouterMode.PLANNING
    mock_context.deps.pending_checkpoint = None

    # Mark all steps done to get to the last step
    sample_plan.current_step_index = 2

    input_data = MarkStepDoneInput(step_id="step-3")
    result = await mark_step_done(mock_context, input_data)

    assert result.success is True
    # Pending checkpoint should be set with None for next_step
    checkpoint = mock_context.deps.pending_checkpoint
    assert checkpoint is not None
    assert checkpoint.completed_step.id == "step-3"
    assert checkpoint.next_step is None


@pytest.mark.asyncio
async def test_mark_step_done_skips_checkpoint_in_drafting_mode(
    mock_context, sample_plan
):
    """Test that mark_step_done does NOT set checkpoint in Drafting mode."""
    mock_context.deps.current_plan = sample_plan
    mock_context.deps.router_mode = RouterMode.DRAFTING
    mock_context.deps.pending_checkpoint = None

    input_data = MarkStepDoneInput(step_id="step-1")
    result = await mark_step_done(mock_context, input_data)

    assert result.success is True
    # Pending checkpoint should NOT be set in Drafting mode
    assert mock_context.deps.pending_checkpoint is None


# Tests for is_executing flag behavior


@pytest.mark.asyncio
async def test_create_plan_sets_is_executing_for_single_step(mock_context):
    """Test that creating a single-step plan sets is_executing=True."""
    mock_context.deps.is_executing = False

    input_data = CreatePlanInput(
        goal="Simple task",
        steps=[
            ExecutionStepInput(id="step-1", title="Do it", objective="Just do it"),
        ],
    )

    await create_plan(mock_context, input_data)

    # Single-step plans skip approval and start executing immediately
    assert mock_context.deps.is_executing is True


@pytest.mark.asyncio
async def test_create_plan_sets_is_executing_for_drafting_mode(mock_context):
    """Test that creating a multi-step plan in Drafting mode sets is_executing=True."""
    mock_context.deps.router_mode = RouterMode.DRAFTING
    mock_context.deps.is_executing = False

    input_data = CreatePlanInput(
        goal="Multi-step task",
        steps=[
            ExecutionStepInput(id="step-1", title="Step 1", objective="First step"),
            ExecutionStepInput(id="step-2", title="Step 2", objective="Second step"),
        ],
    )

    await create_plan(mock_context, input_data)

    # Drafting mode skips approval and starts executing immediately
    assert mock_context.deps.is_executing is True


@pytest.mark.asyncio
async def test_create_plan_does_not_set_is_executing_for_multi_step_planning(
    mock_context,
):
    """Test that creating a multi-step plan in Planning mode does NOT set is_executing."""
    mock_context.deps.router_mode = RouterMode.PLANNING
    mock_context.deps.is_executing = False

    input_data = CreatePlanInput(
        goal="Multi-step task",
        steps=[
            ExecutionStepInput(id="step-1", title="Step 1", objective="First step"),
            ExecutionStepInput(id="step-2", title="Step 2", objective="Second step"),
        ],
    )

    await create_plan(mock_context, input_data)

    # Multi-step plans in Planning mode need approval first
    assert mock_context.deps.is_executing is False


@pytest.mark.asyncio
async def test_mark_step_done_clears_is_executing_when_plan_complete(
    mock_context, sample_plan
):
    """Test that completing the last step sets is_executing=False."""
    mock_context.deps.current_plan = sample_plan
    mock_context.deps.is_executing = True

    # Mark all steps done
    await mark_step_done(mock_context, MarkStepDoneInput(step_id="step-1"))
    await mark_step_done(mock_context, MarkStepDoneInput(step_id="step-2"))
    await mark_step_done(mock_context, MarkStepDoneInput(step_id="step-3"))

    # Plan is now complete, is_executing should be False
    assert sample_plan.is_complete() is True
    assert mock_context.deps.is_executing is False


@pytest.mark.asyncio
async def test_mark_step_done_keeps_is_executing_when_plan_not_complete(
    mock_context, sample_plan
):
    """Test that completing a non-final step keeps is_executing=True."""
    mock_context.deps.current_plan = sample_plan
    mock_context.deps.is_executing = True

    # Mark first step done (not the last)
    await mark_step_done(mock_context, MarkStepDoneInput(step_id="step-1"))

    # Plan is not complete, is_executing should still be True
    assert sample_plan.is_complete() is False
    assert mock_context.deps.is_executing is True
