"""Tool category registry for context analysis.

This module re-exports the tool registry functionality for backward compatibility.
The actual implementation is in shotgun.agents.tools.registry.
"""

from shotgun.agents.tools.registry import ToolCategory, get_tool_category

__all__ = ["ToolCategory", "get_tool_category"]
