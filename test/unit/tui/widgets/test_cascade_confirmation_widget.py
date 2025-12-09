"""Unit tests for CascadeConfirmationWidget."""

import pytest

from shotgun.agents.router.models import CascadeScope
from shotgun.tui.screens.chat_screen.messages import (
    CascadeConfirmed,
    CascadeDeclined,
)
from shotgun.tui.widgets.cascade_confirmation_widget import CascadeConfirmationWidget

pytestmark = pytest.mark.asyncio


# =============================================================================
# Property Tests
# =============================================================================


async def test_cascade_widget_stores_updated_file() -> None:
    """Test that the cascade widget stores the updated file."""
    widget = CascadeConfirmationWidget("specification.md", ["plan.md", "tasks.md"])
    assert widget.updated_file == "specification.md"


async def test_cascade_widget_stores_dependent_files() -> None:
    """Test that the cascade widget stores the dependent files list."""
    widget = CascadeConfirmationWidget("specification.md", ["plan.md", "tasks.md"])
    assert widget.dependent_files == ["plan.md", "tasks.md"]


async def test_cascade_widget_handles_empty_dependent_files() -> None:
    """Test that the cascade widget handles an empty dependent files list."""
    widget = CascadeConfirmationWidget("tasks.md", [])
    assert widget.dependent_files == []


# =============================================================================
# Button Tests
# =============================================================================


async def test_cascade_widget_shows_four_buttons_for_spec_update() -> None:
    """Test that spec update shows all four buttons (Update all, Just plan.md, Just tasks.md, Decline)."""
    from textual.app import App

    class TestApp(App):
        def compose(self):
            yield CascadeConfirmationWidget("specification.md", ["plan.md", "tasks.md"])

    async with TestApp().run_test() as pilot:
        buttons = pilot.app.query("Button")
        assert len(buttons) == 4

        button_ids = {btn.id for btn in buttons}
        assert "btn-update-all" in button_ids
        assert "btn-plan-only" in button_ids
        assert "btn-tasks-only" in button_ids
        assert "btn-decline" in button_ids


async def test_cascade_widget_shows_two_buttons_for_plan_update() -> None:
    """Test that plan update shows only two buttons (Update all, Decline)."""
    from textual.app import App

    class TestApp(App):
        def compose(self):
            yield CascadeConfirmationWidget("plan.md", ["tasks.md"])

    async with TestApp().run_test() as pilot:
        buttons = pilot.app.query("Button")
        assert len(buttons) == 2

        button_ids = {btn.id for btn in buttons}
        assert "btn-update-all" in button_ids
        assert "btn-decline" in button_ids
        # Selective buttons shouldn't appear with only one dependent
        assert "btn-plan-only" not in button_ids
        assert "btn-tasks-only" not in button_ids


async def test_cascade_widget_shows_only_decline_for_no_dependents() -> None:
    """Test that widget with no dependents shows only decline button."""
    from textual.app import App

    class TestApp(App):
        def compose(self):
            yield CascadeConfirmationWidget("tasks.md", [])

    async with TestApp().run_test() as pilot:
        buttons = pilot.app.query("Button")
        assert len(buttons) == 1

        button_ids = {btn.id for btn in buttons}
        assert "btn-decline" in button_ids


# =============================================================================
# Message Tests - Button Clicks
# =============================================================================


async def test_update_all_button_posts_cascade_confirmed_all() -> None:
    """Test that clicking Update all posts CascadeConfirmed with ALL scope."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield CascadeConfirmationWidget("specification.md", ["plan.md", "tasks.md"])

        def on_cascade_confirmed(self, event: CascadeConfirmed) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        await pilot.click("#btn-update-all")

        assert len(messages_received) == 1
        assert isinstance(messages_received[0], CascadeConfirmed)
        assert messages_received[0].scope == CascadeScope.ALL


async def test_plan_only_button_posts_cascade_confirmed_plan_only() -> None:
    """Test that clicking Just plan.md posts CascadeConfirmed with PLAN_ONLY scope."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield CascadeConfirmationWidget("specification.md", ["plan.md", "tasks.md"])

        def on_cascade_confirmed(self, event: CascadeConfirmed) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        await pilot.click("#btn-plan-only")

        assert len(messages_received) == 1
        assert isinstance(messages_received[0], CascadeConfirmed)
        assert messages_received[0].scope == CascadeScope.PLAN_ONLY


