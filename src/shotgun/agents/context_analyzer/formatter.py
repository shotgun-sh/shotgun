"""Format context analysis for various output types."""

from typing import Any

from .models import ContextAnalysis


class ContextFormatter:
    """Formats context analysis for various output types."""

    @staticmethod
    def format_markdown(analysis: ContextAnalysis) -> str:
        """Format the analysis as markdown for display.

        Args:
            analysis: Context analysis to format

        Returns:
            Markdown-formatted string
        """
        lines = ["# Conversation Context Analysis", ""]

        # Top-level summary with model and usage info
        usage_percent = (
            (analysis.agent_context_tokens / analysis.max_usable_tokens * 100)
            if analysis.max_usable_tokens > 0
            else 0
        )
        free_percent = (
            (analysis.free_space_tokens / analysis.max_usable_tokens * 100)
            if analysis.max_usable_tokens > 0
            else 0
        )

        lines.extend(
            [
                f"Model: {analysis.model_name}",
                "",
                f"Total Context: {analysis.agent_context_tokens:,} / {analysis.max_usable_tokens:,} tokens ({usage_percent:.1f}%)",
                "",
                f"Free Space: {analysis.free_space_tokens:,} tokens ({free_percent:.1f}%)",
                "",
                "Autocompact Buffer: 500 tokens",
                "",
            ]
        )

        # Create 25-character visual bar showing proportional usage
        # Each character represents 4% of total context
        filled_chars = int(usage_percent / 4)
        empty_chars = 25 - filled_chars
        visual_bar = "●" * filled_chars + "○" * empty_chars

        lines.extend(
            [
                "## Context Composition",
                visual_bar,
                "",
            ]
        )

        # Add agent context categories only (hints are not part of agent context)
        agent_categories = [
            ("🧑 User Messages", analysis.user_messages),
            ("🤖 Agent Responses", analysis.agent_responses),
            ("📋 System Prompts", analysis.system_prompts),
            ("📊 System Status", analysis.system_status),
            ("🔍 Codebase Understanding", analysis.codebase_understanding),
            ("📦 Artifact Management", analysis.artifact_management),
            ("🌐 Web Research", analysis.web_research),
        ]

        # Only add unknown if it has content
        if analysis.unknown.count > 0:
            agent_categories.append(("⚠️  Unknown Tools", analysis.unknown))

        for label, stats in agent_categories:
            if stats.count > 0:
                percentage = analysis.get_percentage(stats)
                # Align labels to 30 characters for clean visual layout
                lines.append(
                    f"{label:<30} {percentage:>5.1f}%  ({stats.count} messages, ~{stats.tokens:,} tokens)"
                )
                # Add blank line to prevent Textual's Markdown widget from reflowing
                lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_json(analysis: ContextAnalysis) -> dict[str, Any]:
        """Format the analysis as a JSON-serializable dictionary.

        Args:
            analysis: Context analysis to format

        Returns:
            Dictionary with context analysis data
        """
        # Use Pydantic's model_dump() to serialize the model
        data = analysis.model_dump()

        # Add computed summary field
        data["summary"] = {
            "total_messages": analysis.total_messages - analysis.hint_messages.count,
            "agent_context_tokens": analysis.agent_context_tokens,
            "context_window": analysis.context_window,
            "usage_percentage": round(
                (analysis.agent_context_tokens / analysis.context_window * 100)
                if analysis.context_window > 0
                else 0,
                1,
            ),
        }

        return data
