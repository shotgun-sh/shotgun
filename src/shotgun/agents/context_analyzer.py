"""Analyze conversation context composition and display statistics."""

import asyncio
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

import sentry_sdk
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from shotgun.agents.config.models import ModelConfig
from shotgun.agents.history.token_counting.utils import count_tokens_from_messages
from shotgun.agents.messages import AgentSystemPrompt, SystemStatusPrompt
from shotgun.logging_config import get_logger
from shotgun.tui.screens.chat_screen.hint_message import HintMessage

logger = get_logger(__name__)

# Tool category registry - maps tool names to their semantic category
TOOL_CATEGORIES = {
    # Codebase understanding tools
    "query_graph": "codebase_understanding",
    "retrieve_code": "codebase_understanding",
    "file_read": "codebase_understanding",
    "directory_lister": "codebase_understanding",
    "codebase_shell": "codebase_understanding",
    # Artifact management tools
    "write_file": "artifact_management",
    "append_file": "artifact_management",
    "read_file": "artifact_management",
    # Web research tools
    "openai_web_search_tool": "web_research",
    "anthropic_web_search_tool": "web_research",
    "gemini_web_search_tool": "web_research",
    # Special: final_result is treated as agent response, not a tool
    "final_result": "agent_response",
}


def _get_tool_category(tool_name: str) -> str:
    """Get category for a tool, logging unknown tools to Sentry.

    Args:
        tool_name: Name of the tool

    Returns:
        Category name or "unknown"
    """
    category = TOOL_CATEGORIES.get(tool_name)

    if category is None:
        logger.warning(f"Unknown tool encountered in context analysis: {tool_name}")
        sentry_sdk.capture_message(
            f"Unknown tool in context analysis: {tool_name}",
            level="warning",
            extras={"tool_name": tool_name},
        )
        return "unknown"

    return category


@dataclass
class MessageTypeStats:
    """Statistics for a specific message type."""

    count: int
    tokens: int

    @property
    def avg_tokens(self) -> float:
        """Calculate average tokens per message."""
        return self.tokens / self.count if self.count > 0 else 0.0


@dataclass
class ContextAnalysis:
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
    total_tokens: int
    total_messages: int
    context_window: int
    agent_context_tokens: int  # Tokens that actually consume agent context (excluding UI-only)
    model_name: str  # Name of the model being used
    max_usable_tokens: int  # 80% of max_input_tokens (usable limit)
    free_space_tokens: int  # Remaining tokens available

    def get_percentage(self, stats: MessageTypeStats) -> float:
        """Calculate percentage of agent context tokens for a message type."""
        return (stats.tokens / self.agent_context_tokens * 100) if self.agent_context_tokens > 0 else 0.0

    def format_analysis(self) -> str:
        """Format the analysis as markdown for display."""
        lines = ["# Conversation Context Analysis", ""]

        # Top-level summary with model and usage info
        usage_percent = (
            (self.agent_context_tokens / self.max_usable_tokens * 100) if self.max_usable_tokens > 0 else 0
        )
        free_percent = (
            (self.free_space_tokens / self.max_usable_tokens * 100) if self.max_usable_tokens > 0 else 0
        )

        lines.extend([
            f"Model: {self.model_name}",
            "",
            f"Total Context: {self.agent_context_tokens:,} / {self.max_usable_tokens:,} tokens ({usage_percent:.1f}%)",
            "",
            f"Free Space: {self.free_space_tokens:,} tokens ({free_percent:.1f}%)",
            "",
            f"Autocompact Buffer: 500 tokens",
            "",
        ])

        # Create 25-character visual bar showing proportional usage
        # Each character represents 4% of total context
        filled_chars = int(usage_percent / 4)
        empty_chars = 25 - filled_chars
        visual_bar = "●" * filled_chars + "○" * empty_chars

        lines.extend([
            "## Context Composition",
            visual_bar,
            "",
        ])

        # Add agent context categories only (hints are not part of agent context)
        agent_categories = [
            ("🧑 User Messages", self.user_messages),
            ("🤖 Agent Responses", self.agent_responses),
            ("📋 System Prompts", self.system_prompts),
            ("📊 System Status", self.system_status),
            ("🔍 Codebase Understanding", self.codebase_understanding),
            ("📦 Artifact Management", self.artifact_management),
            ("🌐 Web Research", self.web_research),
        ]

        # Only add unknown if it has content
        if self.unknown.count > 0:
            agent_categories.append(("⚠️  Unknown Tools", self.unknown))

        for label, stats in agent_categories:
            if stats.count > 0:
                percentage = self.get_percentage(stats)
                # Align labels to 30 characters for clean visual layout
                lines.append(
                    f"{label:<30} {percentage:>5.1f}%  ({stats.count} messages, ~{stats.tokens:,} tokens)"
                )
                # Add blank line to prevent Textual's Markdown widget from reflowing
                lines.append("")

        return "\n".join(lines)