async def test_tasks_only_button_posts_cascade_confirmed_tasks_only() -> None:
    """Test that clicking Just tasks.md posts CascadeConfirmed with TASKS_ONLY scope."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield CascadeConfirmationWidget("specification.md", ["plan.md", "tasks.md"])

        def on_cascade_confirmed(self, event: CascadeConfirmed) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        await pilot.click("#btn-tasks-only")

        assert len(messages_received) == 1
        assert isinstance(messages_received[0], CascadeConfirmed)
        assert messages_received[0].scope == CascadeScope.TASKS_ONLY


async def test_decline_button_posts_cascade_declined() -> None:
    """Test that clicking decline button posts CascadeDeclined message."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield CascadeConfirmationWidget("specification.md", ["plan.md", "tasks.md"])

        def on_cascade_declined(self, event: CascadeDeclined) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        await pilot.click("#btn-decline")

        assert len(messages_received) == 1
        assert isinstance(messages_received[0], CascadeDeclined)


# =============================================================================
# Keyboard Shortcut Tests
# =============================================================================


async def test_keyboard_shortcut_a_posts_update_all() -> None:
    """Test that pressing 'a' triggers update all action."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield CascadeConfirmationWidget("specification.md", ["plan.md", "tasks.md"])

        def on_cascade_confirmed(self, event: CascadeConfirmed) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        await pilot.press("a")

        assert len(messages_received) == 1
        assert messages_received[0].scope == CascadeScope.ALL


async def test_keyboard_shortcut_enter_posts_update_all() -> None:
    """Test that pressing Enter triggers update all action."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield CascadeConfirmationWidget("specification.md", ["plan.md", "tasks.md"])

        def on_cascade_confirmed(self, event: CascadeConfirmed) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        await pilot.press("enter")

        assert len(messages_received) == 1
        assert messages_received[0].scope == CascadeScope.ALL


async def test_keyboard_shortcut_p_posts_plan_only() -> None:
    """Test that pressing 'p' triggers plan only action when available."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield CascadeConfirmationWidget("specification.md", ["plan.md", "tasks.md"])

        def on_cascade_confirmed(self, event: CascadeConfirmed) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        await pilot.press("p")

        assert len(messages_received) == 1
        assert messages_received[0].scope == CascadeScope.PLAN_ONLY


async def test_keyboard_shortcut_t_posts_tasks_only() -> None:
    """Test that pressing 't' triggers tasks only action when available."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield CascadeConfirmationWidget("specification.md", ["plan.md", "tasks.md"])

        def on_cascade_confirmed(self, event: CascadeConfirmed) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        await pilot.press("t")

        assert len(messages_received) == 1
        assert messages_received[0].scope == CascadeScope.TASKS_ONLY


async def test_keyboard_shortcut_n_posts_declined() -> None:
    """Test that pressing 'n' triggers decline action."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield CascadeConfirmationWidget("specification.md", ["plan.md", "tasks.md"])

        def on_cascade_declined(self, event: CascadeDeclined) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        await pilot.press("n")

        assert len(messages_received) == 1
        assert isinstance(messages_received[0], CascadeDeclined)


async def test_keyboard_shortcut_escape_posts_declined() -> None:
    """Test that pressing Escape triggers decline action."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield CascadeConfirmationWidget("specification.md", ["plan.md", "tasks.md"])

        def on_cascade_declined(self, event: CascadeDeclined) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        await pilot.press("escape")

        assert len(messages_received) == 1
        assert isinstance(messages_received[0], CascadeDeclined)


# =============================================================================
# Edge Cases
# =============================================================================


async def test_keyboard_p_does_nothing_with_single_dependent() -> None:
    """Test that 'p' doesn't trigger plan only when there's only one dependent."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            # Only tasks.md as dependent - 'p' should do nothing
            yield CascadeConfirmationWidget("plan.md", ["tasks.md"])

        def on_cascade_confirmed(self, event: CascadeConfirmed) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        await pilot.press("p")

        # No message should be posted since plan.md isn't in dependents
        # or there's only one dependent
        assert len(messages_received) == 0


async def test_keyboard_t_does_nothing_with_single_non_tasks_dependent() -> None:
    """Test that 't' doesn't trigger tasks only when tasks.md isn't a dependent."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            # Only plan.md as dependent - 't' should do nothing
            yield CascadeConfirmationWidget("research.md", ["specification.md"])

        def on_cascade_confirmed(self, event: CascadeConfirmed) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        await pilot.press("t")

        # No message should be posted
        assert len(messages_received) == 0


async def test_keyboard_a_does_nothing_with_no_dependents() -> None:
    """Test that 'a' doesn't trigger update all when there are no dependents."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield CascadeConfirmationWidget("tasks.md", [])

        def on_cascade_confirmed(self, event: CascadeConfirmed) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        await pilot.press("a")

        # No message should be posted since there are no dependents
        assert len(messages_received) == 0
