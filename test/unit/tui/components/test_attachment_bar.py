"""Tests for AttachmentBar component."""

from pathlib import Path

import pytest
from textual.app import App, ComposeResult

from shotgun.attachments import (
    AttachmentBarState,
    AttachmentType,
    FileAttachment,
)
from shotgun.tui.components.attachment_bar import AttachmentBar


def create_test_attachment(
    file_type: AttachmentType = AttachmentType.PDF,
    file_size: int = 2_500_000,
    file_name: str = "document.pdf",
) -> FileAttachment:
    """Create a test FileAttachment."""
    return FileAttachment(
        file_path=Path(f"/test/{file_name}"),
        file_name=file_name,
        file_type=file_type,
        file_size_bytes=file_size,
        content_base64=None,
        mime_type="application/pdf" if file_type == AttachmentType.PDF else "image/png",
    )


def test_attachment_bar_state_model():
    """Test AttachmentBarState model initialization."""
    state = AttachmentBarState()
    assert state.attachment is None

    attachment = create_test_attachment()
    state_with_attachment = AttachmentBarState(attachment=attachment)
    assert state_with_attachment.attachment == attachment


def test_attachment_bar_initialization():
    """Test AttachmentBar initializes with hidden state."""
    bar = AttachmentBar()
    assert bar.state.attachment is None
    assert bar.has_class("hidden")


def test_attachment_bar_update_attachment_sets_state():
    """Test updating attachment sets state correctly."""
    bar = AttachmentBar()
    attachment = create_test_attachment()

    bar.update_attachment(attachment)

    assert bar.state.attachment == attachment


def test_attachment_bar_update_none_sets_hidden():
    """Test updating with None sets state to None."""
    bar = AttachmentBar()
    attachment = create_test_attachment()

    bar.update_attachment(attachment)
    bar.update_attachment(None)

    assert bar.state.attachment is None
    assert bar.has_class("hidden")


def test_attachment_bar_update_removes_hidden_class():
    """Test updating with attachment removes hidden class."""
    bar = AttachmentBar()
    assert bar.has_class("hidden")

    attachment = create_test_attachment()
    bar.update_attachment(attachment)

    assert not bar.has_class("hidden")


def test_attachment_bar_update_adds_hidden_class_on_none():
    """Test updating with None adds hidden class."""
    bar = AttachmentBar()
    attachment = create_test_attachment()

    bar.update_attachment(attachment)
    assert not bar.has_class("hidden")

    bar.update_attachment(None)
    assert bar.has_class("hidden")


def test_attachment_bar_pdf_state():
    """Test state with PDF attachment."""
    bar = AttachmentBar()
    attachment = create_test_attachment(
        file_type=AttachmentType.PDF,
        file_name="report.pdf",
    )

    bar.update_attachment(attachment)

    assert bar.state.attachment is not None
    assert bar.state.attachment.file_type == AttachmentType.PDF
    assert bar.state.attachment.file_name == "report.pdf"


def test_attachment_bar_image_state():
    """Test state with image attachment."""
    bar = AttachmentBar()
    attachment = FileAttachment(
        file_path=Path("/test/image.png"),
        file_name="image.png",
        file_type=AttachmentType.PNG,
        file_size_bytes=1_200_000,
        content_base64=None,
        mime_type="image/png",
    )

    bar.update_attachment(attachment)

    assert bar.state.attachment is not None
    assert bar.state.attachment.file_type == AttachmentType.PNG
    assert bar.state.attachment.file_name == "image.png"


@pytest.mark.asyncio
async def test_attachment_bar_compose():
    """Test AttachmentBar composes correctly in an app."""

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield AttachmentBar(id="test-bar")

    async with TestApp().run_test() as pilot:
        bar = pilot.app.query_one(AttachmentBar)
        assert bar is not None
        assert bar.has_class("hidden")


@pytest.mark.asyncio
async def test_attachment_bar_update_in_app():
    """Test updating AttachmentBar within a running app."""

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield AttachmentBar(id="test-bar")

    async with TestApp().run_test() as pilot:
        bar = pilot.app.query_one(AttachmentBar)

        # Initially hidden
        assert bar.has_class("hidden")

        # Update with attachment
        attachment = create_test_attachment()
        bar.update_attachment(attachment)

        assert not bar.has_class("hidden")
        assert bar.state.attachment == attachment

        # Hide with None
        bar.update_attachment(None)
        assert bar.has_class("hidden")
