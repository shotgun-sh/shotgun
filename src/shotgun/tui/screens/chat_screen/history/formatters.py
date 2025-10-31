"""Tool formatting utilities for chat history display."""

import json

from pydantic_ai.messages import BuiltinToolCallPart, ToolCallPart

from shotgun.agents.tools.registry import get_tool_display_config


class ToolFormatter:
    """Formats tool calls for display in the TUI."""

    @staticmethod
    def truncate(text: str, max_length: int = 100) -> str:
        """Truncate text to max_length characters, adding ellipsis if needed."""
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."

    @staticmethod
    def parse_args(args: dict[str, object] | str | None) -> dict[str, object]:
        """Parse tool call arguments, handling both dict and JSON string formats."""
        if args is None:
            return {}
        if isinstance(args, str):
            try:
                return json.loads(args) if args.strip() else {}
            except json.JSONDecodeError:
                return {}
        return args if isinstance(args, dict) else {}

    @classmethod
    def format_tool_call_part(cls, part: ToolCallPart) -> str:
        """Format a tool call part using the tool display registry."""
        # Look up the display config for this tool
        display_config = get_tool_display_config(part.tool_name)

        if display_config:
            # Tool is registered - use its display config
            if display_config.hide:
                return ""

            # Parse args
            args = cls.parse_args(part.args)

            # Get the key argument value
            if args and isinstance(args, dict) and display_config.key_arg in args:
                # Special handling for codebase_shell which needs command + args
                if part.tool_name == "codebase_shell" and "command" in args:
                    command = args.get("command", "")
                    cmd_args = args.get("args", [])
                    if isinstance(cmd_args, list):
                        args_str = " ".join(str(arg) for arg in cmd_args)
                    else:
                        args_str = ""
                    key_value = f"{command} {args_str}".strip()
                else:
                    key_value = str(args[display_config.key_arg])

                # Format: "display_text: key_value"
                return f"{display_config.display_text}: {cls.truncate(key_value)}"
            else:
                # No key arg value available - show just display_text
                return display_config.display_text

        # Tool not registered - use fallback formatting
        args = cls.parse_args(part.args)
        if args and isinstance(args, dict):
            # Try to extract common fields
            if "query" in args:
                return f"{part.tool_name}: {cls.truncate(str(args['query']))}"
            elif "question" in args:
                return f"{part.tool_name}: {cls.truncate(str(args['question']))}"
            elif "filename" in args:
                return f"{part.tool_name}: {args['filename']}"
            else:
                # Show tool name with truncated args
                args_str = (
                    str(part.args)[:50] + "..."
                    if len(str(part.args)) > 50
                    else str(part.args)
                )
                return f"{part.tool_name}({args_str})"
        else:
            return f"{part.tool_name}()"

    @classmethod
    def format_builtin_tool_call(cls, part: BuiltinToolCallPart) -> str:
        """Format a builtin tool call part using the tool display registry."""
        display_config = get_tool_display_config(part.tool_name or "")

        if display_config:
            if display_config.hide:
                return ""

            args = cls.parse_args(part.args)
            # Get the key argument value
            if args and isinstance(args, dict) and display_config.key_arg in args:
                key_value = str(args[display_config.key_arg])
                # Format: "display_text: key_value"
                return f"{display_config.display_text}: {cls.truncate(key_value)}"
            else:
                # No key arg value available - show just display_text
                return display_config.display_text
        else:
            # Fallback for unregistered builtin tools
            if part.args:
                args_str = (
                    str(part.args)[:50] + "..."
                    if len(str(part.args)) > 50
                    else str(part.args)
                )
                return f"{part.tool_name}({args_str})"
            else:
                return f"{part.tool_name}()"
