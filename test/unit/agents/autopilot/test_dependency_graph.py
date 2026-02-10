"""Tests for the dependency graph module."""

from shotgun.agents.autopilot.dependency_graph import (
    DependencyError,
    ExecutionBatch,
    ExecutionPlan,
    compute_execution_batches,
    get_ready_stages,
    validate_dependencies,
)
from shotgun.agents.autopilot.models import Stage, StageStatus, Task


def _make_stage(
    number: str,
    depends_on: list[str] | None = None,
    status: StageStatus = StageStatus.PENDING,
    tasks: list[Task] | None = None,
) -> Stage:
    """Helper to create a Stage for testing."""
    return Stage(
        number=number,
        name=f"Stage {number}",
        depends_on=depends_on or [],
        status=status,
        tasks=tasks
        or [Task(text=f"Task for stage {number}", completed=False, line_number=1)],
    )


def test_validate_no_dependencies():
    """All stages have no dependencies - valid graph."""
    stages = [_make_stage("1"), _make_stage("2"), _make_stage("3")]
    errors = validate_dependencies(stages)
    assert errors == []


def test_validate_linear_chain():
    """Linear chain A->B->C is valid."""
    stages = [
        _make_stage("1"),
        _make_stage("2", depends_on=["1"]),
        _make_stage("3", depends_on=["2"]),
    ]
    errors = validate_dependencies(stages)
    assert errors == []


def test_validate_diamond():
    """Diamond pattern A,B->C is valid."""
    stages = [
        _make_stage("1"),
        _make_stage("2"),
        _make_stage("3", depends_on=["1", "2"]),
    ]
    errors = validate_dependencies(stages)
    assert errors == []


def test_validate_cycle_detected():
    """Circular dependency should be detected."""
    stages = [
        _make_stage("1", depends_on=["2"]),
        _make_stage("2", depends_on=["1"]),
    ]
    errors = validate_dependencies(stages)
    assert len(errors) == 1
    assert errors[0].error_type == "cycle"
    assert "1" in errors[0].details
    assert "2" in errors[0].details


def test_validate_self_cycle():
    """Stage depending on itself is a cycle."""
    stages = [_make_stage("1", depends_on=["1"])]
    errors = validate_dependencies(stages)
    assert len(errors) == 1
    assert errors[0].error_type == "cycle"


def test_validate_missing_ref():
    """Reference to non-existent stage should be flagged."""
    stages = [_make_stage("1", depends_on=["99"])]
    errors = validate_dependencies(stages)
    assert len(errors) == 1
    assert errors[0].error_type == "missing_ref"
    assert "99" in errors[0].details


def test_validate_multiple_errors():
    """Multiple errors can be detected at once."""
    stages = [
        _make_stage("1", depends_on=["99"]),  # missing ref
        _make_stage("2", depends_on=["3"]),  # cycle
        _make_stage("3", depends_on=["2"]),  # cycle
    ]
    errors = validate_dependencies(stages)
    assert len(errors) >= 2
    error_types = {e.error_type for e in errors}
    assert "missing_ref" in error_types
    assert "cycle" in error_types


def test_compute_no_dependencies_single_batch():
    """All independent stages should be in one batch."""
    stages = [_make_stage("1"), _make_stage("2"), _make_stage("3")]
    plan = compute_execution_batches(stages, skip_completed=False)

    assert plan.total_batches == 1
    assert plan.total_stages == 3
    assert sorted(plan.batches[0].stage_numbers) == ["1", "2", "3"]


def test_compute_linear_chain_three_batches():
    """Linear chain A->B->C should produce 3 batches of 1."""
    stages = [
        _make_stage("1"),
        _make_stage("2", depends_on=["1"]),
        _make_stage("3", depends_on=["2"]),
    ]
    plan = compute_execution_batches(stages, skip_completed=False)

    assert plan.total_batches == 3
    assert plan.batches[0].stage_numbers == ["1"]
    assert plan.batches[1].stage_numbers == ["2"]
    assert plan.batches[2].stage_numbers == ["3"]


def test_compute_diamond_pattern():
    """Diamond: A,B -> C should be batch [A,B] then [C]."""
    stages = [
        _make_stage("1"),
        _make_stage("2"),
        _make_stage("3", depends_on=["1", "2"]),
    ]
    plan = compute_execution_batches(stages, skip_completed=False)

    assert plan.total_batches == 2
    assert sorted(plan.batches[0].stage_numbers) == ["1", "2"]
    assert plan.batches[1].stage_numbers == ["3"]


def test_compute_skip_completed_stages():
    """Completed stages should be skipped."""
    stages = [
        _make_stage("1", status=StageStatus.COMPLETED),
        _make_stage("2", depends_on=["1"]),
        _make_stage("3", depends_on=["1"]),
    ]
    plan = compute_execution_batches(stages, skip_completed=True)

    assert plan.total_batches == 1
    assert plan.total_stages == 2
    assert sorted(plan.batches[0].stage_numbers) == ["2", "3"]


