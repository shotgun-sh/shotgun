"""Protocol definitions for TUI components.

These protocols define interfaces that components can depend on without
creating circular imports. Screens like ChatScreen can satisfy these
protocols without explicitly implementing them.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class QAStateProvider(Protocol):
    """Protocol for screens that provide Q&A mode state.

    This protocol allows components to check if they're on a screen with
    Q&A mode without importing the concrete ChatScreen class, eliminating
    circular dependencies.
    """

    @property
    def qa_mode(self) -> bool:
        """Whether Q&A mode is currently active.

        Returns:
            True if Q&A mode is active, False otherwise.
        """
        ...


@runtime_checkable
class ProcessingStateProvider(Protocol):
    """Protocol for screens that provide processing state.

    This protocol allows components to check if they're on a screen with
    an active agent processing without importing the concrete ChatScreen class.
    """

    @property
    def working(self) -> bool:
        """Whether an agent is currently working.

        Returns:
            True if an agent is processing, False otherwise.
        """
        ...
