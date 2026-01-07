"""Unit tests for PromptInput component."""

import pytest
from textual.app import App

from shotgun.tui.components.prompt_input import PromptInput

pytestmark = pytest.mark.asyncio


async def test_slash_in_empty_input_posts_open_command_palette() -> None:
    """Test that '/' in empty input triggers OpenCommandPalette message."""
    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield PromptInput()

        def on_prompt_input_open_command_palette(
            self, event: PromptInput.OpenCommandPalette
        ) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        # Focus the prompt input
        prompt_input = pilot.app.query_one(PromptInput)
        prompt_input.focus()

        # Press '/' key in empty input
        await pilot.press("/")

        # Verify message was posted
        assert len(messages_received) == 1
        assert isinstance(messages_received[0], PromptInput.OpenCommandPalette)

        # Verify '/' was not inserted into the text
        assert prompt_input.text == ""


async def test_slash_in_non_empty_input_is_inserted_normally() -> None:
    """Test that '/' is inserted normally when input already has text."""
    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield PromptInput()

        def on_prompt_input_open_command_palette(
            self, event: PromptInput.OpenCommandPalette
        ) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        # Focus the prompt input
        prompt_input = pilot.app.query_one(PromptInput)
        prompt_input.focus()

        # Type some text first
        await pilot.press("h", "e", "l", "l", "o")

        # Press '/' key
        await pilot.press("/")

        # Verify no OpenCommandPalette message was posted
        assert len(messages_received) == 0

        # Verify '/' was inserted into the text
        assert prompt_input.text == "hello/"


async def test_slash_in_whitespace_only_input_posts_open_command_palette() -> None:
    """Test that '/' triggers command palette when input has only whitespace."""
    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield PromptInput()

        def on_prompt_input_open_command_palette(
            self, event: PromptInput.OpenCommandPalette
        ) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        # Focus the prompt input
        prompt_input = pilot.app.query_one(PromptInput)
        prompt_input.focus()

        # Add whitespace
        await pilot.press("space", "space")

        # Press '/' key
        await pilot.press("/")

        # Verify message was posted (whitespace-only is treated as empty)
        assert len(messages_received) == 1
        assert isinstance(messages_received[0], PromptInput.OpenCommandPalette)


async def test_prompt_input_submit_message() -> None:
    """Test that Enter key posts Submitted message."""
    messages_received: list = []

    class TestApp(App):
        def compose(self):
            yield PromptInput()

        def on_prompt_input_submitted(self, event: PromptInput.Submitted) -> None:
            messages_received.append(event)

    async with TestApp().run_test() as pilot:
        # Focus the prompt input
        prompt_input = pilot.app.query_one(PromptInput)
        prompt_input.focus()

        # Type some text
        await pilot.press("t", "e", "s", "t")

        # Press Enter
        await pilot.press("enter")

        # Verify Submitted message was posted
        assert len(messages_received) == 1
        assert isinstance(messages_received[0], PromptInput.Submitted)
        assert messages_received[0].text == "test"
