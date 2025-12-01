"""Dialog for selecting an existing spec or creating a new one."""

from datetime import datetime, timezone

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.events import Resize
from textual.screen import ModalScreen
from textual.widgets import Button, Label, ListItem, ListView, Static

from shotgun.logging_config import get_logger
from shotgun.shotgun_web.exceptions import (
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)
from shotgun.shotgun_web.models import SpecResponse, WorkspaceNotFoundError
from shotgun.shotgun_web.specs_client import SpecsClient
from shotgun.tui.layout import COMPACT_HEIGHT_THRESHOLD
from shotgun.tui.screens.shared_specs.models import (
    ShareSpecsAction,
    ShareSpecsResult,
)

logger = get_logger(__name__)


def _relative_time(dt: datetime | None) -> str:
    """Convert datetime to relative time string (e.g., '2 days ago')."""
    if dt is None:
        return "unknown"
    now = datetime.now(timezone.utc)
    # Make sure dt is timezone-aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    diff = now - dt
    seconds = diff.total_seconds()

    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} min{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"
    elif seconds < 2592000:
        weeks = int(seconds / 604800)
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    else:
        months = int(seconds / 2592000)
        return f"{months} month{'s' if months != 1 else ''} ago"


class ShareSpecsDialog(ModalScreen[ShareSpecsResult | None]):
    """Dialog for selecting an existing spec or creating a new one.

    Shows a list of existing specs in the workspace with:
    - Name (bold)
    - Latest version label or "No versions"
    - Created date (relative time)
    - Visibility badge (Team/Public)

    Plus a "Create new spec" option at the top.

    Returns ShareSpecsResult or None if cancelled.
    """

    DEFAULT_CSS = """
        ShareSpecsDialog {
            align: center middle;
            background: rgba(0, 0, 0, 0.0);
        }

        ShareSpecsDialog > #dialog-container {
            width: 80%;
            max-width: 90;
            height: auto;
            max-height: 80%;
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

        #dialog-subtitle {
            color: $text-muted;
            padding-bottom: 1;
            text-align: center;
        }

        #spec-list {
            height: auto;
            max-height: 20;
            border: solid $border;
            padding: 0 1;
        }

        #spec-list > ListItem {
            padding: 1 0;
        }

        #spec-list > ListItem.--highlight {
            background: $primary-darken-2;
        }

        .spec-item-label {
            width: 100%;
        }

        .spec-name {
            text-style: bold;
        }

        .spec-meta {
            color: $text-muted;
        }

        .visibility-badge-public {
            color: $success;
        }

        .visibility-badge-team {
            color: $warning;
        }

        #loading-label {
            text-align: center;
            padding: 2;
            color: $text-muted;
        }

        #error-label {
            text-align: center;
            padding: 2;
            color: $error;
        }

        #dialog-buttons {
            layout: horizontal;
            align-horizontal: right;
            height: auto;
            padding-top: 1;
        }

        #dialog-buttons Button {
            margin-left: 1;
        }

        /* Compact styles for short terminals */
        ShareSpecsDialog.compact #dialog-container {
            padding: 0 2;
            max-height: 98%;
        }

        ShareSpecsDialog.compact #dialog-title {
            padding-bottom: 0;
        }

        ShareSpecsDialog.compact #dialog-subtitle {
            padding-bottom: 0;
        }

        ShareSpecsDialog.compact #spec-list {
            max-height: 10;
        }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self) -> None:
        """Initialize the dialog."""
        super().__init__()
        self.workspace_id: str | None = None
        self._specs: list[SpecResponse] = []
        self._loading = True
        self._error: str | None = None

    def compose(self) -> ComposeResult:
        """Compose the dialog widgets."""
        with Container(id="dialog-container"):
            yield Label("Share Specs", id="dialog-title")
            yield Static(
                "Select an existing spec to add a new version, or create a new spec.",
                id="dialog-subtitle",
            )
            yield Static("Loading specs...", id="loading-label")
            yield Static("", id="error-label")
            yield ListView(id="spec-list")
            with Horizontal(id="dialog-buttons"):
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        """Load specs when dialog is mounted."""
        # Hide list and error initially
        self.query_one("#spec-list", ListView).display = False
        self.query_one("#error-label", Static).display = False

        # Apply compact layout if starting in a short terminal
        self._apply_compact_layout(self.app.size.height < COMPACT_HEIGHT_THRESHOLD)

        # Load specs
        self._load_specs()

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

    def _update_loading_message(self, message: str) -> None:
        """Update the loading label message."""
        self.query_one("#loading-label", Static).update(message)

    @work
    async def _load_specs(self) -> None:
        """Fetch workspace, check permissions, and load specs."""
        try:
            client = SpecsClient()

            # Step 1: Get workspace
            self._update_loading_message("Connecting to workspace...")
            try:
                self.workspace_id = await client.get_or_fetch_workspace_id()
            except UnauthorizedError:
                self._loading = False
                self._error = "Not authenticated. Run 'shotgun auth' to login."
                self._show_error()
                return
            except WorkspaceNotFoundError:
                self._loading = False
                self._error = "No workspaces available. Please create one at shotgun.sh"
                self._show_error()
                return

            # Step 2: Check permissions
            self._update_loading_message("Checking permissions...")
            try:
                permissions = await client.check_permissions(self.workspace_id)
                if not permissions.can_create_specs:
                    self._loading = False
                    self._error = "You need editor access to share specs"
                    self._show_error()
                    return
            except NotFoundError:
                # Permissions endpoint not available yet - skip check
                logger.debug("Permissions endpoint not available, skipping check")
            except UnauthorizedError:
                self._loading = False
                self._error = "Not authenticated. Run 'shotgun auth' to login."
                self._show_error()
                return
            except ForbiddenError:
                self._loading = False
                self._error = "You don't have access to this workspace"
                self._show_error()
                return

            # Step 3: Load specs
            self._update_loading_message("Loading specs...")
            response = await client.list_specs(self.workspace_id)
            self._specs = response.specs
            self._loading = False
            self._populate_list()
        except Exception as e:
            logger.exception(f"Failed to load specs: {type(e).__name__}: {e}")
            self._loading = False
            self._error = str(e) if str(e) else type(e).__name__
            self._show_error()

    def _populate_list(self) -> None:
        """Populate the ListView with specs."""
        # Hide loading label
        self.query_one("#loading-label", Static).display = False

        # Show and populate list
        list_view = self.query_one("#spec-list", ListView)
        list_view.display = True

        # Clear existing items
        list_view.clear()

        # Add "Create new spec" option first
        create_label = Label(
            "[bold]+ Create new spec[/]\nStart a fresh spec for your .shotgun/ files",
            classes="spec-item-label",
        )
        list_view.append(ListItem(create_label, id="create-new"))

        # Add existing specs
        for spec in self._specs:
            label = self._format_spec_label(spec)
            list_view.append(ListItem(label, id=f"spec-{spec.id}"))

        # Focus the list
        list_view.focus()

    def _format_spec_label(self, spec: SpecResponse) -> Label:
        """Format a spec as a label for display."""
        # Name
        name = spec.name

        # Latest version info
        if spec.latest_version and spec.latest_version.label:
            version_info = spec.latest_version.label
        elif spec.latest_version:
            version_info = "Latest version"
        else:
            version_info = "No versions"

        # Visibility badge
        if spec.is_public:
            visibility = "[green]Public[/]"
        else:
            visibility = "[yellow]Team[/]"

        # Relative time
        time_ago = _relative_time(spec.created_on)

        # Format the label
        text = f"[bold]{name}[/] · {visibility}\n{version_info} · {time_ago}"
        return Label(text, classes="spec-item-label")

    def _show_error(self) -> None:
        """Show error message."""
        self.query_one("#loading-label", Static).display = False
        error_label = self.query_one("#error-label", Static)
        error_label.update(f"Failed to load specs: {self._error}")
        error_label.display = True

    @on(ListView.Selected)
    def _on_spec_selected(self, event: ListView.Selected) -> None:
        """Handle spec selection."""
        item = event.item
        if item is None or item.id is None:
            return

        if item.id == "create-new":
            self.dismiss(
                ShareSpecsResult(
                    action=ShareSpecsAction.CREATE,
                    workspace_id=self.workspace_id,
                )
            )
        elif item.id.startswith("spec-"):
            spec_id = item.id.removeprefix("spec-")
            # Find the spec to get the name
            spec_name = None
            for spec in self._specs:
                if spec.id == spec_id:
                    spec_name = spec.name
                    break
            self.dismiss(
                ShareSpecsResult(
                    action=ShareSpecsAction.ADD_VERSION,
                    workspace_id=self.workspace_id,
                    spec_id=spec_id,
                    spec_name=spec_name,
                )
            )

    @on(Button.Pressed, "#cancel")
    def _on_cancel(self, event: Button.Pressed) -> None:
        """Handle cancel button."""
        event.stop()
        self.dismiss(None)

    def action_cancel(self) -> None:
        """Handle escape key."""
        self.dismiss(None)
