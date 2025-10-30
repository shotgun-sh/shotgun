"""Conversation compaction utilities."""

from pydantic_ai.messages import ModelMessage
from pydantic_ai.usage import RequestUsage

from shotgun.agents.config.models import ModelConfig
from shotgun.agents.models import AgentDeps
from shotgun.logging_config import get_logger
from shotgun.posthog_telemetry import track_event

from .token_estimation import estimate_tokens_from_messages

logger = get_logger(__name__)


async def get_compaction_context_properties(
    messages: list[ModelMessage],
    model_config: ModelConfig,
    ui_messages: list[ModelMessage] | None = None,
) -> dict[str, float | int | str]:
    """Get context composition properties for PostHog event tracking.

    Args:
        messages: Message history to analyze
        model_config: Model configuration
        ui_messages: Optional UI message history (includes hints)

    Returns:
        Dictionary of properties with context composition as decimal proportions (0.0-1.0),
        context window metrics, and model/provider information
    """
    from shotgun.agents.context_analyzer import ContextAnalyzer

    try:
        analyzer = ContextAnalyzer(model_config)
        analysis = await analyzer.analyze_conversation(
            messages, ui_messages if ui_messages is not None else messages  # type: ignore[arg-type]
        )

        # Convert percentages to decimal proportions (0.0-1.0)
        return {
            # Context composition as proportions
            "user_message_proportion": round(
                analysis.get_percentage(analysis.user_messages) / 100, 4
            ),
            "assistant_message_proportion": round(
                analysis.get_percentage(analysis.assistant_messages) / 100, 4
            ),
            "system_prompt_proportion": round(
                analysis.get_percentage(analysis.system_prompts) / 100, 4
            ),
            "system_status_proportion": round(
                analysis.get_percentage(analysis.system_status) / 100, 4
            ),
            "tool_call_proportion": round(
                analysis.get_percentage(analysis.tool_calls) / 100, 4
            ),
            "tool_result_proportion": round(
                analysis.get_percentage(analysis.tool_results) / 100, 4
            ),
            # Context window metrics
            "context_window_size": analysis.context_window,
            "context_window_usage": round(
                analysis.total_tokens / analysis.context_window, 4
            )
            if analysis.context_window > 0
            else 0.0,
            # Model and provider information
            "model_name": model_config.name.value,
            "provider": model_config.provider.value,
            "key_provider": model_config.key_provider.value,
        }
    except Exception as e:
        logger.warning(f"Failed to get context properties for telemetry: {e}")
        # Return minimal fallback properties
        return {
            "model_name": model_config.name.value,
            "provider": model_config.provider.value,
            "key_provider": model_config.key_provider.value,
            "context_window_size": model_config.max_input_tokens,
        }


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
        estimated_tokens = await estimate_tokens_from_messages(messages, deps.llm_model)

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

            # Get context composition properties for before compaction
            context_props_before = await get_compaction_context_properties(
                messages, deps.llm_model
            )
            # Get context composition properties for after compaction
            context_props_after = await get_compaction_context_properties(
                compacted_messages, deps.llm_model
            )

            # Track persistent compaction event with context analysis
            track_event(
                "persistent_compaction_applied",
                {
                    # Basic compaction metrics
                    "messages_before": original_size,
                    "messages_after": compacted_size,
                    "tokens_before": estimated_tokens,
                    "reduction_percentage": round(reduction_pct, 2),
                    "agent_mode": deps.agent_mode.value
                    if hasattr(deps, "agent_mode") and deps.agent_mode
                    else "unknown",
                    # Context composition before compaction
                    "user_message_proportion_before": context_props_before.get(
                        "user_message_proportion", 0
                    ),
                    "assistant_message_proportion_before": context_props_before.get(
                        "assistant_message_proportion", 0
                    ),
                    "system_status_proportion_before": context_props_before.get(
                        "system_status_proportion", 0
                    ),
                    "tool_result_proportion_before": context_props_before.get(
                        "tool_result_proportion", 0
                    ),
                    # Context composition after compaction
                    "user_message_proportion_after": context_props_after.get(
                        "user_message_proportion", 0
                    ),
                    "assistant_message_proportion_after": context_props_after.get(
                        "assistant_message_proportion", 0
                    ),
                    "system_status_proportion_after": context_props_after.get(
                        "system_status_proportion", 0
                    ),
                    "tool_result_proportion_after": context_props_after.get(
                        "tool_result_proportion", 0
                    ),
                    # Context window metrics
                    "context_window_size": context_props_before.get("context_window_size", 0),
                    "context_window_usage_before": context_props_before.get(
                        "context_window_usage", 0
                    ),
                    "context_window_usage_after": context_props_after.get(
                        "context_window_usage", 0
                    ),
                    # Model and provider info
                    "model_name": context_props_before.get("model_name", "unknown"),
                    "provider": context_props_before.get("provider", "unknown"),
                    "key_provider": context_props_before.get("key_provider", "unknown"),
                },
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
