"""Shared specs TUI screens and dialogs."""

from shotgun.tui.screens.shared_specs.create_spec_dialog import (
    CreateSpecDialog,
    CreateSpecResult,
)
from shotgun.tui.screens.shared_specs.share_specs_dialog import (
    ShareSpecsAction,
    ShareSpecsDialog,
    ShareSpecsResult,
)
from shotgun.tui.screens.shared_specs.upload_progress_screen import (
    UploadProgressScreen,
    UploadScreenResult,
)

__all__ = [
    "CreateSpecDialog",
    "CreateSpecResult",
    "ShareSpecsAction",
    "ShareSpecsDialog",
    "ShareSpecsResult",
    "UploadProgressScreen",
    "UploadScreenResult",
]
