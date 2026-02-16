"""Unit tests for ChoiceSelectorWidget."""

import pytest

from shotgun.agents.models import ResponseChoice
from shotgun.tui.screens.chat_screen.messages import ChoiceSelected
from shotgun.tui.widgets.choice_selector_widget import ChoiceSelectorWidget

pytestmark = pytest.mark.asyncio


@pytest.fixture
def two_choices() -> list[ResponseChoice]:
    """Create two sample choices."""
    return [
        ResponseChoice(label="Continue with plan", value="continue", is_default=True),
        ResponseChoice(label="Talk about it first", value="Let's discuss."),
    ]


@pytest.fixture
def three_choices() -> list[ResponseChoice]:
    """Create three sample choices."""
    return [
        ResponseChoice(label="Continue", value="continue", is_default=True),
        ResponseChoice(label="Discuss", value="discuss"),
        ResponseChoice(label="Cancel", value="cancel"),
    ]


async def test_choice_selector_stores_choices(
    two_choices: list[ResponseChoice],
) -> None:
    """Test that the widget stores choices."""
    widget = ChoiceSelectorWidget(two_choices)
    assert widget.choices == two_choices
    assert len(widget.choices) == 2


async def test_choice_selector_has_correct_button_count(
    two_choices: list[ResponseChoice],
) -> None:
    """Test that the widget creates one button per choice."""
    from textual.app import App

    class TestApp(App):
        def compose(self):
            yield ChoiceSelectorWidget(two_choices)

    async with TestApp().run_test() as pilot:
        buttons = pilot.app.query("Button")
        assert len(buttons) == 2


async def test_choice_selector_button_labels(
    two_choices: list[ResponseChoice],
) -> None:
    """Test that buttons show numbered labels."""
    from textual.app import App

    class TestApp(App):
        def compose(self):
            yield ChoiceSelectorWidget(two_choices)

    async with TestApp().run_test() as pilot:
        buttons = pilot.app.query("Button")
        # Buttons should have numbered labels
        assert "1: Continue with plan" in str(buttons[0].label)
        assert "2: Talk about it first" in str(buttons[1].label)


async def test_choice_selector_default_button_has_class(
    two_choices: list[ResponseChoice],
) -> None:
    """Test that the default choice has the correct CSS class."""
    from textual.app import App

    class TestApp(App):
        def compose(self):
            yield ChoiceSelectorWidget(two_choices)

    async with TestApp().run_test() as pilot:
        default_btn = pilot.app.query_one("#btn-choice-0")
        secondary_btn = pilot.app.query_one("#btn-choice-1")
        assert "choice-default" in default_btn.classes
        assert "choice-secondary" in secondary_btn.classes


async def test_click_button_posts_choice_selected(
    two_choices: list[ResponseChoice],
) -> None:
    """Test that clicking a button posts ChoiceSelected message."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield ChoiceSelectorWidget(two_choices)

        def on_choice_selected(self, event: ChoiceSelected) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        await pilot.click("#btn-choice-0")
        assert len(messages_received) == 1
        assert messages_received[0].choice.value == "continue"


async def test_click_second_button_posts_correct_choice(
    two_choices: list[ResponseChoice],
) -> None:
    """Test that clicking second button posts the second choice."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield ChoiceSelectorWidget(two_choices)

        def on_choice_selected(self, event: ChoiceSelected) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        await pilot.click("#btn-choice-1")
        assert len(messages_received) == 1
        assert messages_received[0].choice.value == "Let's discuss."


async def test_enter_selects_default_choice(
    two_choices: list[ResponseChoice],
) -> None:
    """Test that pressing Enter selects the default choice."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield ChoiceSelectorWidget(two_choices)

        def on_choice_selected(self, event: ChoiceSelected) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        await pilot.press("enter")
        assert len(messages_received) == 1
        assert messages_received[0].choice.value == "continue"
        assert messages_received[0].choice.is_default is True


async def test_number_key_selects_choice(
    three_choices: list[ResponseChoice],
) -> None:
    """Test that pressing a number key selects the corresponding choice."""
    from textual.app import App

    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield ChoiceSelectorWidget(three_choices)

        def on_choice_selected(self, event: ChoiceSelected) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        await pilot.press("2")
        assert len(messages_received) == 1
        assert messages_received[0].choice.value == "discuss"


async def test_three_buttons_rendered(
    three_choices: list[ResponseChoice],
) -> None:
    """Test that three choices render three buttons."""
    from textual.app import App

    class TestApp(App):
        def compose(self):
            yield ChoiceSelectorWidget(three_choices)

    async with TestApp().run_test() as pilot:
        buttons = pilot.app.query("Button")
        assert len(buttons) == 3
        button_ids = {btn.id for btn in buttons}
        assert "btn-choice-0" in button_ids
        assert "btn-choice-1" in button_ids
        assert "btn-choice-2" in button_ids
