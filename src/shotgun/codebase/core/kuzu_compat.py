"""Lazy import wrapper for kuzu (real_ladybug) with Windows compatibility handling."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import real_ladybug as kuzu

_kuzu_module: Any = None
_import_error: ImportError | None = None


class KuzuImportError(ImportError):
    """Raised when kuzu cannot be imported, typically on Windows due to DLL issues."""

    def __init__(self, original_error: ImportError) -> None:
        self.original_error = original_error
        if sys.platform == "win32":
            message = (
                "Failed to load the graph database library (real_ladybug).\n\n"
                "This is a known issue on Windows. The codebase indexing feature "
                "is not yet available on Windows.\n\n"
                "You can still use shotgun for all other features.\n\n"
                f"Original error: {original_error}"
            )
        else:
            message = f"Failed to import real_ladybug: {original_error}"
        super().__init__(message)


def get_kuzu() -> Any:
    """Get the kuzu module, importing it lazily on first use.

    Raises:
        KuzuImportError: If kuzu cannot be imported (e.g., Windows DLL issues)

    Returns:
        The real_ladybug module
    """
    global _kuzu_module, _import_error

    if _kuzu_module is not None:
        return _kuzu_module

    if _import_error is not None:
        raise KuzuImportError(_import_error)

    try:
        import real_ladybug

        _kuzu_module = real_ladybug
        return _kuzu_module
    except ImportError as e:
        _import_error = e
        raise KuzuImportError(e) from e


def is_kuzu_available() -> bool:
    """Check if kuzu is available without raising an error.

    Returns:
        True if kuzu can be imported, False otherwise
    """
    try:
        get_kuzu()
        return True
    except KuzuImportError:
        return False
