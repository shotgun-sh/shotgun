"""Tests for router agent plan tools."""

from unittest.mock import MagicMock, patch

import pytest

from shotgun.agents.router.models import ExecutionPlan, ExecutionStep
from shotgun.agents.router.tools.plan_tools import (
    add_step,
    clear_plan,
    create_plan,
    get_plan,
    mark_step_done,
    remove_step,
    reorder_steps,
    update_step,
)


@pytest.fixture
def mock_run_context():
    """Create a mock RunContext."""
    ctx = MagicMock()
    ctx.deps = MagicMock()
    return ctx


@pytest.fixture
def sample_steps():
    """Sample step definitions for testing."""
    return [
        {
            "id": "step-1",
            "title": "Research",
            "objective": "Research the topic",
            "affects_files": ["research.md"],
        },
        {
            "id": "step-2",
            "title": "Specify",
            "objective": "Write specification",
            "affects_files": ["specification.md"],
        },
    ]


@pytest.fixture
def sample_plan():
    """Create a sample execution plan."""
    return ExecutionPlan(
        goal="Test goal",
        steps=[
            ExecutionStep(id="step-1", title="Step 1", objective="First"),
            ExecutionStep(id="step-2", title="Step 2", objective="Second"),
            ExecutionStep(id="step-3", title="Step 3", objective="Third"),
        ],
    )


@pytest.mark.asyncio
async def test_create_plan(mock_run_context, sample_steps):
    """Test creating a new plan."""
    with patch(
        "shotgun.agents.router.tools.plan_tools.save_plan"
    ) as mock_save:
        result = await create_plan(
            mock_run_context,
            goal="Test goal",
            steps=sample_steps,
        )

        mock_save.assert_called_once()
        saved_plan = mock_save.call_args[0][0]

        assert saved_plan.goal == "Test goal"
        assert len(saved_plan.steps) == 2
        assert saved_plan.steps[0].id == "step-1"
        assert saved_plan.steps[0].title == "Research"
        assert saved_plan.steps[0].affects_files == ["research.md"]
        assert saved_plan.current_step_index == 0

        assert "Created plan" in result


@pytest.mark.asyncio
async def test_create_plan_generates_ids(mock_run_context):
    """Test that create_plan generates IDs for steps without them."""
    steps = [
        {"title": "Step 1", "objective": "First"},
        {"title": "Step 2", "objective": "Second"},
    ]

    with patch(
        "shotgun.agents.router.tools.plan_tools.save_plan"
    ) as mock_save:
        await create_plan(mock_run_context, goal="Test", steps=steps)

        saved_plan = mock_save.call_args[0][0]
        # Both steps should have IDs
        assert saved_plan.steps[0].id is not None
        assert saved_plan.steps[1].id is not None
        # IDs should be different
        assert saved_plan.steps[0].id != saved_plan.steps[1].id


@pytest.mark.asyncio
async def test_get_plan_exists(mock_run_context, sample_plan):
    """Test getting an existing plan."""
    with patch(
        "shotgun.agents.router.tools.plan_tools.load_plan",
        return_value=sample_plan,
    ):
        result = await get_plan(mock_run_context)

        assert "Test goal" in result
        assert "Step 1" in result
        assert "Step 2" in result
        assert "Step 3" in result


@pytest.mark.asyncio
async def test_get_plan_not_exists(mock_run_context):
    """Test getting when no plan exists."""
    with patch(
        "shotgun.agents.router.tools.plan_tools.load_plan",
        return_value=None,
    ):
        result = await get_plan(mock_run_context)

        assert "No execution plan exists" in result


@pytest.mark.asyncio
async def test_mark_step_done(mock_run_context, sample_plan):
    """Test marking a step as done."""
    with (
        patch(
            "shotgun.agents.router.tools.plan_tools.load_plan",
            return_value=sample_plan,
        ),
        patch(
            "shotgun.agents.router.tools.plan_tools.save_plan"
        ) as mock_save,
    ):
        result = await mark_step_done(mock_run_context, "step-2")

        mock_save.assert_called_once()
        saved_plan = mock_save.call_args[0][0]

        assert saved_plan.steps[1].done is True
        assert "complete" in result.lower()


