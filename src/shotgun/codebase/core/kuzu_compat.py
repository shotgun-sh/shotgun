"""Lazy import wrapper for kuzu (real_ladybug) with Windows compatibility handling."""

from __future__ import annotations

import sys
from typing import Any

_kuzu_module: Any = None
_import_error: ImportError | None = None

# Windows VC++ download URL
_VC_REDIST_URL = "https://aka.ms/vs/17/release/vc_redist.x64.exe"

# Windows VC++ installation instructions
_WINDOWS_INSTALL_INSTRUCTIONS = f"""
To fix this, install the Visual C++ Redistributable:

1. Download from: {_VC_REDIST_URL}
2. Run the installer and follow the prompts
3. Restart your terminal and try again

Or run this PowerShell command (as Administrator):
  Invoke-WebRequest -Uri "{_VC_REDIST_URL}" -OutFile "$env:TEMP\\vc_redist.x64.exe"
  Start-Process -FilePath "$env:TEMP\\vc_redist.x64.exe" -ArgumentList "/install", "/quiet", "/norestart" -Wait
"""


def copy_vcpp_instructions_to_clipboard() -> bool:
    """Copy the VC++ Redistributable download URL to clipboard.

    Returns:
        True if successful, False otherwise
    """
    try:
        import pyperclip  # type: ignore[import-untyped]

        pyperclip.copy(_VC_REDIST_URL)
        return True
    except Exception:
        return False


class KuzuImportError(ImportError):
    """Raised when kuzu cannot be imported, typically on Windows due to DLL issues."""

    def __init__(self, original_error: ImportError) -> None:
        self.original_error = original_error
        if sys.platform == "win32":
            message = (
                "Failed to load the graph database library (real_ladybug).\n\n"
                "This error typically occurs on Windows when the Visual C++ "
                "Redistributable is not installed.\n"
                f"{_WINDOWS_INSTALL_INSTRUCTIONS}\n"
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
