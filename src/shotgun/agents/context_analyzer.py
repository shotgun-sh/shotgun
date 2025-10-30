"""Analyze conversation context composition and display statistics."""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
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

    def get_percentage(self, stats: MessageTypeStats) -> float:
        """Calculate percentage of total tokens for a message type."""
        return (stats.tokens / self.total_tokens * 100) if self.total_tokens > 0 else 0.0

    def format_analysis(self) -> str:
        """Format the analysis as markdown for display."""
        lines = ["# Conversation Context Analysis", "", "## Message Composition"]

        # Add each category with emoji, percentage, count, and tokens
        categories = [
            ("🧑 User Messages", self.user_messages),
            ("🤖 Assistant Messages", self.assistant_messages),
            ("📋 System Prompts", self.system_prompts),
            ("📊 System Status", self.system_status),
            ("🔧 Tool Calls", self.tool_calls),
            ("📥 Tool Results", self.tool_results),
            ("💡 Hints", self.hint_messages),
        ]

        for label, stats in categories:
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
                f"- Total Messages: {self.total_messages}",
                f"- Total Tokens: ~{self.total_tokens:,}",
            ]
        )

        if self.total_messages > 0:
            avg_length = self.total_tokens / self.total_messages
            lines.append(f"- Average Message Length: ~{avg_length:.0f} tokens")

        # Add context window usage info using actual model's max_input_tokens
        usage_percent = (
            (self.total_tokens / self.context_window * 100) if self.total_tokens > 0 else 0
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

        # Track separate parts for token counting (to avoid double-counting)
        # We'll create synthetic single-part messages for accurate token counting
        user_parts: list[UserPromptPart] = []
        system_prompt_parts: list[SystemPromptPart] = []
        system_status_parts: list[SystemStatusPrompt] = []
        tool_return_parts: list[ToolReturnPart] = []

        # For assistant messages and tool calls, track the full messages/parts
        assistant_msgs: list[ModelResponse] = []
        tool_call_parts: list[ToolCallPart] = []

        # Analyze message_history for most message types
        for msg in message_history:
            if isinstance(msg, ModelRequest):
                # Track what types are in this message for counting
                has_user_prompt = False
                has_system_prompt = False
                has_system_status = False
                has_tool_return = False

                # Collect individual parts for token counting
                for part in msg.parts:
                    if isinstance(part, SystemPromptPart):
                        if isinstance(part, AgentSystemPrompt):
                            has_system_prompt = True
                            system_prompt_parts.append(part)
                        elif isinstance(part, SystemStatusPrompt):
                            has_system_status = True
                            system_status_parts.append(part)
                        else:
                            # Generic system prompt
                            has_system_prompt = True
                            system_prompt_parts.append(part)
                    elif isinstance(part, UserPromptPart):
                        has_user_prompt = True
                        user_parts.append(part)
                    elif isinstance(part, ToolReturnPart):
                        has_tool_return = True
                        tool_return_parts.append(part)

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
                assistant_msgs.append(msg)

                # Check for tool calls in the response
                for part in msg.parts:  # type: ignore[assignment]
                    if isinstance(part, ToolCallPart):
                        counts["tool_calls"] += 1
                        tool_call_parts.append(part)

        # Count hints from ui_message_history
        hint_count = sum(1 for msg in ui_message_history if isinstance(msg, HintMessage))
        counts["hints"] = hint_count

        # Count tokens for each part type by creating synthetic messages
        user_tokens = await self._count_tokens_for_parts(user_parts, "user")
        system_prompt_tokens = await self._count_tokens_for_parts(system_prompt_parts, "system")
        system_status_tokens = await self._count_tokens_for_parts(system_status_parts, "system")
        tool_result_tokens = await self._count_tokens_for_parts(tool_return_parts, "tool_return")

        # Count tokens for assistant messages (these are already full messages)
        assistant_tokens = await self._count_tokens_safe(assistant_msgs)

        # Count tokens for tool calls
        tool_call_tokens = await self._count_tokens_for_parts(tool_call_parts, "tool_call")

        # Estimate hint tokens (rough estimate based on character count)
        hint_tokens = 0
        for msg in ui_message_history:  # type: ignore[assignment]
            if isinstance(msg, HintMessage):
                # Rough estimate: ~4 chars per token
                hint_tokens += len(msg.message) // 4

        # Calculate totals
        total_tokens = (
            user_tokens
            + assistant_tokens
            + system_prompt_tokens
            + system_status_tokens
            + tool_call_tokens
            + tool_result_tokens
            + hint_tokens
        )
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