class ContextAnalyzer:
    """Analyzes conversation message history for context composition."""

    def __init__(self, model_config: ModelConfig):
        """Initialize the analyzer with model configuration for token counting.

        Args:
            model_config: Model configuration for accurate token counting
        """
        self.model_config = model_config

    def _allocate_tokens_from_usage(
        self,
        message_history: list[ModelMessage],
    ) -> dict[str, int]:
        """Allocate tokens from actual API usage data proportionally to parts.

        This uses the ground truth token counts from ModelResponse.usage instead of
        creating synthetic messages, which avoids inflating counts with message framing overhead.

        IMPORTANT: usage.input_tokens is cumulative (includes all conversation history), so we:
        1. Use the LAST response's input_tokens as the ground truth total
        2. Calculate proportions based on content size across ALL requests
        3. Allocate the ground truth total proportionally

        Args:
            message_history: List of actual messages from conversation

        Returns:
            Dict with token counts by part type:
            'user', 'assistant', 'system_prompts', 'system_status',
            'tool_calls', 'tool_results'
        """
        # Step 1: Find the last response's usage data (ground truth for input tokens)
        last_input_tokens = 0
        total_output_tokens = 0

        for msg in reversed(message_history):
            if isinstance(msg, ModelResponse) and msg.usage:
                last_input_tokens = msg.usage.input_tokens + msg.usage.cache_read_tokens
                break

        # Step 2: Calculate total output tokens (sum across all responses)
        for msg in message_history:
            if isinstance(msg, ModelResponse) and msg.usage:
                total_output_tokens += msg.usage.output_tokens

        # Step 3: Calculate content size proportions for each part type across ALL requests
        part_type_sizes: dict[str, int] = defaultdict(int)

        for msg in message_history:
            if isinstance(msg, ModelRequest):
                for part in msg.parts:
                    if isinstance(part, (SystemPromptPart, UserPromptPart)):
                        size = len(part.content)
                    elif isinstance(part, ToolReturnPart):
                        # ToolReturnPart.content can be Any type
                        import json
                        try:
                            content_str = json.dumps(part.content) if part.content is not None else ""
                        except (TypeError, ValueError):
                            content_str = str(part.content) if part.content is not None else ""
                        size = len(content_str)
                    else:
                        size = 0

                    # Categorize by part type
                    # Note: Check subclasses first (AgentSystemPrompt, SystemStatusPrompt)
                    # before checking base class (SystemPromptPart)
                    if isinstance(part, SystemStatusPrompt):
                        part_type_sizes["system_status"] += size
                    elif isinstance(part, AgentSystemPrompt):
                        part_type_sizes["system_prompts"] += size
                    elif isinstance(part, SystemPromptPart):
                        # Generic system prompt (not AgentSystemPrompt or SystemStatusPrompt)
                        part_type_sizes["system_prompts"] += size
                    elif isinstance(part, UserPromptPart):
                        part_type_sizes["user"] += size
                    elif isinstance(part, ToolReturnPart):
                        # Categorize tool results by tool category
                        category = _get_tool_category(part.tool_name)
                        if category in ("codebase_understanding", "artifact_management", "web_research", "unknown"):
                            part_type_sizes[category] += size

        # Step 4: Calculate output proportions by tool category
        codebase_understanding_size = 0
        artifact_management_size = 0
        web_research_size = 0
        unknown_size = 0
        agent_response_size = 0

        for msg in message_history:
            if isinstance(msg, ModelResponse):
                for part in msg.parts:
                    if isinstance(part, ToolCallPart):
                        category = _get_tool_category(part.tool_name)
                        size = len(str(part.args))

                        if category == "agent_response":
                            agent_response_size += size
                        elif category == "codebase_understanding":
                            codebase_understanding_size += size
                        elif category == "artifact_management":
                            artifact_management_size += size
                        elif category == "web_research":
                            web_research_size += size
                        elif category == "unknown":
                            unknown_size += size
                    elif isinstance(part, TextPart):
                        agent_response_size += len(part.content)

        # Step 5: Allocate input tokens proportionally
        token_counts: dict[str, int] = defaultdict(int)
        total_input_size = sum(part_type_sizes.values())

        if total_input_size > 0 and last_input_tokens > 0:
            for part_type, size in part_type_sizes.items():
                proportion = size / total_input_size
                token_counts[part_type] = int(last_input_tokens * proportion)

        # Step 6: Allocate output tokens proportionally
        total_output_size = (
            codebase_understanding_size
            + artifact_management_size
            + web_research_size
            + unknown_size
            + agent_response_size
        )

        if total_output_size > 0 and total_output_tokens > 0:
            token_counts["codebase_understanding"] += int(
                total_output_tokens * (codebase_understanding_size / total_output_size)
            )
            token_counts["artifact_management"] += int(
                total_output_tokens * (artifact_management_size / total_output_size)
            )
            token_counts["web_research"] += int(total_output_tokens * (web_research_size / total_output_size))
            token_counts["unknown"] += int(total_output_tokens * (unknown_size / total_output_size))
            token_counts["agent_responses"] += int(total_output_tokens * (agent_response_size / total_output_size))
        elif total_output_tokens > 0:
            # If no content, put all in agent responses
            token_counts["agent_responses"] = total_output_tokens

        logger.debug(f"Token allocation complete: {dict(token_counts)}")
        logger.debug(f"Input tokens (from last response): {last_input_tokens}, Output tokens (sum): {total_output_tokens}")

        return dict(token_counts)

    async def analyze_conversation(
        self,
        message_history: list[ModelMessage],
        ui_message_history: list[ModelMessage | HintMessage],
    ) -> ContextAnalysis:
        """Analyze the conversation to determine message type composition.

        Args:
            message_history: The agent message history (for token counting)
            ui_message_history: The UI message history (includes hints)

        Returns:
            ContextAnalysis with statistics for each message type
        """
        # Track counts for each message type
        counts: dict[str, int] = defaultdict(int)

        # Analyze message_history to count message types
        for msg in message_history:
            if isinstance(msg, ModelRequest):
                # Track what types are in this message for counting
                has_user_prompt = False
                has_system_prompt = False
                has_system_status = False

                # Check what part types this message contains
                for part in msg.parts:
                    if isinstance(part, AgentSystemPrompt):
                        has_system_prompt = True
                    elif isinstance(part, SystemStatusPrompt):
                        has_system_status = True
                    elif isinstance(part, SystemPromptPart):
                        # Generic system prompt
                        has_system_prompt = True
                    elif isinstance(part, UserPromptPart):
                        has_user_prompt = True
                    elif isinstance(part, ToolReturnPart):
                        # Categorize tool results by category
                        category = _get_tool_category(part.tool_name)
                        if category in ("codebase_understanding", "artifact_management", "web_research", "unknown"):
                            counts[category] += 1

                # Count the message types (only count once per message)
                if has_system_prompt:
                    counts["system_prompts"] += 1
                if has_system_status:
                    counts["system_status"] += 1
                if has_user_prompt:
                    counts["user"] += 1

            elif isinstance(msg, ModelResponse):
                # Agent responses - count entire response as one
                counts["agent_responses"] += 1

                # Check for tool calls in the response
                for part in msg.parts:  # type: ignore[assignment]
                    if isinstance(part, ToolCallPart):
                        category = _get_tool_category(part.tool_name)
                        if category in ("codebase_understanding", "artifact_management", "web_research", "unknown"):
                            counts[category] += 1

        # Count hints from ui_message_history
        hint_count = sum(1 for msg in ui_message_history if isinstance(msg, HintMessage))
        counts["hints"] = hint_count

        # Use actual API usage data for accurate token counting (avoids synthetic message overhead)
        usage_tokens = self._allocate_tokens_from_usage(message_history)

        user_tokens = usage_tokens.get("user", 0)
        agent_response_tokens = usage_tokens.get("agent_responses", 0)
        system_prompt_tokens = usage_tokens.get("system_prompts", 0)
        system_status_tokens = usage_tokens.get("system_status", 0)
        codebase_understanding_tokens = usage_tokens.get("codebase_understanding", 0)
        artifact_management_tokens = usage_tokens.get("artifact_management", 0)
        web_research_tokens = usage_tokens.get("web_research", 0)
        unknown_tokens = usage_tokens.get("unknown", 0)

        # Estimate hint tokens (rough estimate based on character count)
        hint_tokens = 0
        for msg in ui_message_history:  # type: ignore[assignment]
            if isinstance(msg, HintMessage):
                # Rough estimate: ~4 chars per token
                hint_tokens += len(msg.message) // 4

        # Calculate agent context tokens (excluding UI-only hints)
        agent_context_tokens = (
            user_tokens
            + agent_response_tokens
            + system_prompt_tokens
            + system_status_tokens
            + codebase_understanding_tokens
            + artifact_management_tokens
            + web_research_tokens
            + unknown_tokens
        )

        # Total tokens includes hints for display purposes, but agent_context_tokens does not
        total_tokens = agent_context_tokens + hint_tokens
        total_messages = sum(counts.values())

        # Calculate usable context limit (80% of max_input_tokens) and free space
        # This matches the TOKEN_LIMIT_RATIO = 0.8 from history/constants.py
        max_usable_tokens = int(self.model_config.max_input_tokens * 0.8)
        free_space_tokens = max_usable_tokens - agent_context_tokens

        return ContextAnalysis(
            user_messages=MessageTypeStats(count=counts["user"], tokens=user_tokens),
            agent_responses=MessageTypeStats(count=counts["agent_responses"], tokens=agent_response_tokens),
            system_prompts=MessageTypeStats(count=counts["system_prompts"], tokens=system_prompt_tokens),
            system_status=MessageTypeStats(count=counts["system_status"], tokens=system_status_tokens),
            codebase_understanding=MessageTypeStats(
                count=counts["codebase_understanding"], tokens=codebase_understanding_tokens
            ),
            artifact_management=MessageTypeStats(
                count=counts["artifact_management"], tokens=artifact_management_tokens
            ),
            web_research=MessageTypeStats(count=counts["web_research"], tokens=web_research_tokens),
            unknown=MessageTypeStats(count=counts["unknown"], tokens=unknown_tokens),
            hint_messages=MessageTypeStats(count=counts["hints"], tokens=hint_tokens),
            total_tokens=total_tokens,
            total_messages=total_messages,
            context_window=self.model_config.max_input_tokens,
            agent_context_tokens=agent_context_tokens,
            model_name=self.model_config.name.value,
            max_usable_tokens=max_usable_tokens,
            free_space_tokens=free_space_tokens,
        )

    async def _count_tokens_for_parts(
        self,
        parts: Sequence[UserPromptPart | SystemPromptPart | ToolReturnPart | ToolCallPart],
        part_type: str,
    ) -> int:
        """Count tokens for a list of parts by creating synthetic single-part messages.

        This avoids double-counting when a message contains multiple part types.

        Args:
            parts: List of parts to count tokens for
            part_type: Type of parts ("user", "system", "tool_return", "tool_call")

        Returns:
            Total token count for all parts
        """
        if not parts:
            return 0

        # Create synthetic messages with single parts for accurate token counting
        synthetic_messages: list[ModelMessage] = []

        for part in parts:
            if part_type in ("user", "system", "tool_return"):
                # These are request parts - wrap in ModelRequest
                synthetic_messages.append(ModelRequest(parts=[part]))  # type: ignore[list-item]
            elif part_type == "tool_call":
                # Tool calls are in responses - wrap in ModelResponse
                synthetic_messages.append(ModelResponse(parts=[part]))  # type: ignore[list-item]

        # Count tokens for the synthetic messages
        return await self._count_tokens_safe(synthetic_messages)

    async def _count_tokens_safe(self, messages: Sequence[ModelMessage]) -> int:
        """Count tokens for a list of messages, returning 0 on error.

        Args:
            messages: List of messages to count tokens for

        Returns:
            Token count or 0 if counting fails
        """
        if not messages:
            return 0

        try:
            return await count_tokens_from_messages(list(messages), self.model_config)
        except Exception as e:
            logger.warning(f"Failed to count tokens: {e}")
            # Fallback to rough estimate
            total_chars = sum(len(str(msg)) for msg in messages)
            return total_chars // 4  # Rough estimate: 4 chars per token
