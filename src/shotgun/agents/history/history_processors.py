"""History processors for managing conversation history in Shotgun agents."""

from typing import TYPE_CHECKING, Any, Protocol

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)

from shotgun.agents.config.models import shotgun_model_request
from shotgun.agents.models import AgentDeps
from shotgun.logging_config import get_logger
from shotgun.prompts import PromptLoader

from .constants import SUMMARY_MARKER, TOKEN_LIMIT_RATIO
from .context_extraction import extract_context_from_messages
from .history_building import ensure_ends_with_model_request
from .message_utils import (
    get_first_user_request,
    get_system_prompt,
)
from .token_estimation import (
    calculate_max_summarization_tokens as _calculate_max_summarization_tokens,
)
from .token_estimation import (
    estimate_post_summary_tokens,
    estimate_tokens_from_messages,
)

if TYPE_CHECKING:
    pass


class ContextProtocol(Protocol):
    """Protocol defining the interface needed by token_limit_compactor."""

    deps: AgentDeps
    usage: Any  # Optional usage information


logger = get_logger(__name__)

# Global prompt loader instance
prompt_loader = PromptLoader()


def is_summary_part(part: Any) -> bool:
    """Check if a message part is a compacted summary."""
    return isinstance(part, TextPart) and part.content.startswith(SUMMARY_MARKER)


def find_last_summary_index(messages: list[ModelMessage]) -> int | None:
    """Find the index of the last summary in the message history.

    Args:
        messages: List of messages in the conversation history
    Returns:
        Index of the last summary message, or None if no summary exists.
    """
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], ModelResponse):
            for part in messages[i].parts:
                if is_summary_part(part):
                    return i
    return None


def extract_summary_content(summary_part: Any) -> str:
    """Extract the summary content without the marker prefix."""
    if isinstance(summary_part, TextPart):
        return summary_part.content[len(SUMMARY_MARKER) :].strip()
    return ""


def create_marked_summary_part(summary_response: Any) -> TextPart:
    """Create a TextPart with the summary marker prefix.

    This consolidates the duplicate summary creation logic.
    """
    first_part = summary_response.parts[0]
    if isinstance(first_part, TextPart):
        summary_content = f"{SUMMARY_MARKER} {first_part.content}"
        return TextPart(content=summary_content)
    else:
        # Fallback in case the response part is not TextPart
        summary_content = f"{SUMMARY_MARKER} Summary content unavailable"
        return TextPart(content=summary_content)


def log_summarization_request(
    model: Any, max_tokens: int, prompt: str, context: str, request_type: str
) -> None:
    """Log detailed summarization request information.

    Consolidates duplicate logging patterns across the codebase.
    """
    logger.debug(f"{request_type} SUMMARIZATION REQUEST - Model: {model}")
    logger.debug(f"{request_type} SUMMARIZATION REQUEST - Max tokens: {max_tokens}")
    logger.debug(f"{request_type} SUMMARIZATION REQUEST - Instructions: {prompt}")
    logger.debug(f"{request_type} SUMMARIZATION REQUEST - Context: {context}")


def log_summarization_response(response: Any, request_type: str) -> None:
    """Log detailed summarization response information.

    Consolidates duplicate logging patterns across the codebase.
    """
    logger.debug(f"{request_type} SUMMARIZATION RESPONSE - Full response: {response}")
    logger.debug(
        f"{request_type} SUMMARIZATION RESPONSE - Content: "
        f"{response.parts[0] if response.parts else 'No content'}"
    )
    logger.debug(f"{request_type} SUMMARIZATION RESPONSE - Usage: {response.usage}")


# Use centralized calculate_max_summarization_tokens function
calculate_max_summarization_tokens = _calculate_max_summarization_tokens


