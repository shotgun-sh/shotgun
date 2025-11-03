"""Processing state management for TUI operations.

This module provides centralized management of processing state including:
- Tracking whether operations are in progress
- Managing worker references for cancellation
- Coordinating spinner widget updates
- Providing clean cancellation API
"""

from typing import TYPE_CHECKING, Any

from shotgun.logging_config import get_logger
from shotgun.posthog_telemetry import track_event

if TYPE_CHECKING:
    from textual.screen import Screen
    from textual.worker import Worker

    from shotgun.tui.components.spinner import Spinner

logger = get_logger(__name__)


class ProcessingStateManager:
    """Manages processing state and spinner coordination for async operations.

    This class centralizes the logic for tracking whether the TUI is processing
    an operation, managing the current worker for cancellation, and updating
    spinner text.

    Example:
        ```python
        # In ChatScreen
        self.processing_state = ProcessingStateManager(self)

        # Start processing
        @work
        async def some_operation(self) -> None:
            self.processing_state.start_processing("Doing work...")
            self.processing_state.bind_worker(get_current_worker())
            try:
                # ... do work ...
            finally:
                self.processing_state.stop_processing()
        ```
    """

    def __init__(
        self, screen: "Screen[Any]", telemetry_context: dict[str, Any] | None = None
    ) -> None:
        """Initialize the processing state manager.

        Args:
            screen: The Textual screen this manager is attached to
            telemetry_context: Optional context to include in telemetry events
                (e.g., {"agent_mode": "research"})
        """
        self.screen = screen
        self._working = False
        self._current_worker: Worker[Any] | None = None
        self._spinner_widget: Spinner | None = None
        self._default_spinner_text = "Processing..."
        self._telemetry_context = telemetry_context or {}

    @property
    def is_working(self) -> bool:
        """Check if an operation is currently in progress.

        Returns:
            True if processing, False if idle
        """
        return self._working

    def bind_spinner(self, spinner: "Spinner") -> None:
        """Bind a spinner widget for state coordination.

        Should be called during screen mount after the spinner widget is available.

        Args:
            spinner: The Spinner widget to coordinate with
        """
        self._spinner_widget = spinner
        logger.debug(f"Spinner widget bound: {spinner}")

    def start_processing(self, spinner_text: str | None = None) -> None:
        """Start processing state with optional custom spinner text.

        Args:
            spinner_text: Custom text to display in spinner. If None, uses default.
        """
        if self._working:
            logger.warning("Attempted to start processing while already processing")
            return

        self._working = True
        text = spinner_text or self._default_spinner_text

        # Update screen's reactive working state
        if hasattr(self.screen, "working"):
            self.screen.working = True

        if self._spinner_widget:
            self._spinner_widget.text = text
            logger.debug(f"Processing started with spinner text: {text}")
        else:
            logger.warning("Processing started but no spinner widget bound")

    def stop_processing(self) -> None:
        """Stop processing state and reset to default."""
        if not self._working:
            logger.debug("stop_processing called when not working (no-op)")
            return

        self._working = False
        self._current_worker = None

        # Update screen's reactive working state
        if hasattr(self.screen, "working"):
            self.screen.working = False

        # Reset spinner to default text
        if self._spinner_widget:
            self._spinner_widget.text = self._default_spinner_text
            logger.debug("Processing stopped, spinner reset to default")

    def bind_worker(self, worker: "Worker[Any]") -> None:
        """Bind a worker for cancellation tracking.

        Should be called immediately after starting a @work decorated method
        using get_current_worker().

        Args:
            worker: The Worker instance to track for cancellation
        """
        self._current_worker = worker
        logger.debug(f"Worker bound: {worker}")

    def cancel_current_operation(self, cancel_key: str | None = None) -> bool:
        """Attempt to cancel the current operation if one is running.

        Automatically tracks cancellation telemetry with context from initialization.

        Args:
            cancel_key: Optional key that triggered cancellation (e.g., "Escape")

        Returns:
            True if an operation was cancelled, False if no operation was running
        """
        if not self._working or not self._current_worker:
            logger.debug("No operation to cancel")
            return False

        try:
            self._current_worker.cancel()
            logger.info("Operation cancelled successfully")

            # Track cancellation event with context
            event_data = {**self._telemetry_context}
            if cancel_key:
                event_data["cancel_key"] = cancel_key

            track_event("agent_cancelled", event_data)

            return True
        except Exception as e:
            logger.error(f"Failed to cancel operation: {e}", exc_info=True)
            return False

    def update_spinner_text(self, text: str) -> None:
        """Update spinner text during processing.

        Args:
            text: New text to display in spinner
        """
        if not self._working:
            logger.warning(
                f"Attempted to update spinner text while not working: {text}"
            )
            return

        if self._spinner_widget:
            self._spinner_widget.text = text
            logger.debug(f"Spinner text updated to: {text}")
        else:
            logger.warning(f"Cannot update spinner text, widget not bound: {text}")
