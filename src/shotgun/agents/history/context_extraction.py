"""Context extraction utilities for history processing."""

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


def extract_context_from_messages(messages: list[ModelMessage]) -> str:
    """Extract context from a list of messages for summarization."""
    context = ""
    for msg in messages:
        if isinstance(msg, ModelResponse | ModelRequest):
            for part in msg.parts:
                message_content = extract_context_from_part(part)
                if message_content:
                    context += message_content + "\n"
    return context


def extract_context_from_message_range(
    messages: list[ModelMessage],
    start_index: int,
    end_index: int | None = None,
) -> str:
    """Extract context from a specific range of messages."""
    if end_index is None:
        end_index = len(messages)

    message_slice = messages[start_index:end_index]
    return extract_context_from_messages(message_slice)


def has_meaningful_content(messages: list[ModelMessage]) -> bool:
    """Check if messages contain meaningful content worth summarizing.

    Only ModelResponse messages are considered meaningful for summarization.
    User requests alone don't need summarization.
    """
    for msg in messages:
        if isinstance(msg, ModelResponse):
            for part in msg.parts:
                if extract_context_from_part(part):
                    return True
    return False


def extract_context_from_part(
    message_part: (
        SystemPromptPart
        | UserPromptPart
        | ToolReturnPart
        | RetryPromptPart
        | ModelResponsePart
    ),
) -> str:
    """Extract context from a single message part."""
    if isinstance(message_part, SystemPromptPart):
        return ""  # Exclude system prompts from summary

    elif isinstance(message_part, UserPromptPart):
        if isinstance(message_part.content, str):
            return f"<USER_PROMPT>\n{message_part.content}\n</USER_PROMPT>"
        return ""

    elif isinstance(message_part, ToolReturnPart):
        return f"<TOOL_RETURN>\n{str(message_part.content)}\n</TOOL_RETURN>"

    elif isinstance(message_part, RetryPromptPart):
        if isinstance(message_part.content, str):
            return f"<RETRY_PROMPT>\n{message_part.content}\n</RETRY_PROMPT>"
        return ""

    # Handle ModelResponsePart types
    elif isinstance(message_part, TextPart):
        return f"<ASSISTANT_TEXT>\n{message_part.content}\n</ASSISTANT_TEXT>"

    elif isinstance(message_part, ToolCallPart):
        if isinstance(message_part.args, dict):
            args_str = ", ".join(f"{k}={repr(v)}" for k, v in message_part.args.items())
            tool_call_str = f"{message_part.tool_name}({args_str})"
        else:
            tool_call_str = f"{message_part.tool_name}({message_part.args})"
        return f"<TOOL_CALL>\n{tool_call_str}\n</TOOL_CALL>"

    elif isinstance(message_part, BuiltinToolCallPart):
        return f"<BUILTIN_TOOL_CALL>\n{message_part.tool_name}\n</BUILTIN_TOOL_CALL>"

    elif isinstance(message_part, BuiltinToolReturnPart):
        return (
            f"<BUILTIN_TOOL_RETURN>\n{message_part.tool_name}\n</BUILTIN_TOOL_RETURN>"
        )

    elif isinstance(message_part, ThinkingPart):
        return f"<THINKING>\n{message_part.content}\n</THINKING>"

    return ""
