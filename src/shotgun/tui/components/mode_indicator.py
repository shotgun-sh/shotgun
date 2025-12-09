"""Widget to display the current agent mode."""

from textual.widget import Widget

from shotgun.agents.models import AgentType
from shotgun.tui.protocols import (
    ActiveSubAgentProvider,
    QAStateProvider,
    RouterModeProvider,
)
from shotgun.tui.utils.mode_progress import PlaceholderHints


class ModeIndicator(Widget):
    """Widget to display the current agent mode.

    For router mode, displays:
    - Idle: "📋 Planning mode" or "✍️ Drafting mode"
    - During execution: "📋 Planning → Research" format

    For legacy agents, displays the agent name and description.
    """

    DEFAULT_CSS = """
        ModeIndicator {
            text-wrap: wrap;
            padding-left: 1;
        }

        ModeIndicator.mode-planning {
            /* Planning mode styling - blue/cyan accent */
        }

        ModeIndicator.mode-drafting {
            /* Drafting mode styling - green accent */
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
        # Check if in Q&A mode first - takes priority
        if isinstance(self.screen, QAStateProvider) and self.screen.qa_mode:
            return (
                "[bold $text-accent]Q&A mode[/]"
                "[$foreground-muted] (Answer the clarifying questions or ESC to cancel)[/]"
            )

        # Router mode display
        if self.mode == AgentType.ROUTER:
            return self._render_router_mode()

        # Legacy agent mode display
        return self._render_legacy_mode()

    def _render_router_mode(self) -> str:
        """Render the router mode indicator.

        Shows:
        - "📋 Planning mode" or "✍️ Drafting mode" when idle
        - "📋 Planning → Research" format when sub-agent is executing
        """
        # Get router mode from screen
        router_mode: str | None = None
        if isinstance(self.screen, RouterModeProvider):
            router_mode = self.screen.router_mode

        # Get active sub-agent from screen
        active_sub_agent: str | None = None
        if isinstance(self.screen, ActiveSubAgentProvider):
            active_sub_agent = self.screen.active_sub_agent

        # Determine mode display
        if router_mode == "drafting":
            icon = "✍️"
            mode_name = "Drafting"
            description = "Auto-execute without confirmation"
            css_class = "mode-drafting"
        else:
            # Default to planning mode
            icon = "📋"
            mode_name = "Planning"
            description = "Review plans before execution"
            css_class = "mode-planning"

        # Update CSS class for styling
        self.set_classes(css_class)

        # Add sub-agent suffix if executing
        if active_sub_agent:
            # Convert sub-agent type to display name
            sub_agent_display = {
                "research": "Research",
                "specify": "Specify",
                "plan": "Plan",
                "tasks": "Tasks",
                "export": "Export",
            }
            sub_agent_name = sub_agent_display.get(
                active_sub_agent, active_sub_agent.title()
            )
            return f"[bold $text-accent]{icon} {mode_name} → {sub_agent_name}[/]"

        return (
            f"[bold $text-accent]{icon} {mode_name} mode[/]"
            f"[$foreground-muted] ({description})[/]"
        )

    def _render_legacy_mode(self) -> str:
        """Render the legacy agent mode indicator.

        Shows the agent name with description and content status.
        """
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

        # Clear any router mode CSS classes
        self.remove_class("mode-planning")
        self.remove_class("mode-drafting")

        return (
            f"[bold $text-accent]{mode_title}{status_icon} mode[/]"
            f"[$foreground-muted] ({description})[/]"
        )
