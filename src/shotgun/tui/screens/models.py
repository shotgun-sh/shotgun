"""Models and enums for TUI screens."""

from enum import StrEnum


class LockedDialogAction(StrEnum):
    """Actions available in the database locked dialog."""

    RETRY = "retry"
    DELETE = "delete"
    QUIT = "quit"
