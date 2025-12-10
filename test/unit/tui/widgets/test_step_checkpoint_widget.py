"""Unit tests for StepCheckpointWidget."""

import pytest

from shotgun.agents.router.models import ExecutionStep
from shotgun.tui.screens.chat_screen.messages import (
    CheckpointContinue,
    CheckpointModify,
    CheckpointStop,
)
from shotgun.tui.widgets.step_checkpoint_widget import StepCheckpointWidget

pytestmark = pytest.mark.asyncio


@pytest.fixture
def completed_step() -> ExecutionStep:
    """Create a sample completed step."""
    return ExecutionStep(
        id="research-oauth",
        title="Research OAuth providers",
        objective="Research available OAuth providers and their integration patterns",
        done=True,
    )


@pytest.fixture
def next_step() -> ExecutionStep:
    """Create a sample next step."""
    return ExecutionStep(
        id="implement-oauth",
        title="Implement OAuth flow",
        objective="Implement OAuth 2.0 authentication flow",
        done=False,
    )


async def test_checkpoint_widget_shows_completed_step_title(
    completed_step: ExecutionStep, next_step: ExecutionStep
) -> None:
    """Test that the checkpoint widget displays the completed step title."""
    widget = StepCheckpointWidget(completed_step, next_step)

    # Verify step and next_step are stored
    assert widget.step == completed_step
    assert widget.next_step == next_step


async def test_checkpoint_widget_shows_next_step_preview(
    completed_step: ExecutionStep, next_step: ExecutionStep
) -> None:
    """Test that the checkpoint widget shows the next step preview."""
    widget = StepCheckpointWidget(completed_step, next_step)

    # Verify next_step is stored
    assert widget.next_step is not None
    assert widget.next_step.title == "Implement OAuth flow"


async def test_checkpoint_widget_handles_no_next_step(
    completed_step: ExecutionStep,
) -> None:
    """Test that the checkpoint widget handles being the last step."""
    widget = StepCheckpointWidget(completed_step, next_step=None)

    # Verify next_step is None
    assert widget.next_step is None


async def test_checkpoint_widget_has_three_buttons_with_next_step(
    completed_step: ExecutionStep, next_step: ExecutionStep
) -> None:
    """Test that the widget has all three buttons when there's a next step."""
    from textual.app import App

    class TestApp(App):
        def compose(self):
            yield StepCheckpointWidget(completed_step, next_step)

    async with TestApp().run_test() as pilot:
        # Query for buttons
        buttons = pilot.app.query("Button")
        assert len(buttons) == 3

        # Verify button IDs
        button_ids = {btn.id for btn in buttons}
        assert "btn-continue" in button_ids
        assert "btn-modify" in button_ids
        assert "btn-stop" in button_ids


async def test_checkpoint_widget_has_done_button_without_next_step(
    completed_step: ExecutionStep,
) -> None:
    """Test that only Done button is shown when plan is complete (no next step)."""
    from textual.app import App

    class TestApp(App):
        def compose(self):
            yield StepCheckpointWidget(completed_step, next_step=None)

    async with TestApp().run_test() as pilot:
        # Query for buttons
        buttons = pilot.app.query("Button")
        assert len(buttons) == 1

        # Verify only Done button is present
        button_ids = {btn.id for btn in buttons}
        assert "btn-done" in button_ids
        assert "btn-continue" not in button_ids
        assert "btn-modify" not in button_ids
        assert "btn-stop" not in button_ids


async def test_continue_button_posts_checkpoint_continue_message(
    completed_step: ExecutionStep, next_step: ExecutionStep
) -> None:
    """Test that clicking Continue posts CheckpointContinue message."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield StepCheckpointWidget(completed_step, next_step)

        def on_checkpoint_continue(self, event: CheckpointContinue) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        # Click the Continue button
        await pilot.click("#btn-continue")

        # Verify message was posted
        assert len(messages_received) == 1
        assert isinstance(messages_received[0], CheckpointContinue)


async def test_modify_button_posts_checkpoint_modify_message(
    completed_step: ExecutionStep, next_step: ExecutionStep
) -> None:
    """Test that clicking Modify posts CheckpointModify message."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield StepCheckpointWidget(completed_step, next_step)

        def on_checkpoint_modify(self, event: CheckpointModify) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        # Click the Modify button
        await pilot.click("#btn-modify")

        # Verify message was posted
        assert len(messages_received) == 1
        assert isinstance(messages_received[0], CheckpointModify)


