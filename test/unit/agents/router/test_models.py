"""Tests for router agent models."""

from shotgun.agents.router.models import (
    CascadeScope,
    ExecutionPlan,
    ExecutionStep,
    FILE_DEPENDENCIES,
    PlanApprovalStatus,
    RouterMode,
    StepCheckpointAction,
    get_dependent_files,
)


def test_router_mode_values():
    """Test RouterMode enum values."""
    assert RouterMode.PLANNING == "planning"
    assert RouterMode.DRAFTING == "drafting"


def test_plan_approval_status_values():
    """Test PlanApprovalStatus enum values."""
    assert PlanApprovalStatus.PENDING == "pending"
    assert PlanApprovalStatus.APPROVED == "approved"
    assert PlanApprovalStatus.REJECTED == "rejected"
    assert PlanApprovalStatus.SKIPPED == "skipped"


def test_step_checkpoint_action_values():
    """Test StepCheckpointAction enum values."""
    assert StepCheckpointAction.CONTINUE == "continue"
    assert StepCheckpointAction.MODIFY == "modify"
    assert StepCheckpointAction.STOP == "stop"


def test_cascade_scope_values():
    """Test CascadeScope enum values."""
    assert CascadeScope.ALL == "all"
    assert CascadeScope.PLAN_ONLY == "plan_only"
    assert CascadeScope.TASKS_ONLY == "tasks_only"
    assert CascadeScope.NONE == "none"


def test_execution_step_creation():
    """Test creating an ExecutionStep."""
    step = ExecutionStep(
        id="test-step",
        title="Test Step",
        objective="Test the step creation",
        success_criteria=["Step created successfully"],
        affects_files=["test.md"],
    )

    assert step.id == "test-step"
    assert step.title == "Test Step"
    assert step.objective == "Test the step creation"
    assert step.success_criteria == ["Step created successfully"]
    assert step.affects_files == ["test.md"]
    assert step.done is False
    assert step.dependent_files == []


def test_execution_step_defaults():
    """Test ExecutionStep default values."""
    step = ExecutionStep(
        id="minimal",
        title="Minimal Step",
        objective="Just the basics",
    )

    assert step.success_criteria == []
    assert step.affects_files == []
    assert step.dependent_files == []
    assert step.done is False


def test_execution_plan_needs_approval_single_step():
    """Test that single-step plans don't need approval."""
    plan = ExecutionPlan(
        goal="Simple task",
        steps=[
            ExecutionStep(id="1", title="Only step", objective="Do the thing"),
        ],
    )

    assert plan.needs_approval() is False


def test_execution_plan_needs_approval_multi_step():
    """Test that multi-step plans need approval."""
    plan = ExecutionPlan(
        goal="Complex task",
        steps=[
            ExecutionStep(id="1", title="Step 1", objective="First"),
            ExecutionStep(id="2", title="Step 2", objective="Second"),
        ],
    )

    assert plan.needs_approval() is True


def test_execution_plan_needs_approval_empty():
    """Test that empty plans don't need approval."""
    plan = ExecutionPlan(goal="Empty plan", steps=[])
    assert plan.needs_approval() is False


def test_execution_plan_current_step():
    """Test getting the current step."""
    steps = [
        ExecutionStep(id="1", title="Step 1", objective="First"),
        ExecutionStep(id="2", title="Step 2", objective="Second"),
        ExecutionStep(id="3", title="Step 3", objective="Third"),
    ]
    plan = ExecutionPlan(goal="Test", steps=steps, current_step_index=1)

    current = plan.current_step()
    assert current is not None
    assert current.id == "2"
    assert current.title == "Step 2"


def test_execution_plan_current_step_out_of_bounds():
    """Test current_step returns None when index is out of bounds."""
    plan = ExecutionPlan(
        goal="Test",
        steps=[ExecutionStep(id="1", title="Only", objective="Step")],
        current_step_index=5,
    )

    assert plan.current_step() is None


def test_execution_plan_next_step():
    """Test getting the next step."""
    steps = [
        ExecutionStep(id="1", title="Step 1", objective="First"),
        ExecutionStep(id="2", title="Step 2", objective="Second"),
        ExecutionStep(id="3", title="Step 3", objective="Third"),
    ]
    plan = ExecutionPlan(goal="Test", steps=steps, current_step_index=1)

    next_step = plan.next_step()
    assert next_step is not None
    assert next_step.id == "3"
    assert next_step.title == "Step 3"


