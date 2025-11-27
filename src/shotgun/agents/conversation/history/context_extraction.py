"""Context extraction utilities for history processing."""

import json
import logging
import traceback

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

logger = logging.getLogger(__name__)


def _safely_parse_tool_args(args: dict[str, object] | str | None) -> dict[str, object]:
    """Safely parse tool call arguments, handling incomplete/invalid JSON.

    Args:
        args: Tool call arguments (dict, JSON string, or None)

    Returns:
        Parsed args dict, or empty dict if parsing fails
    """
    if args is None:
        return {}

    if isinstance(args, dict):
        return args

    if not isinstance(args, str):
        return {}

    try:
        parsed = json.loads(args)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, ValueError) as e:
        # Only log warning if it looks like JSON (starts with { or [) - incomplete JSON
        # Plain strings are valid args and shouldn't trigger warnings
        stripped_args = args.strip()
        if stripped_args.startswith(("{", "[")):
            args_preview = args[:100] + "..." if len(args) > 100 else args
            logger.warning(
                "Detected incomplete/invalid JSON in tool call args during parsing",
                extra={
                    "args_preview": args_preview,
                    "error": str(e),
                    "args_length": len(args),
                },
            )
        return {}


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
        # Safely parse args to avoid crashes from incomplete JSON during streaming
        try:
            parsed_args = _safely_parse_tool_args(message_part.args)
            if parsed_args:
                # Successfully parsed as dict - format nicely
                args_str = ", ".join(f"{k}={repr(v)}" for k, v in parsed_args.items())
                tool_call_str = f"{message_part.tool_name}({args_str})"
            elif isinstance(message_part.args, str) and message_part.args:
                # Non-empty string that didn't parse as JSON
                # Check if it looks like JSON (starts with { or [) - if so, it's incomplete
                stripped_args = message_part.args.strip()
                if stripped_args.startswith(("{", "[")):
                    # Looks like incomplete JSON - log warning and show empty parens
                    args_preview = (
                        stripped_args[:100] + "..."
                        if len(stripped_args) > 100
                        else stripped_args
                    )
                    stack_trace = "".join(traceback.format_stack())
                    logger.warning(
                        "ToolCallPart with unparseable args encountered during context extraction",
                        extra={
                            "tool_name": message_part.tool_name,
                            "tool_call_id": message_part.tool_call_id,
                            "args_preview": args_preview,
                            "args_type": type(message_part.args).__name__,
                            "stack_trace": stack_trace,
                        },
                    )
                    tool_call_str = f"{message_part.tool_name}()"
                else:
                    # Plain string arg - display as-is
                    tool_call_str = f"{message_part.tool_name}({message_part.args})"
            else:
                # No args
                tool_call_str = f"{message_part.tool_name}()"
            return f"<TOOL_CALL>\n{tool_call_str}\n</TOOL_CALL>"
        except Exception as e:  # pragma: no cover - defensive catch-all
            # If anything goes wrong, log full exception with stack trace
            logger.error(
                "Unexpected error processing ToolCallPart",
                exc_info=True,
                extra={
                    "tool_name": message_part.tool_name,
                    "tool_call_id": message_part.tool_call_id,
                    "error": str(e),
                },
            )
            return f"<TOOL_CALL>\n{message_part.tool_name}()\n</TOOL_CALL>"

    elif isinstance(message_part, BuiltinToolCallPart):
        return f"<BUILTIN_TOOL_CALL>\n{message_part.tool_name}\n</BUILTIN_TOOL_CALL>"

    elif isinstance(message_part, BuiltinToolReturnPart):
        return (
            f"<BUILTIN_TOOL_RETURN>\n{message_part.tool_name}\n</BUILTIN_TOOL_RETURN>"
        )

    elif isinstance(message_part, ThinkingPart):
        return f"<THINKING>\n{message_part.content}\n</THINKING>"

    return ""