async def test_stop_button_posts_checkpoint_stop_message(
    completed_step: ExecutionStep, next_step: ExecutionStep
) -> None:
    """Test that clicking Stop posts CheckpointStop message."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield StepCheckpointWidget(completed_step, next_step)

        def on_checkpoint_stop(self, event: CheckpointStop) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        # Click the Stop button
        await pilot.click("#btn-stop")

        # Verify message was posted
        assert len(messages_received) == 1
        assert isinstance(messages_received[0], CheckpointStop)


async def test_keyboard_shortcut_c_posts_continue(
    completed_step: ExecutionStep, next_step: ExecutionStep
) -> None:
    """Test that pressing 'c' triggers continue action."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield StepCheckpointWidget(completed_step, next_step)

        def on_checkpoint_continue(self, event: CheckpointContinue) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        # Press 'c' key
        await pilot.press("c")

        # Verify message was posted
        assert len(messages_received) == 1
        assert isinstance(messages_received[0], CheckpointContinue)


async def test_keyboard_shortcut_m_posts_modify(
    completed_step: ExecutionStep, next_step: ExecutionStep
) -> None:
    """Test that pressing 'm' triggers modify action."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield StepCheckpointWidget(completed_step, next_step)

        def on_checkpoint_modify(self, event: CheckpointModify) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        # Press 'm' key
        await pilot.press("m")

        # Verify message was posted
        assert len(messages_received) == 1
        assert isinstance(messages_received[0], CheckpointModify)


async def test_keyboard_shortcut_s_posts_stop(
    completed_step: ExecutionStep, next_step: ExecutionStep
) -> None:
    """Test that pressing 's' triggers stop action."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield StepCheckpointWidget(completed_step, next_step)

        def on_checkpoint_stop(self, event: CheckpointStop) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        # Press 's' key
        await pilot.press("s")

        # Verify message was posted
        assert len(messages_received) == 1
        assert isinstance(messages_received[0], CheckpointStop)


async def test_keyboard_shortcut_escape_posts_stop(
    completed_step: ExecutionStep, next_step: ExecutionStep
) -> None:
    """Test that pressing Escape triggers stop action."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield StepCheckpointWidget(completed_step, next_step)

        def on_checkpoint_stop(self, event: CheckpointStop) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        # Press escape key
        await pilot.press("escape")

        # Verify message was posted
        assert len(messages_received) == 1
        assert isinstance(messages_received[0], CheckpointStop)


async def test_keyboard_c_dismisses_when_plan_complete(
    completed_step: ExecutionStep,
) -> None:
    """Test that 'c' dismisses (posts CheckpointStop) when plan is complete."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield StepCheckpointWidget(completed_step, next_step=None)

        def on_checkpoint_stop(self, event: CheckpointStop) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        # Press 'c' key
        await pilot.press("c")

        # Verify CheckpointStop was posted (dismisses the widget)
        assert len(messages_received) == 1
        assert isinstance(messages_received[0], CheckpointStop)


async def test_done_button_posts_checkpoint_stop_message(
    completed_step: ExecutionStep,
) -> None:
    """Test that clicking Done button posts CheckpointStop message."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield StepCheckpointWidget(completed_step, next_step=None)

        def on_checkpoint_stop(self, event: CheckpointStop) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        # Click the Done button
        await pilot.click("#btn-done")

        # Verify message was posted
        assert len(messages_received) == 1
        assert isinstance(messages_received[0], CheckpointStop)
