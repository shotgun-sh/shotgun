"""Tools package for Pydantic AI agents."""

from .codebase import (
    codebase_shell,
    directory_lister,
    file_read,
    query_graph,
    retrieve_code,
)
from .file_management import append_file, read_file, write_file
from .markdown_tools import (
    insert_markdown_section,
    remove_markdown_section,
    replace_markdown_section,
)
from .mermaid_validation import validate_mermaid, validate_mermaid_in_content
from .web_search import (
    anthropic_web_search_tool,
    gemini_web_search_tool,
    get_available_web_search_tools,
    openai_web_search_tool,
)

__all__ = [
    "openai_web_search_tool",
    "anthropic_web_search_tool",
    "gemini_web_search_tool",
    "get_available_web_search_tools",
    "read_file",
    "write_file",
    "append_file",
    # Mermaid validation tools
    "validate_mermaid",
    "validate_mermaid_in_content",
    "replace_markdown_section",
    "insert_markdown_section",
    "remove_markdown_section",
    # Codebase understanding tools
    "query_graph",
    "retrieve_code",
    "file_read",
    "directory_lister",
    "codebase_shell",
]
