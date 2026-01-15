"""Attachment hint widget for displaying attachments in chat history."""

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from shotgun.attachments import AttachmentHint, get_attachment_icon


class AttachmentHintWidget(Widget):
    """Widget that displays attachment indicator in chat history.

    Display format: "icon Attached: filename (size)"
    """

    DEFAULT_CSS = """
    AttachmentHintWidget {
        height: auto;
        padding: 0 1;
        margin: 0 1;
        color: $text-muted;
    }
    """

    def __init__(self, hint: AttachmentHint) -> None:
        """Initialize with attachment hint data.

        Args:
            hint: AttachmentHint model containing display info.
        """
        super().__init__()
        self.hint = hint

    def compose(self) -> ComposeResult:
        """Compose the attachment hint widget."""
        icon = get_attachment_icon(self.hint.file_type)
        display_text = (
            f"{icon} Attached: {self.hint.filename} ({self.hint.file_size_display})"
        )
        yield Static(display_text)