def test_execution_plan_next_step_at_end():
    """Test next_step returns None when at the last step."""
    steps = [
        ExecutionStep(id="1", title="Step 1", objective="First"),
        ExecutionStep(id="2", title="Step 2", objective="Second"),
    ]
    plan = ExecutionPlan(goal="Test", steps=steps, current_step_index=1)

    assert plan.next_step() is None


def test_execution_plan_is_complete_all_done():
    """Test is_complete when all steps are done."""
    steps = [
        ExecutionStep(id="1", title="Step 1", objective="First", done=True),
        ExecutionStep(id="2", title="Step 2", objective="Second", done=True),
    ]
    plan = ExecutionPlan(goal="Test", steps=steps)

    assert plan.is_complete() is True


def test_execution_plan_is_complete_some_pending():
    """Test is_complete when some steps are pending."""
    steps = [
        ExecutionStep(id="1", title="Step 1", objective="First", done=True),
        ExecutionStep(id="2", title="Step 2", objective="Second", done=False),
    ]
    plan = ExecutionPlan(goal="Test", steps=steps)

    assert plan.is_complete() is False


def test_execution_plan_is_complete_empty():
    """Test is_complete with empty steps."""
    plan = ExecutionPlan(goal="Empty", steps=[])
    assert plan.is_complete() is True


def test_execution_plan_pending_steps():
    """Test getting pending steps."""
    steps = [
        ExecutionStep(id="1", title="Step 1", objective="First", done=True),
        ExecutionStep(id="2", title="Step 2", objective="Second", done=False),
        ExecutionStep(id="3", title="Step 3", objective="Third", done=False),
    ]
    plan = ExecutionPlan(goal="Test", steps=steps)

    pending = plan.pending_steps()
    assert len(pending) == 2
    assert pending[0].id == "2"
    assert pending[1].id == "3"


def test_execution_plan_pending_steps_all_done():
    """Test pending_steps when all are done."""
    steps = [
        ExecutionStep(id="1", title="Step 1", objective="First", done=True),
        ExecutionStep(id="2", title="Step 2", objective="Second", done=True),
    ]
    plan = ExecutionPlan(goal="Test", steps=steps)

    assert plan.pending_steps() == []


def test_file_dependencies_map():
    """Test the FILE_DEPENDENCIES map structure."""
    assert "research.md" in FILE_DEPENDENCIES
    assert "specification.md" in FILE_DEPENDENCIES
    assert "plan.md" in FILE_DEPENDENCIES
    assert "tasks.md" in FILE_DEPENDENCIES

    # tasks.md is a leaf node
    assert FILE_DEPENDENCIES["tasks.md"] == []

    # research.md has all downstream files
    assert "specification.md" in FILE_DEPENDENCIES["research.md"]
    assert "plan.md" in FILE_DEPENDENCIES["research.md"]
    assert "tasks.md" in FILE_DEPENDENCIES["research.md"]


def test_get_dependent_files_research():
    """Test getting dependents for research.md."""
    deps = get_dependent_files("research.md")
    assert "specification.md" in deps
    assert "plan.md" in deps
    assert "tasks.md" in deps


def test_get_dependent_files_specification():
    """Test getting dependents for specification.md."""
    deps = get_dependent_files("specification.md")
    assert "plan.md" in deps
    assert "tasks.md" in deps
    assert "research.md" not in deps


def test_get_dependent_files_plan():
    """Test getting dependents for plan.md."""
    deps = get_dependent_files("plan.md")
    assert deps == ["tasks.md"]


def test_get_dependent_files_tasks():
    """Test getting dependents for tasks.md (leaf node)."""
    deps = get_dependent_files("tasks.md")
    assert deps == []


def test_get_dependent_files_with_path():
    """Test get_dependent_files with full path."""
    # Should extract just the filename
    deps = get_dependent_files(".shotgun/specification.md")
    assert "plan.md" in deps
    assert "tasks.md" in deps


def test_get_dependent_files_unknown():
    """Test get_dependent_files with unknown file."""
    deps = get_dependent_files("unknown.md")
    assert deps == []
