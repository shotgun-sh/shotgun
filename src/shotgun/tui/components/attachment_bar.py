"""Attachment bar widget for showing pending file attachment."""

from textual.app import ComposeResult
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from shotgun.attachments import (
    AttachmentBarState,
    FileAttachment,
    format_file_size,
    get_attachment_icon,
)


class AttachmentBar(Widget):
    """Widget showing pending attachment above input.

    Displays format: [icon filename.ext (size)]
    Hidden when no attachment is pending.

    Styles defined in chat.tcss.
    """

    state: reactive[AttachmentBarState] = reactive(AttachmentBarState, init=False)

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the attachment bar.

        Args:
            name: Optional widget name.
            id: Optional widget ID.
            classes: Optional CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self.state = AttachmentBarState(attachment=None)
        self.add_class("hidden")

    def compose(self) -> ComposeResult:
        """Compose the attachment bar widget."""
        yield Static("", id="attachment-display")

    def update_attachment(self, attachment: FileAttachment | None) -> None:
        """Update the displayed attachment.

        Args:
            attachment: FileAttachment to display, or None to hide bar.
        """
        self.state = AttachmentBarState(attachment=attachment)

        if attachment is None:
            self.add_class("hidden")
        else:
            self.remove_class("hidden")
            self._refresh_display()

    def _refresh_display(self) -> None:
        """Refresh the attachment display text."""
        attachment = self.state.attachment
        if attachment is None:
            return

        icon = get_attachment_icon(attachment.file_type)
        size_str = format_file_size(attachment.file_size_bytes)
        display_text = f"[{icon} {attachment.file_name} ({size_str})]"

        try:
            display_widget = self.query_one("#attachment-display", Static)
            display_widget.update(display_text)
        except NoMatches:
            pass  # Widget not mounted yet

    def watch_state(self, new_state: AttachmentBarState) -> None:
        """React to state changes.

        Args:
            new_state: The new attachment bar state.
        """
        if new_state.attachment is not None:
            self._refresh_display()
