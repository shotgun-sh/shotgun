"""Tests for AttachmentHintWidget component."""

import pytest
from textual.app import App, ComposeResult

from shotgun.attachments import AttachmentHint, AttachmentType
from shotgun.tui.screens.chat_screen.attachment_hint import AttachmentHintWidget


def create_test_hint(
    filename: str = "document.pdf",
    file_type: AttachmentType = AttachmentType.PDF,
    size_display: str = "2.5 MB",
) -> AttachmentHint:
    """Create a test AttachmentHint."""
    return AttachmentHint(
        filename=filename,
        file_type=file_type,
        file_size_display=size_display,
    )


def test_attachment_hint_widget_initialization():
    """Test AttachmentHintWidget initializes with hint data."""
    hint = create_test_hint()
    widget = AttachmentHintWidget(hint)

    assert widget.hint == hint
    assert widget.hint.filename == "document.pdf"
    assert widget.hint.file_type == AttachmentType.PDF
    assert widget.hint.file_size_display == "2.5 MB"


def test_attachment_hint_pdf_type():
    """Test AttachmentHintWidget with PDF hint."""
    hint = create_test_hint(
        filename="report.pdf",
        file_type=AttachmentType.PDF,
        size_display="5.0 MB",
    )
    widget = AttachmentHintWidget(hint)

    assert widget.hint.file_type == AttachmentType.PDF


def test_attachment_hint_image_type():
    """Test AttachmentHintWidget with image hint."""
    hint = create_test_hint(
        filename="screenshot.png",
        file_type=AttachmentType.PNG,
        size_display="1.2 MB",
    )
    widget = AttachmentHintWidget(hint)

    assert widget.hint.file_type == AttachmentType.PNG


def test_attachment_hint_jpeg_type():
    """Test AttachmentHintWidget with JPEG hint."""
    hint = create_test_hint(
        filename="photo.jpg",
        file_type=AttachmentType.JPG,
        size_display="3.0 MB",
    )
    widget = AttachmentHintWidget(hint)

    assert widget.hint.file_type == AttachmentType.JPG


def test_attachment_hint_gif_type():
    """Test AttachmentHintWidget with GIF hint."""
    hint = create_test_hint(
        filename="animation.gif",
        file_type=AttachmentType.GIF,
        size_display="500 KB",
    )
    widget = AttachmentHintWidget(hint)

    assert widget.hint.file_type == AttachmentType.GIF


def test_attachment_hint_webp_type():
    """Test AttachmentHintWidget with WebP hint."""
    hint = create_test_hint(
        filename="image.webp",
        file_type=AttachmentType.WEBP,
        size_display="800 KB",
    )
    widget = AttachmentHintWidget(hint)

    assert widget.hint.file_type == AttachmentType.WEBP


@pytest.mark.asyncio
async def test_attachment_hint_compose():
    """Test AttachmentHintWidget composes correctly in an app."""

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield AttachmentHintWidget(create_test_hint())

    async with TestApp().run_test() as pilot:
        widget = pilot.app.query_one(AttachmentHintWidget)
        assert widget is not None
        assert widget.hint.filename == "document.pdf"
