"""Unit tests for PlanPanelWidget."""

import pytest
from textual.app import App

from shotgun.agents.router.models import ExecutionPlan, ExecutionStep
from shotgun.tui.screens.chat_screen.messages import PlanPanelClosed
from shotgun.tui.widgets.plan_panel import PlanPanelWidget

pytestmark = pytest.mark.asyncio


@pytest.fixture
def sample_plan() -> ExecutionPlan:
    """Create a sample plan for testing."""
    return ExecutionPlan(
        goal="Implement OAuth authentication",
        steps=[
            ExecutionStep(
                id="research",
                title="Research OAuth",
                objective="Research OAuth providers",
                done=True,
            ),
            ExecutionStep(
                id="implement",
                title="Implement OAuth",
                objective="Implement OAuth flow",
                done=False,
            ),
        ],
        current_step_index=1,
    )


@pytest.fixture
def completed_plan() -> ExecutionPlan:
    """Create a fully completed plan for testing."""
    return ExecutionPlan(
        goal="Simple task",
        steps=[
            ExecutionStep(
                id="step1",
                title="Step 1",
                objective="Complete the task",
                done=True,
            ),
        ],
        current_step_index=0,
    )


# =============================================================================
# Property Tests
# =============================================================================


async def test_plan_panel_stores_plan(sample_plan: ExecutionPlan) -> None:
    """Test that the plan panel stores the plan."""
    widget = PlanPanelWidget(sample_plan)
    assert widget.plan == sample_plan


async def test_plan_panel_has_correct_goal(sample_plan: ExecutionPlan) -> None:
    """Test that the stored plan has the correct goal."""
    widget = PlanPanelWidget(sample_plan)
    assert widget.plan.goal == "Implement OAuth authentication"


async def test_plan_panel_has_correct_step_count(sample_plan: ExecutionPlan) -> None:
    """Test that the stored plan has the correct number of steps."""
    widget = PlanPanelWidget(sample_plan)
    assert len(widget.plan.steps) == 2


async def test_plan_panel_update_plan(
    sample_plan: ExecutionPlan, completed_plan: ExecutionPlan
) -> None:
    """Test that updating the plan changes the stored plan."""
    widget = PlanPanelWidget(sample_plan)
    widget.update_plan(completed_plan)
    assert widget.plan == completed_plan


# =============================================================================
# Render Tests
# =============================================================================


async def test_plan_panel_composes_without_error(sample_plan: ExecutionPlan) -> None:
    """Test that the plan panel composes without errors."""

    class TestApp(App):
        def compose(self):
            yield PlanPanelWidget(sample_plan)

    async with TestApp().run_test() as pilot:
        # Just verify the widget mounts successfully
        widgets = pilot.app.query(PlanPanelWidget)
        assert len(widgets) == 1


async def test_plan_panel_has_static_widgets(sample_plan: ExecutionPlan) -> None:
    """Test that the plan panel contains Static widgets."""

    class TestApp(App):
        def compose(self):
            yield PlanPanelWidget(sample_plan)

    async with TestApp().run_test() as pilot:
        # The panel should contain Static widgets for goal and steps
        statics = pilot.app.query("Static")
        # Header + goal + 2 steps = 4 Static widgets
        assert len(statics) == 4


async def test_plan_panel_has_correct_structure(sample_plan: ExecutionPlan) -> None:
    """Test that the plan panel has the correct widget structure."""

    class TestApp(App):
        def compose(self):
            yield PlanPanelWidget(sample_plan)

    async with TestApp().run_test() as pilot:
        # Should have a Horizontal container for the header row
        horizontals = pilot.app.query("Horizontal")
        assert len(horizontals) == 1


# =============================================================================
# Close Button Tests
# =============================================================================


async def test_close_button_posts_panel_closed_message(
    sample_plan: ExecutionPlan,
) -> None:
    """Test that clicking the close button posts PlanPanelClosed."""
    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield PlanPanelWidget(sample_plan)

        def on_plan_panel_closed(self, event: PlanPanelClosed) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        await pilot.click("#btn-close")
        assert len(messages_received) == 1
        assert isinstance(messages_received[0], PlanPanelClosed)


async def test_plan_panel_has_close_button(sample_plan: ExecutionPlan) -> None:
    """Test that the plan panel has a close button."""

    class TestApp(App):
        def compose(self):
            yield PlanPanelWidget(sample_plan)

    async with TestApp().run_test() as pilot:
        buttons = pilot.app.query("Button")
        button_ids = {btn.id for btn in buttons}
        assert "btn-close" in button_ids
