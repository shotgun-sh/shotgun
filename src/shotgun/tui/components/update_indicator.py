"""Update indicator component for showing when a new version is available."""

from textual.reactive import reactive
from textual.widgets import Static

from shotgun.utils.update_checker import UpdateInfo


class UpdateIndicator(Static):
    """Display update available notification in footer."""

    DEFAULT_CSS = """
    UpdateIndicator {
        width: auto;
        height: 1;
        text-align: right;
    }
    """

    update_info: reactive[UpdateInfo | None] = reactive(None)

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        # Start hidden - will be shown when update is available
        self.display = False

    def set_update_info(self, info: UpdateInfo | None) -> None:
        """Update the indicator with version check results.

        Args:
            info: UpdateInfo with version details, or None to hide.
        """
        self.update_info = info
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Refresh the display with current update info."""
        if self.update_info is None or not self.update_info.update_available:
            self.display = False
            self.update("")
            return

        # Show the update indicator with attention-grabbing styling
        self.display = True
        info = self.update_info
        self.update(
            f"[bold #ffcc00]⬆ UPDATE AVAILABLE:[/] "
            f"[bold #00ff00]v{info.latest_version}[/] "
            f"[#ffcc00](you have v{info.current_version})[/]"
        )

    def watch_update_info(self, info: UpdateInfo | None) -> None:
        """React to update info changes."""
        self._refresh_display()
