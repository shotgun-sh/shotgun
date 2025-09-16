"""Spinner component for showing loading/working state."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Static


class Spinner(Widget):
    """A spinner widget that shows a rotating animation when working."""

    DEFAULT_CSS = """
    Spinner {
        width: auto;
        height: 1;
    }

    Spinner > Container {
        width: auto;
        height: 1;
        layout: horizontal;
    }

    Spinner .spinner-icon {
        width: 1;
        margin-right: 1;
    }

    Spinner .spinner-text {
        width: auto;
    }
    """

    # Animation frames for the spinner
    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    text = reactive("Working...")
    _frame_index = reactive(0)

    def __init__(
        self,
        text: str = "Working...",
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.text = text
        self._timer: Timer | None = None

    def compose(self) -> ComposeResult:
        """Compose the spinner widget."""
        with Container():
            yield Static("", classes="spinner-icon")
            yield Static(self.text, classes="spinner-text")

    def on_mount(self) -> None:
        """Set up the animation timer when mounted."""
        self._timer = self.set_interval(0.1, self._advance_frame)

    def _advance_frame(self) -> None:
        """Advance to the next animation frame."""
        self._frame_index = (self._frame_index + 1) % len(self.FRAMES)
        self._update_display()

    def _update_display(self) -> None:
        """Update the spinner display."""
        try:
            icon_widget = self.query_one(".spinner-icon", Static)
            icon_widget.update(self.FRAMES[self._frame_index])
        except NoMatches:
            # Widget not mounted yet, ignore
            pass

    def watch_text(self, text: str) -> None:
        """React to changes in the text."""
        try:
            text_widget = self.query_one(".spinner-text", Static)
            text_widget.update(text)
        except NoMatches:
            # Widget not mounted yet, ignore
            return
