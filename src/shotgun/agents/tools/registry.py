"""Tool category registry using decorators for automatic registration.

This module provides a decorator-based system for categorizing tools used by agents.
Tools can be decorated with @tool_category to automatically register their category,
which is then used by the context analyzer to break down token usage by tool type.

It also provides a display registry system for tool formatting in the TUI, allowing
tools to declare how they should be displayed when streaming.
"""

from collections.abc import Callable
from enum import StrEnum
from typing import TypeVar

import sentry_sdk
from pydantic import BaseModel

from shotgun.logging_config import get_logger

logger = get_logger(__name__)

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., object])


class ToolCategory(StrEnum):
    """Categories for agent tools used in context analysis."""

    CODEBASE_UNDERSTANDING = "codebase_understanding"
    ARTIFACT_MANAGEMENT = "artifact_management"
    WEB_RESEARCH = "web_research"
    AGENT_RESPONSE = "agent_response"
    UNKNOWN = "unknown"


class ToolDisplayConfig(BaseModel):
    """Configuration for how a tool should be displayed in the TUI.

    Attributes:
        display_template: Template string with {arg_name} placeholders for formatting
        fallback_text: Text to show when required args are missing
        key_arg: Primary argument to extract from tool args for display (optional)
        hide: Whether to completely hide this tool call from the UI
    """

    display_template: str
    fallback_text: str
    key_arg: str | None = None
    hide: bool = False


# Global registry mapping tool names to categories
_TOOL_REGISTRY: dict[str, ToolCategory] = {}

# Global registry mapping tool names to display configs
_TOOL_DISPLAY_REGISTRY: dict[str, ToolDisplayConfig] = {}


def tool_registry(
    category: ToolCategory,
    display_template: str | None = None,
    fallback_text: str | None = None,
    key_arg: str | None = None,
    hide: bool = False,
) -> Callable[[F], F]:
    """Decorator to register a tool's category and optional display configuration.

    Args:
        category: The ToolCategory enum value for this tool
        display_template: Optional template string with {arg_name} placeholders
        fallback_text: Optional text to show when required args are missing
        key_arg: Optional primary argument to extract for display
        hide: Whether to hide this tool call completely from the UI

    Returns:
        Decorator function that registers the tool and returns it unchanged

    Example:
        @tool_registry(
            ToolCategory.CODEBASE_UNDERSTANDING,
            display_template='Querying code: "{query}"',
            fallback_text="Querying code",
            key_arg="query"
        )
        async def query_graph(ctx: RunContext[AgentDeps], query: str) -> str:
            ...
    """

    def decorator(func: F) -> F:
        tool_name = func.__name__
        _TOOL_REGISTRY[tool_name] = category
        logger.debug(f"Registered tool '{tool_name}' as category '{category.value}'")

        # Register display config if provided
        if display_template is not None and fallback_text is not None:
            config = ToolDisplayConfig(
                display_template=display_template,
                fallback_text=fallback_text,
                key_arg=key_arg,
                hide=hide,
            )
            _TOOL_DISPLAY_REGISTRY[tool_name] = config
            logger.debug(f"Registered display config for tool '{tool_name}'")

        return func

    return decorator


# Backwards compatibility alias
tool_category = tool_registry


def get_tool_category(tool_name: str) -> ToolCategory:
    """Get category for a tool, logging unknown tools to Sentry.

    Args:
        tool_name: Name of the tool to look up

    Returns:
        ToolCategory enum value for the tool, or UNKNOWN if not registered
    """
    category = _TOOL_REGISTRY.get(tool_name)

    if category is None:
        logger.warning(f"Unknown tool encountered in context analysis: {tool_name}")
        sentry_sdk.capture_message(
            f"Unknown tool in context analysis: {tool_name}",
            level="warning",
            extras={"tool_name": tool_name},
        )
        return ToolCategory.UNKNOWN

    return category


def register_special_tool(tool_name: str, category: ToolCategory) -> None:
    """Register a special tool that doesn't have a decorator.

    Used for tools like 'final_result' that aren't actual Python functions
    but need to be categorized.

    Args:
        tool_name: Name of the special tool
        category: Category to assign to this tool
    """
    _TOOL_REGISTRY[tool_name] = category
    logger.debug(
        f"Registered special tool '{tool_name}' as category '{category.value}'"
    )


def tool_display(
    display_template: str,
    fallback_text: str,
    key_arg: str | None = None,
    hide: bool = False,
) -> Callable[[F], F]:
    """Decorator to register a tool's display configuration.

    Args:
        display_template: Template string with {arg_name} placeholders
        fallback_text: Text to show when required args are missing
        key_arg: Primary argument to extract for display (optional)
        hide: Whether to hide this tool call completely

    Returns:
        Decorator function that registers the display config and returns the function unchanged

    Example:
        @tool_display(
            display_template='Searching web: "{query}"',
            fallback_text="Searching web",
            key_arg="query"
        )
        async def web_search_tool(query: str) -> str:
            ...
    """

    def decorator(func: F) -> F:
        tool_name = func.__name__
        config = ToolDisplayConfig(
            display_template=display_template,
            fallback_text=fallback_text,
            key_arg=key_arg,
            hide=hide,
        )
        _TOOL_DISPLAY_REGISTRY[tool_name] = config
        logger.debug(f"Registered display config for tool '{tool_name}'")
        return func

    return decorator


def get_tool_display_config(tool_name: str) -> ToolDisplayConfig | None:
    """Get display configuration for a tool.

    Args:
        tool_name: Name of the tool to look up

    Returns:
        ToolDisplayConfig for the tool, or None if not registered
    """
    return _TOOL_DISPLAY_REGISTRY.get(tool_name)


def register_tool_display(
    tool_name: str,
    display_template: str,
    fallback_text: str,
    key_arg: str | None = None,
    hide: bool = False,
) -> None:
    """Register a display config for a special tool that doesn't have a decorator.

    Used for tools like 'final_result' or builtin tools that aren't actual Python functions.

    Args:
        tool_name: Name of the special tool
        display_template: Template string with {arg_name} placeholders
        fallback_text: Text to show when required args are missing
        key_arg: Primary argument to extract for display (optional)
        hide: Whether to hide this tool call completely
    """
    config = ToolDisplayConfig(
        display_template=display_template,
        fallback_text=fallback_text,
        key_arg=key_arg,
        hide=hide,
    )
    _TOOL_DISPLAY_REGISTRY[tool_name] = config
    logger.debug(f"Registered display config for special tool '{tool_name}'")


# Register special tools that don't have decorators
register_special_tool("final_result", ToolCategory.AGENT_RESPONSE)
register_tool_display("final_result", "", "", hide=True)

# Register builtin tools (tools that come from Pydantic AI or model providers)
# These don't have Python function definitions but need display formatting
register_tool_display(
    "web_search",
    display_template='Searching: "{query}"',
    fallback_text="Searching",
    key_arg="query",
)
