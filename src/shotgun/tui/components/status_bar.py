"""Widget to display the status bar with contextual help text."""

from textual.widget import Widget

from shotgun.tui.protocols import QAStateProvider


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
        # Check if in Q&A mode first (highest priority)
        if isinstance(self.screen, QAStateProvider) and self.screen.qa_mode:
            return (
                "[$foreground-muted][bold $text]esc[/] to exit Q&A mode • "
                "[bold $text]enter[/] to send answer • [bold $text]ctrl+j[/] for newline[/]"
            )

        if self.working:
            return (
                "[$foreground-muted][bold $text]esc[/] to stop • "
                "[bold $text]enter[/] to send • [bold $text]ctrl+j[/] for newline • "
                "[bold $text]ctrl+p[/] command palette • [bold $text]shift+tab[/] cycle modes • "
                "/help for commands[/]"
            )
        else:
            return (
                "[$foreground-muted][bold $text]enter[/] to send • "
                "[bold $text]ctrl+j[/] for newline • [bold $text]ctrl+p[/] command palette • "
                "[bold $text]shift+tab[/] cycle modes • /help for commands[/]"
            )
