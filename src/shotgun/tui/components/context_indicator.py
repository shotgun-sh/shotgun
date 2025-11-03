"""Context window indicator component for showing model usage."""

from textual.reactive import reactive
from textual.widgets import Static

from shotgun.agents.config.models import ModelName, get_model_short_name
from shotgun.agents.context_analyzer.models import ContextAnalysis


class ContextIndicator(Static):
    """Display context window usage and current model name."""

    DEFAULT_CSS = """
    ContextIndicator {
        width: auto;
        height: 1;
        text-align: right;
    }
    """

    context_analysis: reactive[ContextAnalysis | None] = reactive(None)
    model_name: reactive[ModelName | None] = reactive(None)

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)

    def update_context(
        self, analysis: ContextAnalysis | None, model: ModelName | None
    ) -> None:
        """Update the context indicator with new analysis and model data.

        Args:
            analysis: Context analysis with token usage data
            model: Current model name
        """
        self.context_analysis = analysis
        self.model_name = model
        self._refresh_display()

    def _get_percentage_color(self, percentage: float) -> str:
        """Get color for percentage based on threshold.

        Args:
            percentage: Usage percentage (0-100)

        Returns:
            Color name for Textual markup
        """
        if percentage < 60:
            return "#00ff00"  # Green
        elif percentage < 85:
            return "#ffff00"  # Yellow
        else:
            return "#ff0000"  # Red

    def _format_token_count(self, tokens: int) -> str:
        """Format token count for display (e.g., 115000 -> "115K").

        Args:
            tokens: Token count

        Returns:
            Formatted string
        """
        if tokens >= 1_000_000:
            return f"{tokens / 1_000_000:.1f}M"
        elif tokens >= 1_000:
            return f"{tokens / 1_000:.0f}K"
        else:
            return str(tokens)

    def _refresh_display(self) -> None:
        """Refresh the display with current context data."""
        # If no analysis or no actual conversation content, show just model name or empty
        if (
            self.context_analysis is None
            or self.context_analysis.agent_context_tokens == 0
        ):
            if self.model_name:
                model_display = get_model_short_name(self.model_name)
                self.update(f"[bold]{model_display}[/bold]")
            else:
                self.update("")
            return

        analysis = self.context_analysis

        # Calculate percentage
        if analysis.max_usable_tokens > 0:
            percentage = round(
                (analysis.agent_context_tokens / analysis.max_usable_tokens) * 100, 1
            )
        else:
            percentage = 0.0

        # Format token counts
        current_tokens = self._format_token_count(analysis.agent_context_tokens)
        max_tokens = self._format_token_count(analysis.max_usable_tokens)

        # Get color based on percentage
        color = self._get_percentage_color(percentage)

        # Build the display string
        parts = [
            "[$foreground-muted]Context window:[/]",
            f"[{color}]{percentage}% ({current_tokens}/{max_tokens})[/]",
        ]

        # Add model name if available
        if self.model_name:
            model_display = get_model_short_name(self.model_name)
            parts.extend(
                [
                    "[$foreground-muted]|[/]",
                    f"[bold]{model_display}[/bold]",
                ]
            )

        self.update(" ".join(parts))

    def watch_context_analysis(self, analysis: ContextAnalysis | None) -> None:
        """React to context analysis changes."""
        self._refresh_display()

    def watch_model_name(self, model: ModelName | None) -> None:
        """React to model name changes."""
        self._refresh_display()
