"""Shared specs TUI screens and dialogs."""

from shotgun.tui.screens.shared_specs.create_spec_dialog import (
    CreateSpecDialog,
    CreateSpecResult,
)
from shotgun.tui.screens.shared_specs.share_specs_dialog import (
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
    "ShareSpecsDialog",
    "ShareSpecsResult",
    "UploadProgressScreen",
    "UploadScreenResult",
]