async def token_limit_compactor(
    ctx: ContextProtocol,
    messages: list[ModelMessage],
) -> list[ModelMessage]:
    """Compact message history based on token limits with incremental processing.

    This incremental compactor prevents cascading summarization by:
    1. Preserving existing summaries
    2. Only processing NEW messages since the last summary
    3. Combining summaries incrementally
    4. Never re-processing already compacted content

    Args:
        ctx: Run context with usage information and dependencies
        messages: Current conversation history

    Returns:
        Compacted list of messages within token limits
    """
    # Extract dependencies from context
    deps = ctx.deps

    # Get token limit from model configuration
    model_max_tokens = deps.llm_model.max_input_tokens
    max_tokens = int(model_max_tokens * TOKEN_LIMIT_RATIO)

    # Find existing summaries to determine compaction strategy
    last_summary_index = find_last_summary_index(messages)

    if last_summary_index is not None:
        # Check if post-summary conversation exceeds threshold for incremental compaction
        post_summary_tokens = estimate_post_summary_tokens(
            messages, last_summary_index, deps.llm_model
        )
        post_summary_percentage = (
            (post_summary_tokens / max_tokens) * 100 if max_tokens > 0 else 0
        )

        logger.debug(
            f"Found existing summary at index {last_summary_index}. "
            f"Post-summary tokens: {post_summary_tokens}, threshold: {max_tokens}, "
            f"percentage: {post_summary_percentage:.2f}%%"
        )

        # Only do incremental compaction if post-summary conversation exceeds threshold
        if post_summary_tokens < max_tokens:
            logger.debug(
                f"Post-summary conversation under threshold ({post_summary_tokens} < {max_tokens}), "
                f"keeping all {len(messages)} messages"
            )
            return messages

        # INCREMENTAL COMPACTION: Process new messages since last summary
        logger.debug(
            "Post-summary conversation exceeds threshold, performing incremental compaction"
        )

        # Extract existing summary content
        summary_message = messages[last_summary_index]
        existing_summary_part = None
        for part in summary_message.parts:
            if is_summary_part(part):
                existing_summary_part = part
                break

        if not existing_summary_part:
            logger.warning(
                "Found summary index but no summary part, falling back to full compaction"
            )
            return await _full_compaction(deps, messages)

        existing_summary = extract_summary_content(existing_summary_part)

        # Get messages AFTER the last summary for incremental processing
        messages_to_process = messages[last_summary_index + 1 :]

        if not messages_to_process:
            logger.debug(
                "No new messages since last summary, returning existing history"
            )
            return messages

        # Extract context from new messages only
        new_context = extract_context_from_messages(messages_to_process)

        # Check if there's meaningful content (responses) to summarize
        has_meaningful_content = any(
            isinstance(msg, ModelResponse) for msg in messages_to_process
        )

        # If there are only user requests and no responses, no need to summarize
        if not has_meaningful_content or not new_context.strip():
            logger.debug(
                "No meaningful new content to summarize, returning existing history"
            )
            return messages

        # Use incremental summarization prompt with proper template variables
        try:
            incremental_prompt = prompt_loader.render(
                "history/incremental_summarization.j2",
                existing_summary=existing_summary,
                new_messages=new_context,
            )
        except Exception:
            # Fallback to regular summarization if incremental template doesn't exist yet
            logger.warning(
                "Incremental summarization template not found, using regular template"
            )
            incremental_prompt = prompt_loader.render("history/summarization.j2")
            # Combine existing and new context for fallback
            new_context = (
                f"EXISTING SUMMARY:\n{existing_summary}\n\nNEW MESSAGES:\n{new_context}"
            )

        # Create incremental summary
        request_messages: list[ModelMessage] = [
            ModelRequest.user_text_prompt(new_context, instructions=incremental_prompt)
        ]

        # Calculate optimal max_tokens for summarization
        max_tokens = calculate_max_summarization_tokens(
            deps.llm_model, request_messages
        )

        # Debug logging using shared utilities
        log_summarization_request(
            deps.llm_model, max_tokens, incremental_prompt, new_context, "INCREMENTAL"
        )

        # Use shotgun wrapper to ensure full token utilization
        summary_response = await shotgun_model_request(
            model_config=deps.llm_model,
            messages=request_messages,
            max_tokens=max_tokens,  # Use calculated optimal tokens for summarization
        )

        log_summarization_response(summary_response, "INCREMENTAL")

        # Calculate token reduction (from new messages only)
        new_tokens = len(new_context.split())  # Rough estimate
        summary_tokens = (
            summary_response.usage.output_tokens if summary_response.usage else 0
        )
        logger.debug(
            f"Incremental compaction: processed {len(messages_to_process)} new messages, "
            f"reduced ~{new_tokens} tokens to {summary_tokens} tokens"
        )

        # Build the new compacted history with the updated summary
        new_summary_part = create_marked_summary_part(summary_response)

        # Extract essential context from messages before the last summary (if any)
        system_prompt = ""
        first_user_prompt = ""
        if last_summary_index > 0:
            # Get system and first user from original conversation
            system_prompt = get_system_prompt(messages[:last_summary_index]) or ""
            first_user_prompt = (
                get_first_user_request(messages[:last_summary_index]) or ""
            )

        # Create the updated summary message
        updated_summary_message = ModelResponse(parts=[new_summary_part])

        # Build final compacted history with CLEAN structure
        compacted_messages: list[ModelMessage] = []

        # Only add system/user context if it exists and is meaningful
        if system_prompt or first_user_prompt:
            compacted_messages.append(
                ModelRequest(
                    parts=[
                        SystemPromptPart(content=system_prompt),
                        UserPromptPart(content=first_user_prompt),
                    ]
                )
            )

        # Add the summary
        compacted_messages.append(updated_summary_message)

        # Ensure history ends with ModelRequest for PydanticAI compatibility
        compacted_messages = ensure_ends_with_model_request(
            compacted_messages, messages
        )

        logger.debug(
            f"Incremental compaction complete: {len(messages)} -> {len(compacted_messages)} messages"
        )
        return compacted_messages

    else:
        # Check if total conversation exceeds threshold for full compaction
        total_tokens = estimate_tokens_from_messages(messages, deps.llm_model)
        total_percentage = (total_tokens / max_tokens) * 100 if max_tokens > 0 else 0

        logger.debug(
            f"No existing summary found. Total tokens: {total_tokens}, threshold: {max_tokens}, "
            f"percentage: {total_percentage:.2f}%%"
        )

        # Only do full compaction if total conversation exceeds threshold
        if total_tokens < max_tokens:
            logger.debug(
                f"Total conversation under threshold ({total_tokens} < {max_tokens}), "
                f"keeping all {len(messages)} messages"
            )
            return messages

        # FIRST-TIME COMPACTION: Process all messages
        logger.debug(
            "Total conversation exceeds threshold, performing initial full compaction"
        )
        return await _full_compaction(deps, messages)


