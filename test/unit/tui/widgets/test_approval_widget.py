"""Unit tests for PlanApprovalWidget."""

import pytest

from shotgun.agents.router.models import ExecutionPlan, ExecutionStep
from shotgun.tui.screens.chat_screen.messages import (
    PlanApproved,
    PlanRejected,
)
from shotgun.tui.widgets.approval_widget import PlanApprovalWidget

pytestmark = pytest.mark.asyncio


@pytest.fixture
def multi_step_plan() -> ExecutionPlan:
    """Create a sample multi-step plan for testing."""
    return ExecutionPlan(
        goal="Implement OAuth authentication",
        steps=[
            ExecutionStep(
                id="research-oauth",
                title="Research OAuth providers",
                objective="Research available OAuth providers and their integration patterns",
                done=False,
            ),
            ExecutionStep(
                id="implement-oauth",
                title="Implement OAuth flow",
                objective="Implement OAuth 2.0 authentication flow",
                done=False,
            ),
            ExecutionStep(
                id="test-oauth",
                title="Write OAuth tests",
                objective="Write unit tests for OAuth implementation",
                done=False,
            ),
        ],
        current_step_index=0,
    )


# =============================================================================
# Property Tests
# =============================================================================


async def test_approval_widget_stores_plan(multi_step_plan: ExecutionPlan) -> None:
    """Test that the approval widget stores the plan."""
    widget = PlanApprovalWidget(multi_step_plan)
    assert widget.plan == multi_step_plan


async def test_approval_widget_plan_has_correct_goal(
    multi_step_plan: ExecutionPlan,
) -> None:
    """Test that the stored plan has the correct goal."""
    widget = PlanApprovalWidget(multi_step_plan)
    assert widget.plan.goal == "Implement OAuth authentication"


async def test_approval_widget_plan_has_correct_step_count(
    multi_step_plan: ExecutionPlan,
) -> None:
    """Test that the stored plan has the correct number of steps."""
    widget = PlanApprovalWidget(multi_step_plan)
    assert len(widget.plan.steps) == 3


# =============================================================================
# Button Tests
# =============================================================================


async def test_approval_widget_has_two_buttons(
    multi_step_plan: ExecutionPlan,
) -> None:
    """Test that the widget has approve and reject buttons."""
    from textual.app import App

    class TestApp(App):
        def compose(self):
            yield PlanApprovalWidget(multi_step_plan)

    async with TestApp().run_test() as pilot:
        buttons = pilot.app.query("Button")
        assert len(buttons) == 2

        button_ids = {btn.id for btn in buttons}
        assert "btn-approve" in button_ids
        assert "btn-reject" in button_ids


# =============================================================================
# Message Tests - Button Clicks
# =============================================================================


async def test_approve_button_posts_plan_approved(
    multi_step_plan: ExecutionPlan,
) -> None:
    """Test that clicking Go Ahead posts PlanApproved message."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield PlanApprovalWidget(multi_step_plan)

        def on_plan_approved(self, event: PlanApproved) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        await pilot.click("#btn-approve")

        assert len(messages_received) == 1
        assert isinstance(messages_received[0], PlanApproved)


async def test_reject_button_posts_plan_rejected(
    multi_step_plan: ExecutionPlan,
) -> None:
    """Test that clicking No, Let Me Clarify posts PlanRejected message."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield PlanApprovalWidget(multi_step_plan)

        def on_plan_rejected(self, event: PlanRejected) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        await pilot.click("#btn-reject")

        assert len(messages_received) == 1
        assert isinstance(messages_received[0], PlanRejected)


# =============================================================================
# Keyboard Shortcut Tests
# =============================================================================


async def test_keyboard_shortcut_enter_posts_approved(
    multi_step_plan: ExecutionPlan,
) -> None:
    """Test that pressing Enter triggers approve action."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield PlanApprovalWidget(multi_step_plan)

        def on_plan_approved(self, event: PlanApproved) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        await pilot.press("enter")

        assert len(messages_received) == 1
        assert isinstance(messages_received[0], PlanApproved)


async def test_keyboard_shortcut_y_posts_approved(
    multi_step_plan: ExecutionPlan,
) -> None:
    """Test that pressing 'y' triggers approve action."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield PlanApprovalWidget(multi_step_plan)

        def on_plan_approved(self, event: PlanApproved) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        await pilot.press("y")

        assert len(messages_received) == 1
        assert isinstance(messages_received[0], PlanApproved)


async def test_keyboard_shortcut_upper_y_posts_approved(
    multi_step_plan: ExecutionPlan,
) -> None:
    """Test that pressing 'Y' triggers approve action."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield PlanApprovalWidget(multi_step_plan)

        def on_plan_approved(self, event: PlanApproved) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        await pilot.press("Y")

        assert len(messages_received) == 1
        assert isinstance(messages_received[0], PlanApproved)


async def test_keyboard_shortcut_escape_posts_rejected(
    multi_step_plan: ExecutionPlan,
) -> None:
    """Test that pressing Escape triggers reject action."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield PlanApprovalWidget(multi_step_plan)

        def on_plan_rejected(self, event: PlanRejected) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        await pilot.press("escape")

        assert len(messages_received) == 1
        assert isinstance(messages_received[0], PlanRejected)


async def test_keyboard_shortcut_n_posts_rejected(
    multi_step_plan: ExecutionPlan,
) -> None:
    """Test that pressing 'n' triggers reject action."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield PlanApprovalWidget(multi_step_plan)

        def on_plan_rejected(self, event: PlanRejected) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        await pilot.press("n")

        assert len(messages_received) == 1
        assert isinstance(messages_received[0], PlanRejected)


async def test_keyboard_shortcut_upper_n_posts_rejected(
    multi_step_plan: ExecutionPlan,
) -> None:
    """Test that pressing 'N' triggers reject action."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield PlanApprovalWidget(multi_step_plan)

        def on_plan_rejected(self, event: PlanRejected) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        await pilot.press("N")

        assert len(messages_received) == 1
        assert isinstance(messages_received[0], PlanRejected)


# =============================================================================
# Focus Tests
# =============================================================================


async def test_approve_button_auto_focused_on_mount(
    multi_step_plan: ExecutionPlan,
) -> None:
    """Test that the Go Ahead button is auto-focused on mount."""
    from textual.app import App
    from textual.widgets import Button

    class TestApp(App):
        def compose(self):
            yield PlanApprovalWidget(multi_step_plan)

    async with TestApp().run_test() as pilot:
        approve_btn = pilot.app.query_one("#btn-approve", Button)
        assert approve_btn.has_focus
