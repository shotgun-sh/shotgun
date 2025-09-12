from textual.containers import VerticalScroll
from textual.reactive import reactive


class VerticalTail(VerticalScroll):
    """A vertical scroll container that automatically scrolls to the bottom when content is added."""

    auto_scroll = reactive(True, layout=False)

    def on_mount(self) -> None:
        """Set up auto-scrolling when the widget is mounted."""
        # Start at the bottom
        if self.auto_scroll:
            self.scroll_end(animate=False)

    def on_descendant_mount(self) -> None:
        """Auto-scroll when a new child is added."""
        if self.auto_scroll:
            # Check if we're near the bottom (within 1 line of scroll)
            at_bottom = self.scroll_y >= self.max_scroll_y - 1
            if at_bottom:
                # Use call_after_refresh to ensure layout is updated first
                self.call_after_refresh(self.scroll_end, animate=False)

    def watch_auto_scroll(self, value: bool) -> None:
        """Handle auto_scroll property changes."""
        if value:
            self.scroll_end(animate=False)
