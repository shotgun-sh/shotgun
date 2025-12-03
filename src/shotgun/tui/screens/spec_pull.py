"""Screen showing download progress for pulling specs."""

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.events import Resize
from textual.screen import ModalScreen
from textual.widgets import Button, Label, ProgressBar, Static
from textual.worker import Worker, get_current_worker

from shotgun.cli.spec.models import PullSource
from shotgun.cli.spec.pull_service import (
    CancelledError,
    PullProgress,
    SpecPullService,
)
from shotgun.logging_config import get_logger
from shotgun.shotgun_web.exceptions import (
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)
from shotgun.tui.layout import COMPACT_HEIGHT_THRESHOLD
from shotgun.utils.file_system_utils import get_shotgun_base_path

logger = get_logger(__name__)


class SpecPullScreen(ModalScreen[bool]):
    """Screen to pull a spec version with progress display.

    Returns True if pull was successful, False otherwise.
    """

    DEFAULT_CSS = """
        SpecPullScreen {
            align: center middle;
            background: rgba(0, 0, 0, 0.0);
        }

        SpecPullScreen > #dialog-container {
            width: 80%;
            max-width: 90;
            height: auto;
            border: wide $primary;
            padding: 1 2;
            layout: vertical;
            background: $surface;
        }

        #dialog-title {
            text-style: bold;
            color: $text-accent;
            padding-bottom: 1;
            text-align: center;
        }

        #phase-label {
            padding: 0;
        }

        #progress-bar {
            width: 100%;
            padding: 0;
        }

        #file-label {
            color: $text-muted;
        }

        #error-label {
            color: $error;
        }

        #success-label {
            color: $success;
            text-style: bold;
        }

        #dialog-buttons {
            layout: horizontal;
            align-horizontal: center;
            height: auto;
        }

        #dialog-buttons Button {
            margin: 0 1;
        }

        /* Hide elements initially */
        #success-label {
            display: none;
        }

        #error-label {
            display: none;
        }

        /* Compact styles for short terminals */
        SpecPullScreen.compact #dialog-container {
            padding: 0 2;
            max-height: 98%;
        }

        SpecPullScreen.compact #dialog-title {
            padding-bottom: 0;
        }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, version_id: str) -> None:
        """Initialize the screen.

        Args:
            version_id: Version UUID to pull.
        """
        super().__init__()
        self.version_id = version_id
        self._success = False
        self._download_worker: Worker[None] | None = None
        self._cancelled = False

    def compose(self) -> ComposeResult:
        """Compose the screen widgets."""
        with Container(id="dialog-container"):
            yield Label("Pulling spec from cloud", id="dialog-title")

            # Progress section
            yield Static("Fetching version info...", id="phase-label")
            yield ProgressBar(total=100, id="progress-bar")
            yield Static("", id="file-label")

            # Error section (hidden by default)
            yield Static("", id="error-label")

            # Success section (hidden by default)
            yield Static("Spec pulled successfully!", id="success-label")

            # Buttons
            with Horizontal(id="dialog-buttons"):
                yield Button("Cancel", id="cancel-btn")
                yield Button("Continue", variant="primary", id="done-btn")

    def on_mount(self) -> None:
        """Start the download when screen is mounted."""
        # Hide done button initially
        self.query_one("#done-btn", Button).display = False

        # Apply compact layout if starting in a short terminal
        self._apply_compact_layout(self.app.size.height < COMPACT_HEIGHT_THRESHOLD)

        # Start the download
        self._start_download()

    @on(Resize)
    def handle_resize(self, event: Resize) -> None:
        """Adjust layout based on terminal height."""
        self._apply_compact_layout(event.size.height < COMPACT_HEIGHT_THRESHOLD)

    def _apply_compact_layout(self, compact: bool) -> None:
        """Apply or remove compact layout class for short terminals."""
        if compact:
            self.add_class("compact")
        else:
            self.remove_class("compact")

    @work(exclusive=True)
    async def _start_download(self) -> None:
        """Run the download pipeline."""
        worker = get_current_worker()
        self._download_worker = worker

        shotgun_dir = get_shotgun_base_path()
        service = SpecPullService()

        def on_progress(p: PullProgress) -> None:
            pct = 0.0
            if p.total_files and p.file_index is not None:
                pct = ((p.file_index + 1) / p.total_files) * 100
            self._update_phase(p.phase, progress=pct, current_file=p.current_file)

        try:
            result = await service.pull_version(
                version_id=self.version_id,
                shotgun_dir=shotgun_dir,
                on_progress=on_progress,
                is_cancelled=lambda: worker.is_cancelled,
                source=PullSource.TUI,
            )

            if result.success:
                self._update_title(f"Pulled: {result.spec_name}")
                self._success = True
                self._show_success()
            else:
                self._show_error(result.error or "Unknown error")

        except CancelledError:
            self._cancelled = True
            self._show_cancelled()
        except UnauthorizedError:
            self._show_error("Not authenticated. Please try again.")
        except NotFoundError:
            self._show_error(f"Version not found: {self.version_id}")
        except ForbiddenError:
            self._show_error("You don't have access to this spec.")
        except Exception as e:
            logger.exception(f"Download failed: {type(e).__name__}: {e}")
            error_msg = str(e) if str(e) else type(e).__name__
            self._show_error(error_msg)

    def _update_title(self, title: str) -> None:
        """Update the dialog title."""
        self.query_one("#dialog-title", Label).update(title)

    def _update_phase(
        self,
        phase_text: str,
        progress: float = 0,
        current_file: str | None = None,
    ) -> None:
        """Update the progress UI."""
        self.query_one("#phase-label", Static).update(phase_text)
        self.query_one("#progress-bar", ProgressBar).update(progress=progress)

        file_label = self.query_one("#file-label", Static)
        if current_file:
            file_label.update(f"Current: {current_file}")
        else:
            file_label.update("")

    def _show_success(self) -> None:
        """Show success state."""
        self.query_one("#phase-label", Static).update("Download complete!")
        self.query_one("#progress-bar", ProgressBar).update(progress=100)
        self.query_one("#success-label", Static).display = True
        self.query_one("#cancel-btn", Button).display = False
        self.query_one("#done-btn", Button).display = True

    def _show_error(self, error: str) -> None:
        """Show error state."""
        error_label = self.query_one("#error-label", Static)
        error_label.update(f"Error: {error}")
        error_label.display = True
        self.query_one("#cancel-btn", Button).display = False
        self.query_one("#done-btn", Button).display = True
        self.query_one("#done-btn", Button).label = "Close"

    def _show_cancelled(self) -> None:
        """Show cancelled state."""
        self.query_one("#phase-label", Static).update("Download cancelled")
        self.query_one("#cancel-btn", Button).display = False
        self.query_one("#done-btn", Button).display = True
        self.query_one("#done-btn", Button).label = "Close"

    @on(Button.Pressed, "#cancel-btn")
    def _on_cancel(self, event: Button.Pressed) -> None:
        """Handle cancel button."""
        event.stop()
        self._cancel_download()

    @on(Button.Pressed, "#done-btn")
    def _on_done(self, event: Button.Pressed) -> None:
        """Handle done button."""
        event.stop()
        self.dismiss(self._success)

    def action_cancel(self) -> None:
        """Handle escape key."""
        if (
            self._success
            or self._cancelled
            or self.query_one("#error-label", Static).display
        ):
            # Already finished, just dismiss
            self.dismiss(self._success)
        else:
            # Download in progress, cancel it
            self._cancel_download()

    def _cancel_download(self) -> None:
        """Cancel the download."""
        if self._download_worker and not self._download_worker.is_cancelled:
            self._cancelled = True
            self._download_worker.cancel()
