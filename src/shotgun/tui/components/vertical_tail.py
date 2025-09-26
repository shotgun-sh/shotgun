from textual.containers import VerticalScroll
from textual.reactive import reactive


class VerticalTail(VerticalScroll):
    """A vertical scroll container that automatically scrolls to the bottom when content is added."""

    auto_scroll = reactive(True, layout=False)

    def watch_auto_scroll(self, value: bool) -> None:
        """Handle auto_scroll property changes."""
        if value:
            self.scroll_end(animate=False)
