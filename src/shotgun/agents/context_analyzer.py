"""Analyze conversation context composition and display statistics."""

from collections import defaultdict
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

        # Add context window usage info (assuming 100k context window)
        context_window = 100_000
        usage_percent = (self.total_tokens / context_window * 100) if self.total_tokens > 0 else 0
        lines.append(f"- Context Window Usage: ~{usage_percent:.1f}% of {context_window:,} limit")

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

        # Track separate message lists for token counting
        user_msgs: list[ModelMessage] = []
        assistant_msgs: list[ModelMessage] = []
        system_prompt_msgs: list[ModelMessage] = []
        system_status_msgs: list[ModelMessage] = []
        tool_result_msgs: list[ModelMessage] = []

        # Analyze message_history for most message types
        for msg in message_history:
            if isinstance(msg, ModelRequest):
                # Track what types are in this message
                has_user_prompt = False
                has_system_prompt = False
                has_system_status = False
                has_tool_return = False

                # Check for different part types
                for part in msg.parts:
                    if isinstance(part, SystemPromptPart):
                        if isinstance(part, AgentSystemPrompt):
                            has_system_prompt = True
                            system_prompt_msgs.append(msg)
                        elif isinstance(part, SystemStatusPrompt):
                            has_system_status = True
                            system_status_msgs.append(msg)
                        else:
                            # Generic system prompt
                            has_system_prompt = True
                            system_prompt_msgs.append(msg)
                    elif isinstance(part, UserPromptPart):
                        # User text message
                        has_user_prompt = True
                        user_msgs.append(msg)
                    elif isinstance(part, ToolReturnPart):
                        has_tool_return = True
                        tool_result_msgs.append(msg)

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
                # Assistant responses
                counts["assistant"] += 1
                assistant_msgs.append(msg)

                # Check for tool calls in the response
                for part in msg.parts:  # type: ignore[assignment]
                    if isinstance(part, ToolCallPart):
                        counts["tool_calls"] += 1
                        # Create a synthetic message for token counting tool calls
                        # We'll count them as part of the assistant message

        # Count hints from ui_message_history
        hint_count = sum(1 for msg in ui_message_history if isinstance(msg, HintMessage))
        counts["hints"] = hint_count

        # Count tokens for each message type
        user_tokens = await self._count_tokens_safe(user_msgs)
        assistant_tokens = await self._count_tokens_safe(assistant_msgs)
        system_prompt_tokens = await self._count_tokens_safe(system_prompt_msgs)
        system_status_tokens = await self._count_tokens_safe(system_status_msgs)
        tool_result_tokens = await self._count_tokens_safe(tool_result_msgs)

        # For tool calls, they're typically part of assistant messages
        # We'll estimate by looking at parts
        tool_call_tokens = 0
        for msg in message_history:
            if isinstance(msg, ModelResponse):
                for part in msg.parts:  # type: ignore[assignment]
                    if isinstance(part, ToolCallPart):
                        # Rough estimate: tool name + args
                        tool_call_tokens += len(part.tool_name) + len(str(part.args_as_dict()))

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
        )

    async def _count_tokens_safe(self, messages: list[ModelMessage]) -> int:
        """Count tokens for a list of messages, returning 0 on error.

        Args:
            messages: List of messages to count tokens for

        Returns:
            Token count or 0 if counting fails
        """
        if not messages:
            return 0

        try:
            return await count_tokens_from_messages(messages, self.model_config)
        except Exception as e:
            logger.warning(f"Failed to count tokens: {e}")
            # Fallback to rough estimate
            total_chars = sum(len(str(msg)) for msg in messages)
            return total_chars // 4  # Rough estimate: 4 chars per token
