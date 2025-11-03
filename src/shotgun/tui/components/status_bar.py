"""Widget to display the status bar with contextual help text."""

from typing import TYPE_CHECKING

from textual.widget import Widget

if TYPE_CHECKING:
    from shotgun.tui.screens.chat import ChatScreen


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
        try:
            chat_screen = self.screen
            if isinstance(chat_screen, ChatScreen) and chat_screen.qa_mode:
                return (
                    "[$foreground-muted][bold $text]esc[/] to exit Q&A mode • "
                    "[bold $text]enter[/] to send answer • [bold $text]ctrl+j[/] for newline[/]"
                )
        except Exception:  # noqa: S110
            # If we can't access chat screen, continue with normal display
            pass

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
