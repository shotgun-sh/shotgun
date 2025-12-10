"""Tests for router agent models."""

from shotgun.agents.router.models import (
    AddStepInput,
    CascadeScope,
    CreatePlanInput,
    DelegationInput,
    DelegationResult,
    ExecutionPlan,
    ExecutionStep,
    ExecutionStepInput,
    MarkStepDoneInput,
    PlanApprovalStatus,
    RemoveStepInput,
    RouterMode,
    StepCheckpointAction,
    SubAgentResult,
    SubAgentResultStatus,
    ToolResult,
    get_dependent_files,
)


def test_router_mode_enum():
    """Test RouterMode enum values."""
    assert RouterMode.PLANNING == "planning"
    assert RouterMode.DRAFTING == "drafting"


def test_plan_approval_status_enum():
    """Test PlanApprovalStatus enum values."""
    assert PlanApprovalStatus.PENDING == "pending"
    assert PlanApprovalStatus.APPROVED == "approved"
    assert PlanApprovalStatus.REJECTED == "rejected"
    assert PlanApprovalStatus.SKIPPED == "skipped"


def test_step_checkpoint_action_enum():
    """Test StepCheckpointAction enum values."""
    assert StepCheckpointAction.CONTINUE == "continue"
    assert StepCheckpointAction.MODIFY == "modify"
    assert StepCheckpointAction.STOP == "stop"


def test_cascade_scope_enum():
    """Test CascadeScope enum values."""
    assert CascadeScope.ALL == "all"
    assert CascadeScope.PLAN_ONLY == "plan_only"
    assert CascadeScope.TASKS_ONLY == "tasks_only"
    assert CascadeScope.NONE == "none"


def test_sub_agent_result_status_enum():
    """Test SubAgentResultStatus enum values."""
    assert SubAgentResultStatus.SUCCESS == "success"
    assert SubAgentResultStatus.PARTIAL == "partial"
    assert SubAgentResultStatus.ERROR == "error"
    assert SubAgentResultStatus.NEEDS_CLARIFICATION == "needs_clarification"


def test_execution_step_creation():
    """Test ExecutionStep model creation."""
    step = ExecutionStep(
        id="research-oauth",
        title="Research OAuth patterns",
        objective="Find best practices for OAuth 2.0 implementation",
    )
    assert step.id == "research-oauth"
    assert step.title == "Research OAuth patterns"
    assert step.objective == "Find best practices for OAuth 2.0 implementation"
    assert step.done is False


def test_execution_step_done_default():
    """Test ExecutionStep done field defaults to False."""
    step = ExecutionStep(
        id="test-step",
        title="Test step",
        objective="Test objective",
    )
    assert step.done is False


def test_execution_plan_creation():
    """Test ExecutionPlan model creation."""
    steps = [
        ExecutionStep(id="step-1", title="Step 1", objective="Do step 1"),
        ExecutionStep(id="step-2", title="Step 2", objective="Do step 2"),
    ]
    plan = ExecutionPlan(goal="Complete the task", steps=steps)

    assert plan.goal == "Complete the task"
    assert len(plan.steps) == 2
    assert plan.current_step_index == 0


def test_execution_plan_needs_approval_single_step():
    """Test needs_approval returns True for single-step plans.

    All plans require approval in Planning mode - user should always
    see the plan before execution begins, even for simple tasks.
    """
    plan = ExecutionPlan(
        goal="Simple task",
        steps=[ExecutionStep(id="step-1", title="Step 1", objective="Do it")],
    )
    assert plan.needs_approval() is True


def test_execution_plan_needs_approval_multi_step():
    """Test needs_approval returns True for multi-step plans."""
    plan = ExecutionPlan(
        goal="Complex task",
        steps=[
            ExecutionStep(id="step-1", title="Step 1", objective="First"),
            ExecutionStep(id="step-2", title="Step 2", objective="Second"),
        ],
    )
    assert plan.needs_approval() is True


def test_execution_plan_needs_approval_empty():
    """Test needs_approval returns False for empty plans."""
    plan = ExecutionPlan(goal="Empty task", steps=[])
    assert plan.needs_approval() is False


def test_execution_plan_current_step():
    """Test current_step returns correct step."""
    steps = [
        ExecutionStep(id="step-1", title="Step 1", objective="First"),
        ExecutionStep(id="step-2", title="Step 2", objective="Second"),
    ]
    plan = ExecutionPlan(goal="Task", steps=steps, current_step_index=0)

    current = plan.current_step()
    assert current is not None
    assert current.id == "step-1"

    plan.current_step_index = 1
    current = plan.current_step()
    assert current is not None
    assert current.id == "step-2"


