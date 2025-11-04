"""Core context analysis logic."""

import json
from collections.abc import Sequence

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
from shotgun.agents.history.token_estimation import estimate_tokens_from_messages
from shotgun.agents.messages import AgentSystemPrompt, SystemStatusPrompt
from shotgun.logging_config import get_logger
from shotgun.tui.screens.chat_screen.hint_message import HintMessage

from .constants import ToolCategory, get_tool_category
from .models import ContextAnalysis, MessageTypeStats, TokenAllocation

logger = get_logger(__name__)


class ContextAnalyzer:
    """Analyzes conversation message history for context composition."""

    def __init__(self, model_config: ModelConfig):
        """Initialize the analyzer with model configuration for token counting.

        Args:
            model_config: Model configuration for accurate token counting
        """
        self.model_config = model_config

    async def _allocate_tokens_from_usage(
        self,
        message_history: list[ModelMessage],
    ) -> TokenAllocation:
        """Allocate tokens from actual API usage data proportionally to parts.

        This uses the ground truth token counts from ModelResponse.usage instead of
        creating synthetic messages, which avoids inflating counts with message framing overhead.

        IMPORTANT: usage.input_tokens is cumulative (includes all conversation history), so we:
        1. Use the LAST response's input_tokens as the ground truth total
        2. Calculate proportions based on content size across ALL requests
        3. Allocate the ground truth total proportionally

        If usage data is missing or zero (e.g., after compaction), falls back to token estimation.

        Args:
            message_history: List of actual messages from conversation

        Returns:
            TokenAllocation with token counts by message/tool type
        """
        # Step 1: Find the last response's usage data (ground truth for input tokens)
        last_input_tokens = 0
        total_output_tokens = 0

        for msg in reversed(message_history):
            if isinstance(msg, ModelResponse) and msg.usage:
                last_input_tokens = msg.usage.input_tokens + msg.usage.cache_read_tokens
                break

        if last_input_tokens == 0:
            # Fallback to token estimation (no logging to reduce verbosity)
            last_input_tokens = await estimate_tokens_from_messages(
                message_history, self.model_config
            )

        # Step 2: Calculate total output tokens (sum across all responses)
        for msg in message_history:
            if isinstance(msg, ModelResponse) and msg.usage:
                total_output_tokens += msg.usage.output_tokens

        # Step 3: Calculate content size proportions for each part type across ALL requests
        # Initialize size accumulators
        user_size = 0
        system_prompts_size = 0
        system_status_size = 0
        codebase_understanding_input_size = 0
        artifact_management_input_size = 0
        web_research_input_size = 0
        unknown_input_size = 0

        for msg in message_history:
            if isinstance(msg, ModelRequest):
                for part in msg.parts:
                    if isinstance(part, (SystemPromptPart, UserPromptPart)):
                        size = len(part.content)
                    elif isinstance(part, ToolReturnPart):
                        # ToolReturnPart.content can be Any type
                        try:
                            content_str = (
                                json.dumps(part.content)
                                if part.content is not None
                                else ""
                            )
                        except (TypeError, ValueError):
                            content_str = (
                                str(part.content) if part.content is not None else ""
                            )
                        size = len(content_str)
                    else:
                        size = 0

                    # Categorize by part type
                    # Note: Check subclasses first (AgentSystemPrompt, SystemStatusPrompt)
                    # before checking base class (SystemPromptPart)
                    if isinstance(part, SystemStatusPrompt):
                        system_status_size += size
                    elif isinstance(part, AgentSystemPrompt):
                        system_prompts_size += size
                    elif isinstance(part, SystemPromptPart):
                        # Generic system prompt (not AgentSystemPrompt or SystemStatusPrompt)
                        system_prompts_size += size
                    elif isinstance(part, UserPromptPart):
                        user_size += size
                    elif isinstance(part, ToolReturnPart):
                        # Categorize tool results by tool category
                        category = get_tool_category(part.tool_name)
                        if category == ToolCategory.CODEBASE_UNDERSTANDING:
                            codebase_understanding_input_size += size
                        elif category == ToolCategory.ARTIFACT_MANAGEMENT:
                            artifact_management_input_size += size
                        elif category == ToolCategory.WEB_RESEARCH:
                            web_research_input_size += size
                        elif category == ToolCategory.UNKNOWN:
                            unknown_input_size += size

        # Step 4: Calculate output proportions by tool category
        codebase_understanding_size = 0
        artifact_management_size = 0
        web_research_size = 0
        unknown_size = 0
        agent_response_size = 0

        for msg in message_history:
            if isinstance(msg, ModelResponse):
                for part in msg.parts:  # type: ignore[assignment]
                    if isinstance(part, ToolCallPart):
                        category = get_tool_category(part.tool_name)
                        size = len(str(part.args))

                        if category == ToolCategory.AGENT_RESPONSE:
                            agent_response_size += size
                        elif category == ToolCategory.CODEBASE_UNDERSTANDING:
                            codebase_understanding_size += size
                        elif category == ToolCategory.ARTIFACT_MANAGEMENT:
                            artifact_management_size += size
                        elif category == ToolCategory.WEB_RESEARCH:
                            web_research_size += size
                        elif category == ToolCategory.UNKNOWN:
                            unknown_size += size
                    elif isinstance(part, TextPart):
                        agent_response_size += len(part.content)

        # Step 5: Allocate input tokens proportionally
        # Initialize TokenAllocation fields
        user_tokens = 0
        agent_response_tokens = 0
        system_prompt_tokens = 0
        system_status_tokens = 0
        codebase_understanding_tokens = 0
        artifact_management_tokens = 0
        web_research_tokens = 0
        unknown_tokens = 0

        total_input_size = (
            user_size
            + system_prompts_size
            + system_status_size
            + codebase_understanding_input_size
            + artifact_management_input_size
            + web_research_input_size
            + unknown_input_size
        )

        if total_input_size > 0 and last_input_tokens > 0:
            user_tokens = int(last_input_tokens * (user_size / total_input_size))
            system_prompt_tokens = int(
                last_input_tokens * (system_prompts_size / total_input_size)
            )
            system_status_tokens = int(
                last_input_tokens * (system_status_size / total_input_size)
            )
            codebase_understanding_tokens = int(
                last_input_tokens
                * (codebase_understanding_input_size / total_input_size)
            )
            artifact_management_tokens = int(
                last_input_tokens * (artifact_management_input_size / total_input_size)
            )
            web_research_tokens = int(
                last_input_tokens * (web_research_input_size / total_input_size)
            )
            unknown_tokens = int(
                last_input_tokens * (unknown_input_size / total_input_size)
            )

        # Step 6: Allocate output tokens proportionally
        total_output_size = (
            codebase_understanding_size
            + artifact_management_size
            + web_research_size
            + unknown_size
            + agent_response_size
        )

        if total_output_size > 0 and total_output_tokens > 0:
            codebase_understanding_tokens += int(
                total_output_tokens * (codebase_understanding_size / total_output_size)
            )
            artifact_management_tokens += int(
                total_output_tokens * (artifact_management_size / total_output_size)
            )
            web_research_tokens += int(
                total_output_tokens * (web_research_size / total_output_size)
            )
            unknown_tokens += int(
                total_output_tokens * (unknown_size / total_output_size)
            )
            agent_response_tokens += int(
                total_output_tokens * (agent_response_size / total_output_size)
            )
        elif total_output_tokens > 0:
            # If no content, put all in agent responses
            agent_response_tokens = total_output_tokens

        # Token allocation complete (no logging to reduce verbosity)

        # Create TokenAllocation model
        return TokenAllocation(
            user=user_tokens,
            agent_responses=agent_response_tokens,
            system_prompts=system_prompt_tokens,
            system_status=system_status_tokens,
            codebase_understanding=codebase_understanding_tokens,
            artifact_management=artifact_management_tokens,
            web_research=web_research_tokens,
            unknown=unknown_tokens,
        )

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
        user_count = 0
        agent_responses_count = 0
        system_prompts_count = 0
        system_status_count = 0
        codebase_understanding_count = 0
        artifact_management_count = 0
        web_research_count = 0
        unknown_count = 0

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
                        category = get_tool_category(part.tool_name)
                        if category == ToolCategory.CODEBASE_UNDERSTANDING:
                            codebase_understanding_count += 1
                        elif category == ToolCategory.ARTIFACT_MANAGEMENT:
                            artifact_management_count += 1
                        elif category == ToolCategory.WEB_RESEARCH:
                            web_research_count += 1
                        elif category == ToolCategory.UNKNOWN:
                            unknown_count += 1

                # Count the message types (only count once per message)
                if has_system_prompt:
                    system_prompts_count += 1
                if has_system_status:
                    system_status_count += 1
                if has_user_prompt:
                    user_count += 1

            elif isinstance(msg, ModelResponse):
                # Agent responses - count entire response as one
                agent_responses_count += 1

                # Check for tool calls in the response
                for part in msg.parts:  # type: ignore[assignment]
                    if isinstance(part, ToolCallPart):
                        category = get_tool_category(part.tool_name)
                        if category == ToolCategory.CODEBASE_UNDERSTANDING:
                            codebase_understanding_count += 1
                        elif category == ToolCategory.ARTIFACT_MANAGEMENT:
                            artifact_management_count += 1
                        elif category == ToolCategory.WEB_RESEARCH:
                            web_research_count += 1
                        elif category == ToolCategory.UNKNOWN:
                            unknown_count += 1

        # Count hints from ui_message_history
        hint_count = sum(
            1 for msg in ui_message_history if isinstance(msg, HintMessage)
        )

        # Use actual API usage data for accurate token counting (avoids synthetic message overhead)
        usage_tokens = await self._allocate_tokens_from_usage(message_history)

        user_tokens = usage_tokens.user
        agent_response_tokens = usage_tokens.agent_responses
        system_prompt_tokens = usage_tokens.system_prompts
        system_status_tokens = usage_tokens.system_status
        codebase_understanding_tokens = usage_tokens.codebase_understanding
        artifact_management_tokens = usage_tokens.artifact_management
        web_research_tokens = usage_tokens.web_research
        unknown_tokens = usage_tokens.unknown

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
        total_messages = (
            user_count
            + agent_responses_count
            + system_prompts_count
            + system_status_count
            + codebase_understanding_count
            + artifact_management_count
            + web_research_count
            + unknown_count
            + hint_count
        )

        # Calculate usable context limit (80% of max_input_tokens) and free space
        # This matches the TOKEN_LIMIT_RATIO = 0.8 from history/constants.py
        max_usable_tokens = int(self.model_config.max_input_tokens * 0.8)
        free_space_tokens = max_usable_tokens - agent_context_tokens

        return ContextAnalysis(
            user_messages=MessageTypeStats(count=user_count, tokens=user_tokens),
            agent_responses=MessageTypeStats(
                count=agent_responses_count, tokens=agent_response_tokens
            ),
            system_prompts=MessageTypeStats(
                count=system_prompts_count, tokens=system_prompt_tokens
            ),
            system_status=MessageTypeStats(
                count=system_status_count, tokens=system_status_tokens
            ),
            codebase_understanding=MessageTypeStats(
                count=codebase_understanding_count,
                tokens=codebase_understanding_tokens,
            ),
            artifact_management=MessageTypeStats(
                count=artifact_management_count, tokens=artifact_management_tokens
            ),
            web_research=MessageTypeStats(
                count=web_research_count, tokens=web_research_tokens
            ),
            unknown=MessageTypeStats(count=unknown_count, tokens=unknown_tokens),
            hint_messages=MessageTypeStats(count=hint_count, tokens=hint_tokens),
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
        parts: Sequence[
            UserPromptPart | SystemPromptPart | ToolReturnPart | ToolCallPart
        ],
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
