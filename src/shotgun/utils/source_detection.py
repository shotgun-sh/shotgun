"""Utility for detecting the source of function calls (CLI vs TUI)."""

import inspect


def detect_source() -> str:
    """Detect if the call originated from CLI or TUI by inspecting the call stack.

    Returns:
        "tui" if any frame in the call stack contains "tui" in the filename,
        "cli" otherwise.
    """
    for frame_info in inspect.stack():
        if "tui" in frame_info.filename.lower():
            return "tui"
    return "cli"
