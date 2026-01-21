"""Widget to display the status bar with contextual help text."""

from textual.widget import Widget

from shotgun.tui.protocols import QAStateProvider, QuitConfirmationProvider


class StatusBar(Widget):
    """Widget to display the status bar with contextual help text."""

    DEFAULT_CSS = """
        StatusBar {
            text-wrap: wrap;
            padding-left: 1;
        }
    """

    def __init__(self, working: bool = False) -> None:
        """Initialize the status bar.

        Args:
            working: Whether an agent is currently working.
        """
        super().__init__()
        self.working = working

    def render(self) -> str:
        """Render the status bar with contextual help text."""
        # Check if quit confirmation is pending (highest priority)
        if isinstance(self.app, QuitConfirmationProvider) and self.app.quit_pending:
            return "[$foreground-muted][bold $warning]Press Ctrl+C again to quit[/] • [bold $text]esc[/] to cancel[/]"

        # Check if in Q&A mode
        if isinstance(self.screen, QAStateProvider) and self.screen.qa_mode:
            return (
                "[$foreground-muted][bold $text]esc[/] to exit Q&A mode • "
                "[bold $text]enter[/] to send answer • [bold $text]ctrl+j[/] for newline[/]"
            )

        if self.working:
            return (
                "[$foreground-muted][bold $text]esc[/] to stop • "
                "[bold $text]enter[/] to send • [bold $text]ctrl+j[/] newline • "
                "[bold $text]/[/] command palette • "
                "[bold $text]shift+tab[/] toggle mode • "
                "[bold $text]ctrl+c[/] copy • [bold $text]ctrl+v[/] paste[/]"
            )
        else:
            return (
                "[$foreground-muted][bold $text]enter[/] to send • "
                "[bold $text]ctrl+j[/] newline • "
                "[bold $text]/[/] command palette • "
                "[bold $text]shift+tab[/] toggle mode • "
                "[bold $text]ctrl+c[/] copy • [bold $text]ctrl+v[/] paste[/]"
            )
