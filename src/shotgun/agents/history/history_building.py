"""Functions for building compacted message history."""

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelRequestPart,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)

from .message_utils import (
    get_first_user_request,
    get_last_user_request,
    get_system_prompt,
    get_user_content_from_request,
)


def build_clean_compacted_history(
    summary_part: TextPart,
    all_messages: list[ModelMessage],
    last_summary_index: int | None = None,
) -> list[ModelMessage]:
    """Build a clean compacted history without preserving old verbose content.

    Args:
        summary_part: The marked summary part to include
        all_messages: Original message history
        last_summary_index: Index of the last summary (if any)

    Returns:
        Clean compacted message history
    """
    # Extract essential context from pre-summary messages (if any)
    system_prompt = ""
    first_user_prompt = ""

    if last_summary_index is not None and last_summary_index > 0:
        # Get system and first user from original conversation
        pre_summary_messages = all_messages[:last_summary_index]
        system_prompt = get_system_prompt(pre_summary_messages) or ""
        first_user_prompt = get_first_user_request(pre_summary_messages) or ""

    # Build the base structure
    compacted_messages: list[ModelMessage] = []

    # Add system/user context if it exists and is meaningful
    if system_prompt or first_user_prompt:
        compacted_messages.append(
            _create_base_request(system_prompt, first_user_prompt)
        )

    # Add the summary
    summary_message = ModelResponse(parts=[summary_part])
    compacted_messages.append(summary_message)

    # Ensure proper ending
    return ensure_ends_with_model_request(compacted_messages, all_messages)


def ensure_ends_with_model_request(
    compacted_messages: list[ModelMessage],
    original_messages: list[ModelMessage],
) -> list[ModelMessage]:
    """Ensure the message history ends with ModelRequest for PydanticAI compatibility."""
    last_user_request = get_last_user_request(original_messages)

    if not last_user_request:
        return compacted_messages

    # Check if we need to add the last request or restructure
    if compacted_messages and isinstance(compacted_messages[0], ModelRequest):
        first_request = compacted_messages[0]
        last_user_content = get_user_content_from_request(last_user_request)
        first_user_content = get_user_content_from_request(first_request)

        if last_user_content != first_user_content:
            # Different messages - append the last request
            compacted_messages.append(last_user_request)
        else:
            # Same message - restructure to end with ModelRequest
            if len(compacted_messages) >= 2:
                summary_message = compacted_messages[1]  # The summary
                compacted_messages = [summary_message, first_request]
    else:
        # No first request, just add the last one
        compacted_messages.append(last_user_request)

    return compacted_messages


def _create_base_request(system_prompt: str, user_prompt: str) -> ModelRequest:
    """Create the base ModelRequest with system and user prompts."""
    parts: list[ModelRequestPart] = []

    if system_prompt:
        parts.append(SystemPromptPart(content=system_prompt))

    if user_prompt:
        parts.append(UserPromptPart(content=user_prompt))

    return ModelRequest(parts=parts)