def test_execution_plan_current_step_out_of_bounds():
    """Test current_step returns None when index is out of bounds."""
    plan = ExecutionPlan(
        goal="Task",
        steps=[ExecutionStep(id="step-1", title="Step 1", objective="First")],
        current_step_index=5,
    )
    assert plan.current_step() is None


def test_execution_plan_current_step_empty():
    """Test current_step returns None for empty plans."""
    plan = ExecutionPlan(goal="Task", steps=[])
    assert plan.current_step() is None


def test_execution_plan_next_step():
    """Test next_step returns correct step."""
    steps = [
        ExecutionStep(id="step-1", title="Step 1", objective="First"),
        ExecutionStep(id="step-2", title="Step 2", objective="Second"),
        ExecutionStep(id="step-3", title="Step 3", objective="Third"),
    ]
    plan = ExecutionPlan(goal="Task", steps=steps, current_step_index=0)

    next_step = plan.next_step()
    assert next_step is not None
    assert next_step.id == "step-2"


def test_execution_plan_next_step_at_last():
    """Test next_step returns None when at last step."""
    steps = [
        ExecutionStep(id="step-1", title="Step 1", objective="First"),
        ExecutionStep(id="step-2", title="Step 2", objective="Second"),
    ]
    plan = ExecutionPlan(goal="Task", steps=steps, current_step_index=1)
    assert plan.next_step() is None


def test_execution_plan_is_complete():
    """Test is_complete when all steps are done."""
    steps = [
        ExecutionStep(id="step-1", title="Step 1", objective="First", done=True),
        ExecutionStep(id="step-2", title="Step 2", objective="Second", done=True),
    ]
    plan = ExecutionPlan(goal="Task", steps=steps)
    assert plan.is_complete() is True


def test_execution_plan_is_not_complete():
    """Test is_complete when some steps are not done."""
    steps = [
        ExecutionStep(id="step-1", title="Step 1", objective="First", done=True),
        ExecutionStep(id="step-2", title="Step 2", objective="Second", done=False),
    ]
    plan = ExecutionPlan(goal="Task", steps=steps)
    assert plan.is_complete() is False


def test_execution_plan_is_complete_empty():
    """Test is_complete returns True for empty plans."""
    plan = ExecutionPlan(goal="Task", steps=[])
    assert plan.is_complete() is True


def test_execution_plan_pending_steps():
    """Test pending_steps returns incomplete steps."""
    steps = [
        ExecutionStep(id="step-1", title="Step 1", objective="First", done=True),
        ExecutionStep(id="step-2", title="Step 2", objective="Second", done=False),
        ExecutionStep(id="step-3", title="Step 3", objective="Third", done=False),
    ]
    plan = ExecutionPlan(goal="Task", steps=steps)

    pending = plan.pending_steps()
    assert len(pending) == 2
    assert pending[0].id == "step-2"
    assert pending[1].id == "step-3"


def test_execution_plan_format_for_display():
    """Test format_for_display output format."""
    steps = [
        ExecutionStep(
            id="step-1", title="Research OAuth", objective="First", done=True
        ),
        ExecutionStep(id="step-2", title="Write spec", objective="Second", done=False),
        ExecutionStep(id="step-3", title="Create tasks", objective="Third", done=False),
    ]
    plan = ExecutionPlan(goal="Implement OAuth", steps=steps, current_step_index=1)

    output = plan.format_for_display()

    assert "**Goal:** Implement OAuth" in output
    assert "**Steps:**" in output
    assert "1." in output and "Research OAuth" in output
    assert "2." in output and "Write spec" in output
    assert "3." in output and "Create tasks" in output
    # Check markers
    assert "✅" in output  # Done marker for step 1
    assert "⬜" in output  # Not done marker
    assert "◀" in output  # Current step indicator


def test_get_dependent_files_research():
    """Test get_dependent_files for research.md."""
    deps = get_dependent_files("research.md")
    assert "specification.md" in deps
    assert "plan.md" in deps
    assert "tasks.md" in deps


def test_get_dependent_files_specification():
    """Test get_dependent_files for specification.md."""
    deps = get_dependent_files("specification.md")
    assert "plan.md" in deps
    assert "tasks.md" in deps
    assert "research.md" not in deps


def test_get_dependent_files_plan():
    """Test get_dependent_files for plan.md."""
    deps = get_dependent_files("plan.md")
    assert deps == ["tasks.md"]


