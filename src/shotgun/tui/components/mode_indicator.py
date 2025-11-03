"""Widget to display the current agent mode."""

from typing import TYPE_CHECKING

from textual.widget import Widget

from shotgun.agents.models import AgentType
from shotgun.tui.utils.mode_progress import PlaceholderHints

if TYPE_CHECKING:
    from shotgun.tui.screens.chat import ChatScreen


class ModeIndicator(Widget):
    """Widget to display the current agent mode."""

    DEFAULT_CSS = """
        ModeIndicator {
            text-wrap: wrap;
            padding-left: 1;
        }
    """

    def __init__(self, mode: AgentType) -> None:
        """Initialize the mode indicator.

        Args:
            mode: The current agent type/mode.
        """
        super().__init__()
        self.mode = mode
        self.progress_checker = PlaceholderHints().progress_checker

    def render(self) -> str:
        """Render the mode indicator."""
        # Check if in Q&A mode first
        try:
            chat_screen = self.screen
            if isinstance(chat_screen, ChatScreen) and chat_screen.qa_mode:
                return (
                    "[bold $text-accent]Q&A mode[/]"
                    "[$foreground-muted] (Answer the clarifying questions or ESC to cancel)[/]"
                )
        except Exception:  # noqa: S110
            # If we can't access chat screen, continue with normal display
            pass

        mode_display = {
            AgentType.RESEARCH: "Research",
            AgentType.PLAN: "Planning",
            AgentType.TASKS: "Tasks",
            AgentType.SPECIFY: "Specify",
            AgentType.EXPORT: "Export",
        }
        mode_description = {
            AgentType.RESEARCH: (
                "Research topics with web search and synthesize findings"
            ),
            AgentType.PLAN: "Create comprehensive, actionable plans with milestones",
            AgentType.TASKS: (
                "Generate specific, actionable tasks from research and plans"
            ),
            AgentType.SPECIFY: (
                "Create detailed specifications and requirements documents"
            ),
            AgentType.EXPORT: "Export artifacts and findings to various formats",
        }

        mode_title = mode_display.get(self.mode, self.mode.value.title())
        description = mode_description.get(self.mode, "")

        # Check if mode has content
        has_content = self.progress_checker.has_mode_content(self.mode)
        status_icon = " ✓" if has_content else ""

        return (
            f"[bold $text-accent]{mode_title}{status_icon} mode[/]"
            f"[$foreground-muted] ({description})[/]"
        )
