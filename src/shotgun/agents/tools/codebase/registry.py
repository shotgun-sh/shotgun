"""Registry for codebase understanding tools."""

from collections.abc import Callable
from typing import Any

from .codebase_shell import codebase_shell
from .directory_lister import directory_lister
from .file_read import file_read
from .query_graph import query_graph
from .retrieve_code import retrieve_code


def get_codebase_tools() -> list[Callable[..., Any]]:
    """Get all codebase understanding tools.

    Returns:
        List of codebase understanding tool functions
    """
    return [
        query_graph,
        retrieve_code,
        file_read,
        directory_lister,
        codebase_shell,
    ]
