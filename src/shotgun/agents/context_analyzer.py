"""Analyze conversation context composition and display statistics."""

import asyncio
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

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
    assistant_messages: MessageTypeStats
    system_prompts: MessageTypeStats
    system_status: MessageTypeStats
    tool_calls: MessageTypeStats
    tool_results: MessageTypeStats
    hint_messages: MessageTypeStats
    total_tokens: int
    total_messages: int
    context_window: int
    agent_context_tokens: int  # Tokens that actually consume agent context (excluding UI-only)

    def get_percentage(self, stats: MessageTypeStats) -> float:
        """Calculate percentage of agent context tokens for a message type."""
        return (stats.tokens / self.agent_context_tokens * 100) if self.agent_context_tokens > 0 else 0.0

    def format_analysis(self) -> str:
        """Format the analysis as markdown for display."""
        lines = ["# Conversation Context Analysis", "", "## Agent Context Composition"]

        # Add agent context categories only (hints are not part of agent context)
        agent_categories = [
            ("🧑 User Messages", self.user_messages),
            ("🤖 Assistant Messages", self.assistant_messages),
            ("📋 System Prompts", self.system_prompts),
            ("📊 System Status", self.system_status),
            ("🔧 Tool Calls", self.tool_calls),
            ("📥 Tool Results", self.tool_results),
        ]

        for label, stats in agent_categories:
            if stats.count > 0:
                percentage = self.get_percentage(stats)
                lines.append(
                    f"- {label}: {percentage:.1f}% ({stats.count} messages, ~{stats.tokens:,} tokens)"
                )

        # Add summary section
        lines.extend(
            [
                "",
                "## Summary",
                f"- Total Messages: {self.total_messages - self.hint_messages.count}",
                f"- Agent Context Tokens: ~{self.agent_context_tokens:,}",
            ]
        )

        # Calculate average based on agent context messages only (excluding hints)
        agent_message_count = self.total_messages - self.hint_messages.count
        if agent_message_count > 0:
            avg_length = self.agent_context_tokens / agent_message_count
            lines.append(f"- Average Message Length: ~{avg_length:.0f} tokens")

        # Add context window usage based ONLY on agent context tokens
        usage_percent = (
            (self.agent_context_tokens / self.context_window * 100) if self.agent_context_tokens > 0 else 0
        )
        lines.append(
            f"- Context Window Usage: ~{usage_percent:.1f}% of {self.context_window:,} limit"
        )

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
                        part_type_sizes["tool_results"] += size

        # Step 4: Calculate output proportions (tool calls vs assistant text)
        # Note: final_result is semantically an assistant response, not a tool call
        tool_call_size = 0
        text_size = 0

        for msg in message_history:
            if isinstance(msg, ModelResponse):
                for part in msg.parts:
                    if isinstance(part, ToolCallPart):
                        # Treat final_result as assistant text, not tool call
                        if part.tool_name == "final_result":
                            text_size += len(str(part.args))
                        else:
                            tool_call_size += len(str(part.args))
                    elif isinstance(part, TextPart):
                        text_size += len(part.content)

        # Step 5: Allocate input tokens proportionally
        token_counts: dict[str, int] = defaultdict(int)
        total_input_size = sum(part_type_sizes.values())

        if total_input_size > 0 and last_input_tokens > 0:
            for part_type, size in part_type_sizes.items():
                proportion = size / total_input_size
                token_counts[part_type] = int(last_input_tokens * proportion)

        # Step 6: Allocate output tokens proportionally
        total_output_size = tool_call_size + text_size

        if total_output_size > 0 and total_output_tokens > 0:
            token_counts["tool_calls"] = int(total_output_tokens * (tool_call_size / total_output_size))
            token_counts["assistant"] = int(total_output_tokens * (text_size / total_output_size))
        elif total_output_tokens > 0:
            # If no content, put all in assistant
            token_counts["assistant"] = total_output_tokens

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
                has_tool_return = False

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
                        has_tool_return = True

                # Count the message types (only count once per message)
                if has_system_prompt:
                    counts["system_prompts"] += 1
                if has_system_status:
                    counts["system_status"] += 1
                if has_user_prompt:
                    counts["user"] += 1
                if has_tool_return:
                    counts["tool_results"] += 1

            elif isinstance(msg, ModelResponse):
                # Assistant responses - count entire response as one
                counts["assistant"] += 1

                # Check for tool calls in the response
                # Note: final_result is semantically an assistant response, not a tool call
                for part in msg.parts:  # type: ignore[assignment]
                    if isinstance(part, ToolCallPart):
                        if part.tool_name != "final_result":
                            counts["tool_calls"] += 1

        # Count hints from ui_message_history
        hint_count = sum(1 for msg in ui_message_history if isinstance(msg, HintMessage))
        counts["hints"] = hint_count

        # Use actual API usage data for accurate token counting (avoids synthetic message overhead)
        usage_tokens = self._allocate_tokens_from_usage(message_history)

        user_tokens = usage_tokens.get("user", 0)
        assistant_tokens = usage_tokens.get("assistant", 0)
        system_prompt_tokens = usage_tokens.get("system_prompts", 0)
        system_status_tokens = usage_tokens.get("system_status", 0)
        tool_call_tokens = usage_tokens.get("tool_calls", 0)
        tool_result_tokens = usage_tokens.get("tool_results", 0)

        # Estimate hint tokens (rough estimate based on character count)
        hint_tokens = 0
        for msg in ui_message_history:  # type: ignore[assignment]
            if isinstance(msg, HintMessage):
                # Rough estimate: ~4 chars per token
                hint_tokens += len(msg.message) // 4

        # Calculate agent context tokens (excluding UI-only hints)
        agent_context_tokens = (
            user_tokens
            + assistant_tokens
            + system_prompt_tokens
            + system_status_tokens
            + tool_call_tokens
            + tool_result_tokens
        )

        # Total tokens includes hints for display purposes, but agent_context_tokens does not
        total_tokens = agent_context_tokens + hint_tokens
        total_messages = sum(counts.values())

        return ContextAnalysis(
            user_messages=MessageTypeStats(count=counts["user"], tokens=user_tokens),
            assistant_messages=MessageTypeStats(count=counts["assistant"], tokens=assistant_tokens),
            system_prompts=MessageTypeStats(count=counts["system_prompts"], tokens=system_prompt_tokens),
            system_status=MessageTypeStats(count=counts["system_status"], tokens=system_status_tokens),
            tool_calls=MessageTypeStats(count=counts["tool_calls"], tokens=tool_call_tokens),
            tool_results=MessageTypeStats(count=counts["tool_results"], tokens=tool_result_tokens),
            hint_messages=MessageTypeStats(count=counts["hints"], tokens=hint_tokens),
            total_tokens=total_tokens,
            total_messages=total_messages,
            context_window=self.model_config.max_input_tokens,
            agent_context_tokens=agent_context_tokens,
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
