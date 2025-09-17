"""History processors for managing conversation history in Shotgun agents."""

from pydantic_ai import RunContext
from pydantic_ai.direct import model_request
from pydantic_ai.messages import (
    BuiltinToolCallPart,
    BuiltinToolReturnPart,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelResponsePart,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from shotgun.agents.models import AgentDeps
from shotgun.logging_config import get_logger
from shotgun.prompts import PromptLoader

logger = get_logger(__name__)

# Global prompt loader instance
prompt_loader = PromptLoader()


async def token_limit_compactor(
    ctx: RunContext[AgentDeps],
    messages: list[ModelMessage],
) -> list[ModelMessage]:
    """Compact message history based on token limits.

    This context-aware processor monitors token usage and removes older messages
    when the conversation history becomes too large. It preserves system messages
    and recent context while removing older user/assistant exchanges.

    Args:
        ctx: Run context with usage information and dependencies
        messages: List of messages in the conversation history

    Returns:
        Compacted list of messages within token limits
    """
    # Get current token usage from context
    current_tokens = ctx.usage.total_tokens if ctx.usage else 0

    # Get token limit from model configuration or use fallback
    model_max_tokens = ctx.deps.llm_model.max_input_tokens
    max_tokens = int(
        model_max_tokens * 0.8
    )  # Use 80% of max to leave room for response
    percentage_of_limit_used = (
        (current_tokens / max_tokens) * 100 if max_tokens > 0 else 0
    )
    logger.debug(
        "History compactor: current tokens=%d, limit=%d, percentage used=%.2f%%",
        current_tokens,
        max_tokens,
        percentage_of_limit_used,
    )

    # If we're under the limit, return all messages
    if current_tokens < max_tokens:
        logger.debug("Under token limit, keeping all %d messages", len(messages))
        return messages

    # Get current token usage from context
    current_tokens = ctx.usage.total_tokens if ctx.usage else 0

    context = ""

    # Separate system messages from conversation messages
    for msg in messages:
        if isinstance(msg, ModelResponse) or isinstance(msg, ModelRequest):
            for part in msg.parts:
                message_content = get_context_from_message(part)
                if not message_content:
                    continue
                context += get_context_from_message(part) + "\n"
        else:
            # Handle whatever this is
            pass

    summarization_prompt = prompt_loader.render("history/summarization.j2")
    summary_response = await model_request(
        model=ctx.model,
        messages=[
            ModelRequest.user_text_prompt(context, instructions=summarization_prompt)
        ],
    )
    # Usage before and after
    summary_usage = summary_response.usage
    reduction_percentage = (
        (current_tokens - summary_usage.output_tokens) / current_tokens
    ) * 100
    logger.debug(
        "Compacted %s tokens into %s tokens for a %.2f percent reduction",
        current_tokens,
        summary_usage.output_tokens,
        reduction_percentage,
    )

    system_prompt = get_system_promt(messages) or ""
    user_prompt = get_first_user_request(messages) or ""
    # Extract content from the first response part safely
    summarization_part = summary_response.parts[0]
    return [
        ModelRequest(
            parts=[
                SystemPromptPart(content=system_prompt),
                UserPromptPart(content=user_prompt),
            ]
        ),
        ModelResponse(
            parts=[
                summarization_part,
            ]
        ),
    ]


def get_first_user_request(messages: list[ModelMessage]) -> str | None:
    """Extract first user request from messages.

    Args:
        messages: List of messages in the conversation history
    Returns:
        The first user request as a string.
    """
    for msg in messages:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, UserPromptPart):
                    if isinstance(part.content, str):
                        return part.content
    return None


def get_system_promt(messages: list[ModelMessage]) -> str | None:
    """Extract system prompt from messages.

    Args:
        messages: List of messages in the conversation history

    Returns:
        The system prompt as a string.
    """
    for msg in messages:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, SystemPromptPart):
                    return part.content
    return None


def get_context_from_message(
    message_part: SystemPromptPart
    | UserPromptPart
    | ToolReturnPart
    | RetryPromptPart
    | ModelResponsePart,
) -> str:
    """Extract context from a message part.

    Args:
        message: The message part to extract context from.

    Returns:
        The extracted context as a string.
    """

    if isinstance(message_part, SystemPromptPart):
        return ""  # We do not include system prompts in the summary
    elif isinstance(message_part, UserPromptPart):
        if isinstance(message_part.content, str):
            return "<USER_PROMPT>\n" + message_part.content + "\n</USER_PROMPT>"
        else:
            return ""
    elif isinstance(message_part, ToolReturnPart):
        return "<TOOL_RETURN>\n" + str(message_part.content) + "\n</TOOL_RETURN>"
    elif isinstance(message_part, RetryPromptPart):
        if isinstance(message_part.content, str):
            return "<RETRY_PROMPT>\n" + message_part.content + "\n</RETRY_PROMPT>"
        return ""

    # TextPart | ToolCallPart | BuiltinToolCallPart | BuiltinToolReturnPart | ThinkingPart
    if isinstance(message_part, TextPart):
        return "<ASSISTANT_TEXT>\n" + message_part.content + "\n</ASSISTANT_TEXT>"
    elif isinstance(message_part, ToolCallPart):
        if isinstance(message_part.args, dict):
            args_str = ", ".join(f"{k}={repr(v)}" for k, v in message_part.args.items())
            tool_call_str = f"{message_part.tool_name}({args_str})"
        else:
            tool_call_str = f"{message_part.tool_name}({message_part.args})"
        return "<TOOL_CALL>\n" + tool_call_str + "\n</TOOL_CALL>"
    elif isinstance(message_part, BuiltinToolCallPart):
        return (
            "<BUILTIN_TOOL_CALL>\n" + message_part.tool_name + "\n</BUILTIN_TOOL_CALL>"
        )
    elif isinstance(message_part, BuiltinToolReturnPart):
        return (
            "<BUILTIN_TOOL_RETURN>\n"
            + message_part.tool_name
            + "\n</BUILTIN_TOOL_RETURN>"
        )
    elif isinstance(message_part, ThinkingPart):
        return "<THINKING>\n" + message_part.content + "\n</THINKING>"

    return ""
