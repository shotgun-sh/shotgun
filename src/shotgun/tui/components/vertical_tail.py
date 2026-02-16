from typing import Any

from textual.containers import VerticalScroll
from textual.geometry import Size
from textual.reactive import reactive


class VerticalTail(VerticalScroll):
    """A vertical scroll container that automatically scrolls to the bottom when content is added."""

    auto_scroll = reactive(True, layout=False)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._scroll_pending = False

    def watch_auto_scroll(self, value: bool) -> None:
        """Handle auto_scroll property changes."""
        if value:
            self.scroll_end(animate=False)

    def watch_virtual_size(self, value: Size) -> None:
        """Handle virtual_size property changes."""
        if not self.auto_scroll or self._scroll_pending:
            return
        self._scroll_pending = True
        self.call_later(self._deferred_scroll_end)

    def _deferred_scroll_end(self) -> None:
        self._scroll_pending = False
        self.scroll_end(animate=False)
