"""Screen showing upload progress for sharing specs."""

from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.events import Resize
from textual.screen import ModalScreen
from textual.widgets import Button, Label, ProgressBar, Static
from textual.worker import Worker, WorkerCancelled, get_current_worker

from shotgun.logging_config import get_logger
from shotgun.shotgun_web.shared_specs.models import UploadProgress, UploadResult
from shotgun.shotgun_web.shared_specs.upload_pipeline import run_upload_pipeline
from shotgun.shotgun_web.shared_specs.utils import UploadPhase, format_bytes
from shotgun.shotgun_web.specs_client import SpecsClient
from shotgun.tui.layout import COMPACT_HEIGHT_THRESHOLD
from shotgun.tui.screens.shared_specs.models import UploadScreenResult

logger = get_logger(__name__)


class UploadProgressScreen(ModalScreen[UploadScreenResult]):
    """Screen showing upload progress for sharing specs.

    Displays:
    - Current phase (scanning, hashing, uploading, closing)
    - Progress bar
    - Current file being processed
    - Bytes uploaded / total bytes

    On success, shows URL with options to open in browser or copy.
    """

    DEFAULT_CSS = """
        UploadProgressScreen {
            align: center middle;
            background: rgba(0, 0, 0, 0.0);
        }

        UploadProgressScreen > #dialog-container {
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

        #bytes-label {
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
        UploadProgressScreen.compact #dialog-container {
            padding: 0 2;
            max-height: 98%;
        }

        UploadProgressScreen.compact #dialog-title {
            padding-bottom: 0;
        }

        UploadProgressScreen.compact #phase-label {
            padding: 0;
        }

        UploadProgressScreen.compact #progress-bar {
            padding: 0;
        }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        workspace_id: str,
        # For existing spec - add version (spec_id required, version_id optional)
        spec_id: str | None = None,
        version_id: str | None = None,
        # For new spec - create spec + version
        spec_name: str | None = None,
        spec_description: str | None = None,
        spec_is_public: bool = False,
        project_root: Path | None = None,
    ) -> None:
        """Initialize the screen.

        Args:
            workspace_id: Workspace UUID
            spec_id: Spec UUID (for existing spec) or None (for new spec)
            version_id: Version UUID (if already created) or None
            spec_name: Name for new spec (triggers spec creation)
            spec_description: Description for new spec
            spec_is_public: Whether new spec should be public
            project_root: Project root containing .shotgun/ (defaults to cwd)

        Usage:
            # Add version to existing spec (creates version)
            UploadProgressScreen(workspace_id="...", spec_id="...")

            # Create new spec and version
            UploadProgressScreen(workspace_id="...", spec_name="My Spec")

            # Use pre-created version (legacy mode)
            UploadProgressScreen(workspace_id="...", spec_id="...", version_id="...")
        """
        super().__init__()
        self.workspace_id = workspace_id
        self.spec_id = spec_id
        self.version_id = version_id
        self.spec_name = spec_name
        self.spec_description = spec_description
        self.spec_is_public = spec_is_public
        self.project_root = project_root
        self._result: UploadResult | None = None
        self._upload_worker: Worker[UploadResult] | None = None
        self._cancelled = False

    def compose(self) -> ComposeResult:
        """Compose the screen widgets."""
        with Container(id="dialog-container"):
            yield Label("Sharing specs to workspace", id="dialog-title")

            # Progress section
            yield Static("Phase 1/4: Scanning files...", id="phase-label")
            yield ProgressBar(total=100, id="progress-bar")
            yield Static("", id="file-label")
            yield Static("", id="bytes-label")

            # Error section (hidden by default)
            yield Static("", id="error-label")

            # Success section (hidden by default)
            yield Static("Specs shared successfully!", id="success-label")

            # Buttons
            with Horizontal(id="dialog-buttons"):
                yield Button("Cancel", id="cancel-btn")
                yield Button("Open in Browser", variant="primary", id="open-btn")
                yield Button("Copy URL", id="copy-btn")
                yield Button("Done", id="done-btn")

    def on_mount(self) -> None:
        """Start the upload when screen is mounted."""
        # Hide success buttons initially
        self.query_one("#open-btn", Button).display = False
        self.query_one("#copy-btn", Button).display = False
        self.query_one("#done-btn", Button).display = False

        # Apply compact layout if starting in a short terminal
        self._apply_compact_layout(self.app.size.height < COMPACT_HEIGHT_THRESHOLD)

        # Start the upload
        self._start_upload()

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
    async def _start_upload(self) -> None:
        """Run the upload pipeline."""
        worker = get_current_worker()
        self._upload_worker = worker

        def on_progress(progress: UploadProgress) -> None:
            """Handle progress updates from the pipeline."""
            # Check if we should cancel
            if worker.is_cancelled:
                raise WorkerCancelled()

            # Update UI directly (we're in an async context via @work)
            self._update_progress(progress)

        try:
            # Phase 0: Create spec/version if needed
            client = SpecsClient()

            if self.spec_name:
                # Creating a new spec
                self._show_creating_phase("Creating spec...")
                if worker.is_cancelled:
                    raise WorkerCancelled()

                create_response = await client.create_spec(
                    self.workspace_id,
                    name=self.spec_name,
                    description=self.spec_description,
                )
                self.spec_id = create_response.spec.id
                self.version_id = create_response.version.id

                # Set public if requested
                if self.spec_is_public:
                    self._show_creating_phase("Setting visibility...")
                    if worker.is_cancelled:
                        raise WorkerCancelled()
                    await client.update_spec(
                        self.workspace_id, self.spec_id, is_public=True
                    )

            elif self.spec_id and not self.version_id:
                # Adding version to existing spec
                self._show_creating_phase("Creating version...")
                if worker.is_cancelled:
                    raise WorkerCancelled()

                version_response = await client.create_version(
                    self.workspace_id, self.spec_id
                )
                self.version_id = version_response.version.id

            # Validate we have spec_id and version_id
            if not self.spec_id or not self.version_id:
                self._show_error("Missing spec or version ID")
                return

            # Run upload pipeline
            result = await run_upload_pipeline(
                self.workspace_id,
                self.spec_id,
                self.version_id,
                self.project_root,
                on_progress=on_progress,
            )
            self._result = result
            self._show_result(result)
        except WorkerCancelled:
            self._cancelled = True
            self._show_cancelled()
        except Exception as e:
            logger.exception(f"Upload failed: {type(e).__name__}: {e}")
            error_msg = str(e) if str(e) else type(e).__name__
            self._show_error(error_msg)

    def _show_creating_phase(self, message: str) -> None:
        """Update UI to show creating phase."""
        phase_label = self.query_one("#phase-label", Static)
        phase_label.update(message)
        # Keep progress bar at 0 during creation
        progress_bar = self.query_one("#progress-bar", ProgressBar)
        progress_bar.update(progress=0)
        # Clear file/bytes labels
        self.query_one("#file-label", Static).update("")
        self.query_one("#bytes-label", Static).update("")

    def _update_progress(self, progress: UploadProgress) -> None:
        """Update the UI with progress information."""
        phase_names = {
            UploadPhase.CREATING: "Creating spec...",
            UploadPhase.SCANNING: "Phase 1/4: Scanning files...",
            UploadPhase.HASHING: "Phase 2/4: Calculating hashes...",
            UploadPhase.UPLOADING: "Phase 3/4: Uploading files...",
            UploadPhase.CLOSING: "Phase 4/4: Finalizing version...",
            UploadPhase.COMPLETE: "Complete!",
            UploadPhase.ERROR: "Error",
        }

        phase_label = self.query_one("#phase-label", Static)
        progress_bar = self.query_one("#progress-bar", ProgressBar)
        file_label = self.query_one("#file-label", Static)
        bytes_label = self.query_one("#bytes-label", Static)

        # Update phase label
        phase_text = phase_names.get(progress.phase, progress.phase)
        if progress.total > 0:
            phase_text = f"{phase_text} ({progress.current}/{progress.total})"
        phase_label.update(phase_text)

        # Update progress bar
        if progress.total > 0:
            percentage = (progress.current / progress.total) * 100
            progress_bar.update(progress=percentage)
        else:
            progress_bar.update(progress=0)

        # Update file label
        if progress.current_file:
            file_label.update(f"Current: {progress.current_file}")
        else:
            file_label.update("")

        # Update bytes label
        if progress.total_bytes > 0:
            bytes_label.update(
                f"Uploaded: {format_bytes(progress.bytes_uploaded)} / {format_bytes(progress.total_bytes)}"
            )
        else:
            bytes_label.update("")

    def _show_result(self, result: UploadResult) -> None:
        """Show the upload result."""
        if result.success:
            self._show_success(result.web_url)
        else:
            self._show_error(result.error or "Unknown error")

    def _show_success(self, web_url: str | None) -> None:
        """Show success state."""
        # Update phase label
        self.query_one("#phase-label", Static).update("Upload complete!")
        self.query_one("#progress-bar", ProgressBar).update(progress=100)

        # Show success label
        self.query_one("#success-label", Static).display = True

        # Hide cancel, show success buttons
        self.query_one("#cancel-btn", Button).display = False
        self.query_one("#open-btn", Button).display = bool(web_url)
        self.query_one("#copy-btn", Button).display = bool(web_url)
        self.query_one("#done-btn", Button).display = True

    def _show_error(self, error: str) -> None:
        """Show error state."""
        error_label = self.query_one("#error-label", Static)
        error_label.update(f"Error: {error}")
        error_label.display = True

        # Hide cancel, show done
        self.query_one("#cancel-btn", Button).display = False
        self.query_one("#done-btn", Button).display = True

    def _show_cancelled(self) -> None:
        """Show cancelled state."""
        self.query_one("#phase-label", Static).update("Upload cancelled")
        self.query_one("#cancel-btn", Button).display = False
        self.query_one("#done-btn", Button).display = True

    @on(Button.Pressed, "#cancel-btn")
    def _on_cancel(self, event: Button.Pressed) -> None:
        """Handle cancel button."""
        event.stop()
        self._cancel_upload()

    @on(Button.Pressed, "#open-btn")
    def _on_open(self, event: Button.Pressed) -> None:
        """Handle open in browser button."""
        event.stop()
        if self._result and self._result.web_url:
            import webbrowser

            webbrowser.open(self._result.web_url)

    @on(Button.Pressed, "#copy-btn")
    def _on_copy(self, event: Button.Pressed) -> None:
        """Handle copy URL button."""
        event.stop()
        if self._result and self._result.web_url:
            try:
                import pyperclip  # type: ignore[import-untyped]

                pyperclip.copy(self._result.web_url)
                self.query_one("#copy-btn", Button).label = "Copied!"
            except Exception:
                # pyperclip may not be available on all systems
                logger.debug("pyperclip not available for URL copy")

    @on(Button.Pressed, "#done-btn")
    def _on_done(self, event: Button.Pressed) -> None:
        """Handle done button."""
        event.stop()
        self._dismiss_with_result()

    def action_cancel(self) -> None:
        """Handle escape key."""
        if self._result:
            # Upload complete, just dismiss
            self._dismiss_with_result()
        else:
            # Upload in progress, cancel it
            self._cancel_upload()

    def _cancel_upload(self) -> None:
        """Cancel the upload."""
        if self._upload_worker and not self._upload_worker.is_cancelled:
            self._cancelled = True
            self._upload_worker.cancel()

    def _dismiss_with_result(self) -> None:
        """Dismiss the screen with the appropriate result."""
        if self._cancelled:
            self.dismiss(UploadScreenResult(success=False, cancelled=True))
        elif self._result:
            self.dismiss(
                UploadScreenResult(
                    success=self._result.success,
                    web_url=self._result.web_url,
                )
            )
        else:
            self.dismiss(UploadScreenResult(success=False))
