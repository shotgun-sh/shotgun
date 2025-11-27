"""Pattern-based chunking for oversized conversation compaction.

This module provides functions to break oversized conversations into logical
chunks for summarization, preserving semantic units like tool call sequences.
"""

import logging
from dataclasses import dataclass, field

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from shotgun.agents.config.models import ModelConfig

from .constants import CHUNK_TARGET_RATIO, RETENTION_WINDOW_MESSAGES
from .token_estimation import estimate_tokens_from_messages

logger = logging.getLogger(__name__)


@dataclass
class MessageGroup:
    """A logical group of messages that must stay together.

    Examples:
    - A single user message
    - A tool call sequence: ModelResponse(ToolCallPart) -> ModelRequest(ToolReturnPart)
    - A standalone assistant response
    """

    messages: list[ModelMessage]
    is_tool_sequence: bool = False
    start_index: int = 0
    end_index: int = 0
    _token_count: int | None = field(default=None, repr=False)

    async def get_token_count(self, model_config: ModelConfig) -> int:
        """Lazily compute and cache token count for this group."""
        if self._token_count is None:
            self._token_count = await estimate_tokens_from_messages(
                self.messages, model_config
            )
        return self._token_count


@dataclass
class Chunk:
    """A chunk of message groups ready for summarization."""

    groups: list[MessageGroup]
    chunk_index: int
    total_token_estimate: int = 0

    def get_all_messages(self) -> list[ModelMessage]:
        """Flatten all messages in this chunk."""
        messages: list[ModelMessage] = []
        for group in self.groups:
            messages.extend(group.messages)
        return messages


def identify_message_groups(messages: list[ModelMessage]) -> list[MessageGroup]:
    """Identify logical message groups that must stay together.

    Rules:
    1. Tool calls must include their responses (matched by tool_call_id)
    2. User messages are individual groups
    3. Standalone assistant responses are individual groups

    Args:
        messages: The full message history

    Returns:
        List of MessageGroup objects
    """
    groups: list[MessageGroup] = []

    # Track pending tool calls that need their returns
    # Maps tool_call_id -> group index
    pending_tool_calls: dict[str, int] = {}

    for i, msg in enumerate(messages):
        if isinstance(msg, ModelResponse):
            # Check for tool calls in response
            tool_calls = [p for p in msg.parts if isinstance(p, ToolCallPart)]

            if tool_calls:
                # Start a tool sequence group
                group = MessageGroup(
                    messages=[msg],
                    is_tool_sequence=True,
                    start_index=i,
                    end_index=i,
                )
                group_idx = len(groups)
                groups.append(group)

                # Track all tool call IDs in this response
                for tc in tool_calls:
                    if tc.tool_call_id:
                        pending_tool_calls[tc.tool_call_id] = group_idx
            else:
                # Standalone assistant response (text only)
                groups.append(
                    MessageGroup(
                        messages=[msg],
                        is_tool_sequence=False,
                        start_index=i,
                        end_index=i,
                    )
                )

        elif isinstance(msg, ModelRequest):
            # Check for tool returns in request
            tool_returns = [p for p in msg.parts if isinstance(p, ToolReturnPart)]
            user_prompts = [p for p in msg.parts if isinstance(p, UserPromptPart)]

            if tool_returns:
                # Add to corresponding tool call groups
                for tr in tool_returns:
                    if tr.tool_call_id and tr.tool_call_id in pending_tool_calls:
                        group_idx = pending_tool_calls.pop(tr.tool_call_id)
                        groups[group_idx].messages.append(msg)
                        groups[group_idx].end_index = i
                    # Note: orphaned tool returns are handled by filter_orphaned_tool_responses

            elif user_prompts:
                # User message - standalone group
                groups.append(
                    MessageGroup(
                        messages=[msg],
                        is_tool_sequence=False,
                        start_index=i,
                        end_index=i,
                    )
                )
            # Note: System prompts are handled separately by compaction

    logger.debug(
        f"Identified {len(groups)} message groups "
        f"({sum(1 for g in groups if g.is_tool_sequence)} tool sequences)"
    )

    return groups


async def create_chunks(
    groups: list[MessageGroup],
    model_config: ModelConfig,
    retention_window: int = RETENTION_WINDOW_MESSAGES,
) -> tuple[list[Chunk], list[ModelMessage]]:
    """Create chunks from message groups, respecting token limits.

    Args:
        groups: List of message groups from identify_message_groups()
        model_config: Model configuration for token limits
        retention_window: Number of recent groups to keep outside compaction

    Returns:
        Tuple of (chunks_to_summarize, retained_recent_messages)
    """
    max_chunk_tokens = int(model_config.max_input_tokens * CHUNK_TARGET_RATIO)

    # Handle edge case: too few groups
    if len(groups) <= retention_window:
        all_messages: list[ModelMessage] = []
        for g in groups:
            all_messages.extend(g.messages)
        return [], all_messages

    # Separate retention window from groups to chunk
    groups_to_chunk = groups[:-retention_window]
    retained_groups = groups[-retention_window:]

    # Build chunks
    chunks: list[Chunk] = []
    current_groups: list[MessageGroup] = []
    current_tokens = 0

    for group in groups_to_chunk:
        group_tokens = await group.get_token_count(model_config)

        # Handle oversized single group - becomes its own chunk
        if group_tokens > max_chunk_tokens:
            # Finish current chunk if any
            if current_groups:
                chunks.append(
                    Chunk(
                        groups=current_groups,
                        chunk_index=len(chunks),
                        total_token_estimate=current_tokens,
                    )
                )
                current_groups = []
                current_tokens = 0

            # Add oversized as its own chunk
            chunks.append(
                Chunk(
                    groups=[group],
                    chunk_index=len(chunks),
                    total_token_estimate=group_tokens,
                )
            )
            logger.warning(
                f"Oversized message group ({group_tokens:,} tokens) "
                f"added as single chunk - may need special handling"
            )
            continue

        # Would adding this group exceed limit?
        if current_tokens + group_tokens > max_chunk_tokens:
            # Finish current chunk
            if current_groups:
                chunks.append(
                    Chunk(
                        groups=current_groups,
                        chunk_index=len(chunks),
                        total_token_estimate=current_tokens,
                    )
                )
            current_groups = [group]
            current_tokens = group_tokens
        else:
            current_groups.append(group)
            current_tokens += group_tokens

    # Don't forget last chunk
    if current_groups:
        chunks.append(
            Chunk(
                groups=current_groups,
                chunk_index=len(chunks),
                total_token_estimate=current_tokens,
            )
        )

    # Extract retained messages
    retained_messages: list[ModelMessage] = []
    for g in retained_groups:
        retained_messages.extend(g.messages)

    # Update chunk indices (in case any were out of order)
    for i, chunk in enumerate(chunks):
        chunk.chunk_index = i

    logger.info(
        f"Created {len(chunks)} chunks for compaction, "
        f"retaining {len(retained_messages)} recent messages"
    )

    return chunks, retained_messages


async def chunk_messages_for_compaction(
    messages: list[ModelMessage],
    model_config: ModelConfig,
) -> tuple[list[Chunk], list[ModelMessage]]:
    """Main entry point: chunk oversized conversation for summarization.

    This function identifies logical message groups (preserving tool call sequences),
    then packs them into chunks that fit within model token limits.

    Args:
        messages: Full conversation message history
        model_config: Model configuration for token limits

    Returns:
        Tuple of (chunks_to_summarize, retention_window_messages)
    """
    groups = identify_message_groups(messages)
    return await create_chunks(groups, model_config)
