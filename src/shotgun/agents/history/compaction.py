"""Conversation compaction utilities."""

from pydantic_ai.messages import ModelMessage
from pydantic_ai.usage import RequestUsage

from shotgun.agents.models import AgentDeps
from shotgun.logging_config import get_logger

from .token_estimation import estimate_tokens_from_messages

logger = get_logger(__name__)


async def apply_persistent_compaction(
    messages: list[ModelMessage], deps: AgentDeps
) -> list[ModelMessage]:
    """Apply compaction to message history for persistent storage.

    This ensures that compacted history is actually used as the conversation baseline,
    preventing cascading compaction issues across both CLI and TUI usage patterns.

    Args:
        messages: Full message history from agent run
        deps: Agent dependencies containing model config

    Returns:
        Compacted message history that should be stored as conversation state
    """
    from .history_processors import token_limit_compactor

    try:
        # Count actual token usage using shared utility
        estimated_tokens = estimate_tokens_from_messages(messages, deps.llm_model)

        # Create minimal usage info for compaction check
        usage = RequestUsage(
            input_tokens=estimated_tokens,
            output_tokens=0,
        )

        # Create a minimal context object for compaction
        class MockContext:
            def __init__(self, deps: AgentDeps, usage: RequestUsage | None):
                self.deps = deps
                self.usage = usage

        ctx = MockContext(deps, usage)
        compacted_messages = await token_limit_compactor(ctx, messages)

        # Log the result for monitoring
        original_size = len(messages)
        compacted_size = len(compacted_messages)

        if compacted_size < original_size:
            reduction_pct = ((original_size - compacted_size) / original_size) * 100
            logger.debug(
                f"Persistent compaction applied: {original_size} → {compacted_size} messages "
                f"({reduction_pct:.1f}% reduction)"
            )
        else:
            logger.debug(
                f"No persistent compaction needed: {original_size} messages unchanged"
            )

        return compacted_messages

    except Exception as e:
        # If compaction fails, return original messages
        # This ensures the system remains functional even if compaction has issues
        logger.warning(f"Persistent compaction failed, using original history: {e}")
        return messages


def should_apply_persistent_compaction(deps: AgentDeps) -> bool:
    """Check if persistent compaction should be applied.

    Args:
        deps: Agent dependencies

    Returns:
        True if persistent compaction should be applied
    """
    # For now, always apply persistent compaction
    # Future: Add configuration option in deps or environment variable
    return True