async def _full_compaction(
    deps: AgentDeps,
    messages: list[ModelMessage],
) -> list[ModelMessage]:
    """Perform full compaction for first-time summarization."""
    # Extract context from all messages
    context = extract_context_from_messages(messages)

    # Use regular summarization prompt
    summarization_prompt = prompt_loader.render("history/summarization.j2")
    request_messages: list[ModelMessage] = [
        ModelRequest.user_text_prompt(context, instructions=summarization_prompt)
    ]

    # Calculate optimal max_tokens for summarization
    max_tokens = calculate_max_summarization_tokens(deps.llm_model, request_messages)

    # Debug logging using shared utilities
    log_summarization_request(
        deps.llm_model, max_tokens, summarization_prompt, context, "FULL"
    )

    # Use shotgun wrapper to ensure full token utilization
    summary_response = await shotgun_model_request(
        model_config=deps.llm_model,
        messages=request_messages,
        max_tokens=max_tokens,  # Use calculated optimal tokens for summarization
    )

    # Calculate token reduction
    current_tokens = estimate_tokens_from_messages(messages, deps.llm_model)
    summary_usage = summary_response.usage
    reduction_percentage = (
        ((current_tokens - summary_usage.output_tokens) / current_tokens) * 100
        if current_tokens > 0 and summary_usage
        else 0
    )

    log_summarization_response(summary_response, "FULL")

    # Log token reduction (already calculated above)
    logger.debug(
        "Full compaction: %s tokens -> %s tokens (%.2f%% reduction)",
        current_tokens,
        summary_usage.output_tokens if summary_usage else 0,
        reduction_percentage,
    )

    # Mark summary with special prefix
    marked_summary_part = create_marked_summary_part(summary_response)

    # Build compacted history structure
    system_prompt = get_system_prompt(messages) or ""
    user_prompt = get_first_user_request(messages) or ""

    # Create base structure
    compacted_messages: list[ModelMessage] = [
        ModelRequest(
            parts=[
                SystemPromptPart(content=system_prompt),
                UserPromptPart(content=user_prompt),
            ]
        ),
        ModelResponse(parts=[marked_summary_part]),
    ]

    # Ensure history ends with ModelRequest for PydanticAI compatibility
    compacted_messages = ensure_ends_with_model_request(compacted_messages, messages)

    return compacted_messages
