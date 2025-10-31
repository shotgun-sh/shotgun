"""Agent response widget for chat history."""

from pydantic_ai.messages import (
    BuiltinToolCallPart,
    BuiltinToolReturnPart,
    ModelResponse,
    TextPart,
    ThinkingPart,
    ToolCallPart,
)
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Markdown

from .formatters import ToolFormatter


class AgentResponseWidget(Widget):
    """Widget that displays agent responses in the chat history."""

    def __init__(
        self,
        item: ModelResponse | None,
        sub_agent_contexts: dict[int, dict[str, str]] | None = None,
    ) -> None:
        """Initialize agent response widget.

        Args:
            item: The model response to display
            sub_agent_contexts: Dict mapping part indices to sub-agent context
        """
        super().__init__()
        self.item = item
        self.sub_agent_contexts = sub_agent_contexts or {}

    def compose(self) -> ComposeResult:
        self.display = self.item is not None
        if self.item is None:
            yield Markdown(markdown="")
        else:
            yield Markdown(markdown=self.compute_output())

    def compute_output(self) -> str:
        """Compute the markdown output for the agent response."""
        acc = ""
        if self.item is None:
            return ""

        # Track which sub-agent execution we're currently in
        current_sub_agent_id: str | None = None
        sub_agent_parts: list[tuple[int, ToolCallPart]] = []

        for idx, part in enumerate(self.item.parts):
            # Check if this part belongs to a sub-agent
            sub_agent_ctx = self.sub_agent_contexts.get(idx)

            if isinstance(part, TextPart):
                # If we have accumulated sub-agent parts, flush them first
                if sub_agent_parts and current_sub_agent_id:
                    acc += self._format_sub_agent_section(
                        current_sub_agent_id, sub_agent_parts
                    )
                    sub_agent_parts = []
                    current_sub_agent_id = None

                # Only show the circle prefix if there's actual content
                if part.content and part.content.strip():
                    acc += f"**⏺** {part.content}\n\n"

            elif isinstance(part, ToolCallPart):
                if sub_agent_ctx:
                    # This is a sub-agent tool call
                    execution_id = sub_agent_ctx["execution_id"]

                    # Check if this is a new sub-agent execution
                    if current_sub_agent_id != execution_id:
                        # Flush previous sub-agent parts if any
                        if sub_agent_parts and current_sub_agent_id:
                            acc += self._format_sub_agent_section(
                                current_sub_agent_id, sub_agent_parts
                            )
                            sub_agent_parts = []

                        current_sub_agent_id = execution_id

                    # Add to sub-agent parts list
                    sub_agent_parts.append((idx, part))
                else:
                    # Regular tool call (not from sub-agent)
                    # Flush sub-agent parts first if any
                    if sub_agent_parts and current_sub_agent_id:
                        acc += self._format_sub_agent_section(
                            current_sub_agent_id, sub_agent_parts
                        )
                        sub_agent_parts = []
                        current_sub_agent_id = None

                    parts_str = ToolFormatter.format_tool_call_part(part)
                    if parts_str:  # Only add if there's actual content
                        acc += parts_str + "\n\n"

            elif isinstance(part, BuiltinToolCallPart):
                # Flush sub-agent parts first if any
                if sub_agent_parts and current_sub_agent_id:
                    acc += self._format_sub_agent_section(
                        current_sub_agent_id, sub_agent_parts
                    )
                    sub_agent_parts = []
                    current_sub_agent_id = None

                # Format builtin tool calls using registry
                formatted = ToolFormatter.format_builtin_tool_call(part)
                if formatted:  # Only add if not hidden
                    acc += formatted + "\n\n"

            elif isinstance(part, BuiltinToolReturnPart):
                # Don't show tool return parts in the UI
                pass

            elif isinstance(part, ThinkingPart):
                # Flush sub-agent parts first if any
                if sub_agent_parts and current_sub_agent_id:
                    acc += self._format_sub_agent_section(
                        current_sub_agent_id, sub_agent_parts
                    )
                    sub_agent_parts = []
                    current_sub_agent_id = None

                if (
                    idx == len(self.item.parts) - 1
                ):  # show the thinking part only if it's the last part
                    acc += (
                        f"thinking: {part.content}\n\n"
                        if part.content
                        else "Thinking..."
                    )
                else:
                    continue

        # Flush any remaining sub-agent parts
        if sub_agent_parts and current_sub_agent_id:
            acc += self._format_sub_agent_section(current_sub_agent_id, sub_agent_parts)

        return acc.strip()

    def _format_sub_agent_section(
        self, execution_id: str, parts: list[tuple[int, ToolCallPart]]
    ) -> str:
        """Format a section of sub-agent tool calls.

        Args:
            execution_id: The sub-agent execution ID
            parts: List of (index, ToolCallPart) tuples

        Returns:
            Formatted markdown string
        """
        if not parts:
            return ""

        # Get agent name from first part's context
        first_idx = parts[0][0]
        agent_name = self.sub_agent_contexts[first_idx]["agent_name"]

        # Build the section
        section = f"**🔧 Sub-Agent: {agent_name}**\n\n"

        # Format each tool call with indentation
        for _, part in parts:
            formatted = ToolFormatter.format_tool_call_part(part)
            if formatted:
                # Indent each line by 2 spaces for visual hierarchy
                indented = "\n".join(f"  {line}" for line in formatted.split("\n"))
                section += indented + "\n\n"

        return section