@pytest.mark.asyncio
async def test_mark_step_done_advances_index(mock_run_context):
    """Test that marking current step done advances the index."""
    plan = ExecutionPlan(
        goal="Test",
        steps=[
            ExecutionStep(id="1", title="First", objective="1"),
            ExecutionStep(id="2", title="Second", objective="2"),
        ],
        current_step_index=0,
    )

    with (
        patch(
            "shotgun.agents.router.tools.plan_tools.load_plan",
            return_value=plan,
        ),
        patch(
            "shotgun.agents.router.tools.plan_tools.save_plan"
        ) as mock_save,
    ):
        await mark_step_done(mock_run_context, "1")

        saved_plan = mock_save.call_args[0][0]
        assert saved_plan.current_step_index == 1


@pytest.mark.asyncio
async def test_mark_step_done_not_found(mock_run_context, sample_plan):
    """Test marking a non-existent step as done."""
    with patch(
        "shotgun.agents.router.tools.plan_tools.load_plan",
        return_value=sample_plan,
    ):
        result = await mark_step_done(mock_run_context, "nonexistent")

        assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_mark_step_done_no_plan(mock_run_context):
    """Test marking step done when no plan exists."""
    with patch(
        "shotgun.agents.router.tools.plan_tools.load_plan",
        return_value=None,
    ):
        result = await mark_step_done(mock_run_context, "step-1")

        assert "No execution plan exists" in result


@pytest.mark.asyncio
async def test_add_step_at_end(mock_run_context, sample_plan):
    """Test adding a step at the end."""
    new_step = {"id": "new", "title": "New Step", "objective": "New"}

    with (
        patch(
            "shotgun.agents.router.tools.plan_tools.load_plan",
            return_value=sample_plan,
        ),
        patch(
            "shotgun.agents.router.tools.plan_tools.save_plan"
        ) as mock_save,
    ):
        result = await add_step(mock_run_context, new_step)

        saved_plan = mock_save.call_args[0][0]
        assert len(saved_plan.steps) == 4
        assert saved_plan.steps[-1].id == "new"
        assert "at end" in result.lower()


@pytest.mark.asyncio
async def test_add_step_after_specific(mock_run_context, sample_plan):
    """Test adding a step after a specific step."""
    new_step = {"id": "new", "title": "New Step", "objective": "New"}

    with (
        patch(
            "shotgun.agents.router.tools.plan_tools.load_plan",
            return_value=sample_plan,
        ),
        patch(
            "shotgun.agents.router.tools.plan_tools.save_plan"
        ) as mock_save,
    ):
        result = await add_step(mock_run_context, new_step, after_step_id="step-1")

        saved_plan = mock_save.call_args[0][0]
        assert len(saved_plan.steps) == 4
        # New step should be at index 1 (after step-1 which is at index 0)
        assert saved_plan.steps[1].id == "new"
        assert "after" in result.lower()


@pytest.mark.asyncio
async def test_add_step_after_not_found(mock_run_context, sample_plan):
    """Test adding a step after non-existent step."""
    new_step = {"id": "new", "title": "New", "objective": "New"}

    with patch(
        "shotgun.agents.router.tools.plan_tools.load_plan",
        return_value=sample_plan,
    ):
        result = await add_step(mock_run_context, new_step, after_step_id="nonexistent")

        assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_remove_step(mock_run_context, sample_plan):
    """Test removing a step."""
    with (
        patch(
            "shotgun.agents.router.tools.plan_tools.load_plan",
            return_value=sample_plan,
        ),
        patch(
            "shotgun.agents.router.tools.plan_tools.save_plan"
        ) as mock_save,
    ):
        result = await remove_step(mock_run_context, "step-2")

        saved_plan = mock_save.call_args[0][0]
        assert len(saved_plan.steps) == 2
        assert all(s.id != "step-2" for s in saved_plan.steps)
        assert "removed" in result.lower()


