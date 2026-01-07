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

    class OpenCommandPalette(Message):
        """Request to open the command palette."""

    def action_submit(self) -> None:
        """An action to submit the text."""
        self.post_message(self.Submitted(self.text))

    def on_key(self, event: events.Key) -> None:
        """Handle key presses for special actions."""
        # Submit on Enter
        if event.key == "enter":
            event.stop()
            event.prevent_default()
            self.action_submit()
            return

        # Detect "/" as first character to trigger command palette
        if event.character == "/" and not self.text.strip():
            event.stop()
            event.prevent_default()
            self.post_message(self.OpenCommandPalette())
            return

        # Handle ctrl+j for newline (since enter is for submit)
        if event.key == "ctrl+j":
            event.stop()
            event.prevent_default()
            start, end = self.selection
            self.replace(
                "\n",
                start,
                end,
                maintain_selection_offset=False,
            )
            return
