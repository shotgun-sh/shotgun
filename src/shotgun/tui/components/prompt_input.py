from textual import events
from textual.message import Message
from textual.widgets import TextArea


class PromptInput(TextArea):
    """A TextArea with a submit binding."""

    DEFAULT_CSS = """
        PromptInput {
            outline: round $primary;
            background: transparent;
        }
    """

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool:
        if action != "copy":
            return True
        # run copy action if there is selected text
        # otherwise, do nothing, so global ctrl+c still works.
        return bool(self.selected_text)

    class Submitted(Message):
        """A message to indicate that the text has been submitted."""

        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    def action_submit(self) -> None:
        """An action to submit the text."""
        self.post_message(self.Submitted(self.text))

    async def _on_key(self, event: events.Key) -> None:
        """Handle key presses which correspond to document inserts."""

        # Don't handle Enter key here - let the binding handle it
        if event.key == "enter":
            self.action_submit()

        self._restart_blink()

        if self.read_only:
            return

        key = event.key
        insert_values = {
            "ctrl+j": "\n",
        }
        if self.tab_behavior == "indent":
            if key == "escape":
                event.stop()
                event.prevent_default()
                self.screen.focus_next()
                return
            if self.indent_type == "tabs":
                insert_values["tab"] = "\t"
            else:
                insert_values["tab"] = " " * self._find_columns_to_next_tab_stop()

        if event.is_printable or key in insert_values:
            event.stop()
            event.prevent_default()
            insert = insert_values.get(key, event.character)
            # `insert` is not None because event.character cannot be
            # None because we've checked that it's printable.
            assert insert is not None  # noqa: S101
            start, end = self.selection
            self._replace_via_keyboard(insert, start, end)
