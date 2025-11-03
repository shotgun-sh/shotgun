"""Pydantic models for context analysis."""

from typing import Any

from pydantic import BaseModel, Field


class TokenAllocation(BaseModel):
    """Token counts allocated from API usage data by message/tool type.

    Used internally by ContextAnalyzer to track token distribution across
    different message types and tool categories.
    """

    user: int = Field(ge=0, default=0, description="Tokens from user prompts")
    agent_responses: int = Field(
        ge=0, default=0, description="Tokens from agent text responses"
    )
    system_prompts: int = Field(
        ge=0, default=0, description="Tokens from system prompts"
    )
    system_status: int = Field(
        ge=0, default=0, description="Tokens from system status messages"
    )
    codebase_understanding: int = Field(
        ge=0, default=0, description="Tokens from codebase understanding tools"
    )
    artifact_management: int = Field(
        ge=0, default=0, description="Tokens from artifact management tools"
    )
    web_research: int = Field(
        ge=0, default=0, description="Tokens from web research tools"
    )
    unknown: int = Field(ge=0, default=0, description="Tokens from uncategorized tools")


class MessageTypeStats(BaseModel):
    """Statistics for a specific message type."""

    count: int = Field(ge=0, description="Number of messages of this type")
    tokens: int = Field(ge=0, description="Total tokens consumed by this type")

    @property
    def avg_tokens(self) -> float:
        """Calculate average tokens per message."""
        return self.tokens / self.count if self.count > 0 else 0.0


class ContextAnalysis(BaseModel):
    """Complete analysis of conversation context composition."""

    user_messages: MessageTypeStats
    agent_responses: MessageTypeStats
    system_prompts: MessageTypeStats
    system_status: MessageTypeStats
    codebase_understanding: MessageTypeStats
    artifact_management: MessageTypeStats
    web_research: MessageTypeStats
    unknown: MessageTypeStats
    hint_messages: MessageTypeStats
    total_tokens: int = Field(ge=0, description="Total tokens including hints")
    total_messages: int = Field(ge=0, description="Total message count including hints")
    context_window: int = Field(ge=0, description="Model's maximum input tokens")
    agent_context_tokens: int = Field(
        ge=0,
        description="Tokens that actually consume agent context (excluding UI-only)",
    )
    model_name: str = Field(description="Name of the model being used")
    max_usable_tokens: int = Field(
        ge=0, description="80% of max_input_tokens (usable limit)"
    )
    free_space_tokens: int = Field(
        description="Remaining tokens available (negative if over capacity)"
    )

    def get_percentage(self, stats: MessageTypeStats) -> float:
        """Calculate percentage of agent context tokens for a message type.

        Args:
            stats: Message type statistics to calculate percentage for

        Returns:
            Percentage of total agent context tokens (0-100)
        """
        return (
            (stats.tokens / self.agent_context_tokens * 100)
            if self.agent_context_tokens > 0
            else 0.0
        )


class ContextCompositionTelemetry(BaseModel):
    """Telemetry data for context composition tracking to PostHog."""

    # Context usage
    total_messages: int = Field(ge=0)
    agent_context_tokens: int = Field(ge=0)
    context_window: int = Field(ge=0)
    max_usable_tokens: int = Field(ge=0)
    free_space_tokens: int = Field(ge=0)
    usage_percentage: float = Field(ge=0, le=100)

    # Message type counts
    user_messages_count: int = Field(ge=0)
    agent_responses_count: int = Field(ge=0)
    system_prompts_count: int = Field(ge=0)
    system_status_count: int = Field(ge=0)
    codebase_understanding_count: int = Field(ge=0)
    artifact_management_count: int = Field(ge=0)
    web_research_count: int = Field(ge=0)
    unknown_tools_count: int = Field(ge=0)

    # Token distribution percentages
    user_messages_pct: float = Field(ge=0, le=100)
    agent_responses_pct: float = Field(ge=0, le=100)
    system_prompts_pct: float = Field(ge=0, le=100)
    system_status_pct: float = Field(ge=0, le=100)
    codebase_understanding_pct: float = Field(ge=0, le=100)
    artifact_management_pct: float = Field(ge=0, le=100)
    web_research_pct: float = Field(ge=0, le=100)
    unknown_tools_pct: float = Field(ge=0, le=100)

    # Compaction info
    compaction_occurred: bool
    messages_before_compaction: int | None = None
    messages_after_compaction: int | None = None
    compaction_reduction_pct: float | None = None

    @classmethod
    def from_analysis(
        cls,
        analysis: "ContextAnalysis",
        compaction_occurred: bool = False,
        messages_before_compaction: int | None = None,
    ) -> "ContextCompositionTelemetry":
        """Create telemetry from context analysis.

        Args:
            analysis: The context analysis to convert
            compaction_occurred: Whether message compaction occurred
            messages_before_compaction: Number of messages before compaction

        Returns:
            ContextCompositionTelemetry instance
        """
        total_messages = analysis.total_messages - analysis.hint_messages.count
        usage_pct = (
            round((analysis.agent_context_tokens / analysis.max_usable_tokens * 100), 1)
            if analysis.max_usable_tokens > 0
            else 0
        )

        # Calculate compaction metrics
        messages_after: int | None = None
        compaction_reduction_pct: float | None = None

        if compaction_occurred and messages_before_compaction is not None:
            messages_after = total_messages
            if messages_before_compaction > 0:
                compaction_reduction_pct = round(
                    (1 - (total_messages / messages_before_compaction)) * 100, 1
                )

        return cls(
            # Context usage
            total_messages=total_messages,
            agent_context_tokens=analysis.agent_context_tokens,
            context_window=analysis.context_window,
            max_usable_tokens=analysis.max_usable_tokens,
            free_space_tokens=analysis.free_space_tokens,
            usage_percentage=usage_pct,
            # Message type counts
            user_messages_count=analysis.user_messages.count,
            agent_responses_count=analysis.agent_responses.count,
            system_prompts_count=analysis.system_prompts.count,
            system_status_count=analysis.system_status.count,
            codebase_understanding_count=analysis.codebase_understanding.count,
            artifact_management_count=analysis.artifact_management.count,
            web_research_count=analysis.web_research.count,
            unknown_tools_count=analysis.unknown.count,
            # Token distribution percentages
            user_messages_pct=round(analysis.get_percentage(analysis.user_messages), 1),
            agent_responses_pct=round(
                analysis.get_percentage(analysis.agent_responses), 1
            ),
            system_prompts_pct=round(
                analysis.get_percentage(analysis.system_prompts), 1
            ),
            system_status_pct=round(analysis.get_percentage(analysis.system_status), 1),
            codebase_understanding_pct=round(
                analysis.get_percentage(analysis.codebase_understanding), 1
            ),
            artifact_management_pct=round(
                analysis.get_percentage(analysis.artifact_management), 1
            ),
            web_research_pct=round(analysis.get_percentage(analysis.web_research), 1),
            unknown_tools_pct=round(analysis.get_percentage(analysis.unknown), 1),
            # Compaction info
            compaction_occurred=compaction_occurred,
            messages_before_compaction=messages_before_compaction,
            messages_after_compaction=messages_after,
            compaction_reduction_pct=compaction_reduction_pct,
        )


class ContextAnalysisOutput(BaseModel):
    """Output format for context analysis with multiple representations."""

    markdown: str = Field(description="Markdown-formatted analysis for display")
    json_data: dict[str, Any] = Field(
        description="JSON representation of analysis data"
    )