@pytest.mark.asyncio
async def test_remove_step_not_found(mock_run_context, sample_plan):
    """Test removing a non-existent step."""
    with patch(
        "shotgun.agents.router.tools.plan_tools.load_plan",
        return_value=sample_plan,
    ):
        result = await remove_step(mock_run_context, "nonexistent")

        assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_update_step(mock_run_context, sample_plan):
    """Test updating a step."""
    updates = {"title": "Updated Title", "done": True}

    with (
        patch(
            "shotgun.agents.router.tools.plan_tools.load_plan",
            return_value=sample_plan,
        ),
        patch(
            "shotgun.agents.router.tools.plan_tools.save_plan"
        ) as mock_save,
    ):
        result = await update_step(mock_run_context, "step-2", updates)

        saved_plan = mock_save.call_args[0][0]
        assert saved_plan.steps[1].title == "Updated Title"
        assert saved_plan.steps[1].done is True
        assert "updated" in result.lower()


@pytest.mark.asyncio
async def test_update_step_not_found(mock_run_context, sample_plan):
    """Test updating a non-existent step."""
    with patch(
        "shotgun.agents.router.tools.plan_tools.load_plan",
        return_value=sample_plan,
    ):
        result = await update_step(mock_run_context, "nonexistent", {"title": "X"})

        assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_reorder_steps(mock_run_context, sample_plan):
    """Test reordering steps."""
    new_order = ["step-3", "step-1", "step-2"]

    with (
        patch(
            "shotgun.agents.router.tools.plan_tools.load_plan",
            return_value=sample_plan,
        ),
        patch(
            "shotgun.agents.router.tools.plan_tools.save_plan"
        ) as mock_save,
    ):
        result = await reorder_steps(mock_run_context, new_order)

        saved_plan = mock_save.call_args[0][0]
        assert saved_plan.steps[0].id == "step-3"
        assert saved_plan.steps[1].id == "step-1"
        assert saved_plan.steps[2].id == "step-2"
        assert "reordered" in result.lower()


@pytest.mark.asyncio
async def test_reorder_steps_missing_id(mock_run_context, sample_plan):
    """Test reordering with missing step ID."""
    new_order = ["step-1", "step-2"]  # Missing step-3

    with patch(
        "shotgun.agents.router.tools.plan_tools.load_plan",
        return_value=sample_plan,
    ):
        result = await reorder_steps(mock_run_context, new_order)

        assert "mismatch" in result.lower() or "missing" in result.lower()


@pytest.mark.asyncio
async def test_reorder_steps_extra_id(mock_run_context, sample_plan):
    """Test reordering with extra step ID."""
    new_order = ["step-1", "step-2", "step-3", "extra"]

    with patch(
        "shotgun.agents.router.tools.plan_tools.load_plan",
        return_value=sample_plan,
    ):
        result = await reorder_steps(mock_run_context, new_order)

        assert "mismatch" in result.lower() or "unknown" in result.lower()


@pytest.mark.asyncio
async def test_clear_plan_exists(mock_run_context):
    """Test clearing an existing plan."""
    with patch(
        "shotgun.agents.router.tools.plan_tools.delete_plan",
        return_value=True,
    ):
        result = await clear_plan(mock_run_context)

        assert "deleted" in result.lower()


@pytest.mark.asyncio
async def test_clear_plan_not_exists(mock_run_context):
    """Test clearing when no plan exists."""
    with patch(
        "shotgun.agents.router.tools.plan_tools.delete_plan",
        return_value=False,
    ):
        result = await clear_plan(mock_run_context)

        assert "no" in result.lower()