def test_compute_skip_completed_deps_satisfied():
    """Completed deps should be treated as satisfied."""
    stages = [
        _make_stage("1", status=StageStatus.COMPLETED),
        _make_stage("2", depends_on=["1"]),
    ]
    plan = compute_execution_batches(stages, skip_completed=True)

    assert plan.total_batches == 1
    assert plan.batches[0].stage_numbers == ["2"]
    # Stage 2's dependency on stage 1 is satisfied because stage 1 is completed


def test_compute_all_completed():
    """All stages completed should produce empty plan."""
    stages = [
        _make_stage("1", status=StageStatus.COMPLETED),
        _make_stage("2", status=StageStatus.COMPLETED),
    ]
    plan = compute_execution_batches(stages, skip_completed=True)
    assert plan.total_batches == 0
    assert plan.total_stages == 0


def test_compute_empty_stages():
    """Empty stage list should produce empty plan."""
    plan = compute_execution_batches([], skip_completed=True)
    assert plan.total_batches == 0


def test_compute_single_stage():
    """Single stage should be in one batch."""
    stages = [_make_stage("1")]
    plan = compute_execution_batches(stages, skip_completed=False)

    assert plan.total_batches == 1
    assert plan.batches[0].stage_numbers == ["1"]


def test_compute_complex_graph():
    """Complex graph with multiple levels."""
    # Graph: 1->3, 2->3, 3->5, 4->5
    # Levels: [1,2,4], [3], [5]
    stages = [
        _make_stage("1"),
        _make_stage("2"),
        _make_stage("3", depends_on=["1", "2"]),
        _make_stage("4"),
        _make_stage("5", depends_on=["3", "4"]),
    ]
    plan = compute_execution_batches(stages, skip_completed=False)

    assert plan.total_batches == 3
    assert sorted(plan.batches[0].stage_numbers) == ["1", "2", "4"]
    assert plan.batches[1].stage_numbers == ["3"]
    assert plan.batches[2].stage_numbers == ["5"]


def test_compute_batch_levels():
    """Verify batch level numbers are sequential."""
    stages = [
        _make_stage("1"),
        _make_stage("2", depends_on=["1"]),
        _make_stage("3", depends_on=["2"]),
    ]
    plan = compute_execution_batches(stages, skip_completed=False)

    for i, batch in enumerate(plan.batches):
        assert batch.level == i


def test_get_ready_stages_no_deps():
    """All pending stages with no deps should be ready."""
    stages = [_make_stage("1"), _make_stage("2"), _make_stage("3")]
    ready = get_ready_stages(stages)
    assert len(ready) == 3


def test_get_ready_stages_deps_satisfied():
    """Stages with completed dependencies should be ready."""
    stages = [
        _make_stage("1", status=StageStatus.COMPLETED),
        _make_stage("2", depends_on=["1"]),
    ]
    ready = get_ready_stages(stages)
    assert len(ready) == 1
    assert ready[0].number == "2"


def test_get_ready_stages_deps_not_satisfied():
    """Stages with pending dependencies should not be ready."""
    stages = [
        _make_stage("1"),
        _make_stage("2", depends_on=["1"]),
    ]
    ready = get_ready_stages(stages)
    assert len(ready) == 1
    assert ready[0].number == "1"  # Only stage 1 is ready


def test_get_ready_stages_in_progress_excluded():
    """In-progress stages should not be in the ready list."""
    stages = [
        _make_stage("1", status=StageStatus.IN_PROGRESS),
        _make_stage("2", depends_on=["1"]),
    ]
    ready = get_ready_stages(stages)
    assert len(ready) == 0


def test_get_ready_stages_skipped_satisfies_deps():
    """Skipped stages should satisfy dependencies."""
    stages = [
        _make_stage("1", status=StageStatus.SKIPPED),
        _make_stage("2", depends_on=["1"]),
    ]
    ready = get_ready_stages(stages)
    assert len(ready) == 1
    assert ready[0].number == "2"


def test_execution_plan_properties():
    """Test ExecutionPlan model properties."""
    plan = ExecutionPlan(
        batches=[
            ExecutionBatch(level=0, stage_numbers=["1", "2"]),
            ExecutionBatch(level=1, stage_numbers=["3"]),
        ]
    )
    assert plan.total_batches == 2
    assert plan.total_stages == 3


def test_dependency_error_model():
    """Test DependencyError model construction."""
    err = DependencyError(error_type="cycle", details="cycle in 1,2")
    assert err.error_type == "cycle"
    assert err.details == "cycle in 1,2"

    err2 = DependencyError(error_type="missing_ref", details="stage 99 not found")
    assert err2.error_type == "missing_ref"


def test_compute_skipped_stages_excluded():
    """Skipped stages should be excluded from batches."""
    stages = [
        _make_stage("1", status=StageStatus.SKIPPED),
        _make_stage("2", depends_on=["1"]),
    ]
    plan = compute_execution_batches(stages, skip_completed=True)
    assert plan.total_batches == 1
    assert plan.batches[0].stage_numbers == ["2"]