def test_get_dependent_files_tasks():
    """Test get_dependent_files for tasks.md (leaf node)."""
    deps = get_dependent_files("tasks.md")
    assert deps == []


def test_get_dependent_files_with_path():
    """Test get_dependent_files with full path."""
    deps = get_dependent_files(".shotgun/research.md")
    assert "specification.md" in deps


def test_get_dependent_files_unknown():
    """Test get_dependent_files for unknown file."""
    deps = get_dependent_files("unknown.md")
    assert deps == []


def test_tool_result_creation():
    """Test ToolResult model creation."""
    result = ToolResult(success=True, message="Operation completed")
    assert result.success is True
    assert result.message == "Operation completed"


def test_delegation_input_creation():
    """Test DelegationInput model creation."""
    input_model = DelegationInput(
        task="Research OAuth patterns",
        context_hint="Focus on OAuth 2.0 with PKCE",
    )
    assert input_model.task == "Research OAuth patterns"
    assert input_model.context_hint == "Focus on OAuth 2.0 with PKCE"


def test_delegation_input_optional_hint():
    """Test DelegationInput with optional context_hint."""
    input_model = DelegationInput(task="Research OAuth patterns")
    assert input_model.task == "Research OAuth patterns"
    assert input_model.context_hint is None


def test_delegation_result_creation():
    """Test DelegationResult model creation."""
    result = DelegationResult(
        success=True,
        response="Research completed",
        files_modified=["research.md"],
        has_questions=False,
        questions=[],
    )
    assert result.success is True
    assert result.response == "Research completed"
    assert result.files_modified == ["research.md"]
    assert result.has_questions is False


def test_delegation_result_with_questions():
    """Test DelegationResult with clarifying questions."""
    result = DelegationResult(
        success=True,
        response="",
        files_modified=[],
        has_questions=True,
        questions=["Should I include SSO?", "What scope?"],
    )
    assert result.has_questions is True
    assert len(result.questions) == 2


def test_sub_agent_result_creation():
    """Test SubAgentResult model creation."""
    result = SubAgentResult(
        status=SubAgentResultStatus.SUCCESS,
        response="Task completed",
        files_modified=["research.md"],
    )
    assert result.status == SubAgentResultStatus.SUCCESS
    assert result.response == "Task completed"
    assert result.files_modified == ["research.md"]
    assert result.is_retryable is False


def test_sub_agent_result_with_error():
    """Test SubAgentResult with error status."""
    result = SubAgentResult(
        status=SubAgentResultStatus.ERROR,
        error="Connection timeout",
        is_retryable=True,
    )
    assert result.status == SubAgentResultStatus.ERROR
    assert result.error == "Connection timeout"
    assert result.is_retryable is True


def test_execution_step_input_creation():
    """Test ExecutionStepInput model creation."""
    input_model = ExecutionStepInput(
        id="step-1",
        title="Research OAuth",
        objective="Find OAuth best practices",
    )
    assert input_model.id == "step-1"
    assert input_model.title == "Research OAuth"
    assert input_model.objective == "Find OAuth best practices"


def test_create_plan_input_creation():
    """Test CreatePlanInput model creation."""
    input_model = CreatePlanInput(
        goal="Implement OAuth",
        steps=[
            ExecutionStepInput(
                id="step-1", title="Research", objective="Research OAuth"
            ),
            ExecutionStepInput(id="step-2", title="Implement", objective="Write code"),
        ],
    )
    assert input_model.goal == "Implement OAuth"
    assert len(input_model.steps) == 2


def test_mark_step_done_input_creation():
    """Test MarkStepDoneInput model creation."""
    input_model = MarkStepDoneInput(step_id="step-1")
    assert input_model.step_id == "step-1"


def test_add_step_input_creation():
    """Test AddStepInput model creation."""
    step = ExecutionStepInput(id="new-step", title="New", objective="New step")
    input_model = AddStepInput(step=step, after_step_id="step-1")
    assert input_model.step.id == "new-step"
    assert input_model.after_step_id == "step-1"


def test_add_step_input_append():
    """Test AddStepInput for appending (no after_step_id)."""
    step = ExecutionStepInput(id="new-step", title="New", objective="New step")
    input_model = AddStepInput(step=step)
    assert input_model.after_step_id is None


def test_remove_step_input_creation():
    """Test RemoveStepInput model creation."""
    input_model = RemoveStepInput(step_id="step-1")
    assert input_model.step_id == "step-1"
