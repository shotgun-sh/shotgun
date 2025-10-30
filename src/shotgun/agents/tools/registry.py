"""Tool category registry using decorators for automatic registration.

This module provides a decorator-based system for categorizing tools used by agents.
Tools can be decorated with @tool_category to automatically register their category,
which is then used by the context analyzer to break down token usage by tool type.
"""

from collections.abc import Callable
from enum import StrEnum
from typing import TypeVar

import sentry_sdk

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


# Global registry mapping tool names to categories
_TOOL_REGISTRY: dict[str, ToolCategory] = {}


def tool_category(category: ToolCategory) -> Callable[[F], F]:
    """Decorator to register a tool's category.

    Args:
        category: The ToolCategory enum value for this tool

    Returns:
        Decorator function that registers the tool and returns it unchanged

    Example:
        @tool_category(ToolCategory.CODEBASE_UNDERSTANDING)
        async def query_graph(ctx: RunContext[AgentDeps], query: str) -> str:
            ...
    """

    def decorator(func: F) -> F:
        tool_name = func.__name__
        _TOOL_REGISTRY[tool_name] = category
        logger.debug(f"Registered tool '{tool_name}' as category '{category.value}'")
        return func

    return decorator


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


# Register special tools that don't have decorators
register_special_tool("final_result", ToolCategory.AGENT_RESPONSE)
