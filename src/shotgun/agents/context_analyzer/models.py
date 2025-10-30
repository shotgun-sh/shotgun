"""Pydantic models for context analysis."""

from typing import Any

from pydantic import BaseModel, Field


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
        ge=0, description="Tokens that actually consume agent context (excluding UI-only)"
    )
    model_name: str = Field(description="Name of the model being used")
    max_usable_tokens: int = Field(ge=0, description="80% of max_input_tokens (usable limit)")
    free_space_tokens: int = Field(ge=0, description="Remaining tokens available")

    def get_percentage(self, stats: MessageTypeStats) -> float:
        """Calculate percentage of agent context tokens for a message type.

        Args:
            stats: Message type statistics to calculate percentage for

        Returns:
            Percentage of total agent context tokens (0-100)
        """
        return (stats.tokens / self.agent_context_tokens * 100) if self.agent_context_tokens > 0 else 0.0


class ContextAnalysisOutput(BaseModel):
    """Output format for context analysis with multiple representations."""

    markdown: str = Field(description="Markdown-formatted analysis for display")
    json_data: dict[str, Any] = Field(description="JSON representation of analysis data")
