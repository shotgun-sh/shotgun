"""Tests for UserQuestionWidget attachment detection."""

from shotgun.tui.screens.chat_screen.history.user_question import (
    ATTACHMENT_PATH_PATTERN,
    UserQuestionWidget,
)


def test_attachment_pattern_matches_absolute_path():
    """Test pattern matches absolute path references."""
    text = "Analyze @/path/to/document.pdf"
    match = ATTACHMENT_PATH_PATTERN.search(text)
    assert match is not None
    assert match.group(1) == "/path/to/document.pdf"


def test_attachment_pattern_matches_home_path():
    """Test pattern matches home directory paths."""
    text = "Check @~/Documents/image.png"
    match = ATTACHMENT_PATH_PATTERN.search(text)
    assert match is not None
    assert match.group(1) == "~/Documents/image.png"


def test_attachment_pattern_matches_relative_path():
    """Test pattern matches relative paths."""
    text = "Look at @./screenshot.jpg"
    match = ATTACHMENT_PATH_PATTERN.search(text)
    assert match is not None
    assert match.group(1) == "./screenshot.jpg"


def test_attachment_pattern_matches_parent_path():
    """Test pattern matches parent directory paths."""
    text = "Review @../parent/file.gif"
    match = ATTACHMENT_PATH_PATTERN.search(text)
    assert match is not None
    assert match.group(1) == "../parent/file.gif"


def test_attachment_pattern_matches_filename_only():
    """Test pattern matches bare filename with extension."""
    text = "Review @report.pdf please"
    match = ATTACHMENT_PATH_PATTERN.search(text)
    assert match is not None
    assert match.group(1) == "report.pdf"


def test_attachment_pattern_matches_bare_relative():
    """Test pattern matches bare relative path."""
    text = "Look at @tmp/file.pdf"
    match = ATTACHMENT_PATH_PATTERN.search(text)
    assert match is not None
    assert match.group(1) == "tmp/file.pdf"


def test_attachment_pattern_no_match_without_at():
    """Test pattern does not match without @ prefix."""
    text = "The file is at /path/to/file.pdf"
    match = ATTACHMENT_PATH_PATTERN.search(text)
    assert match is None


def test_attachment_pattern_no_match_plain_text():
    """Test pattern does not match plain text."""
    text = "Just a regular message"
    match = ATTACHMENT_PATH_PATTERN.search(text)
    assert match is None


def test_extract_attachment_info_pdf():
    """Test extracting attachment info for PDF file."""
    widget = UserQuestionWidget(None)
    info = widget._extract_attachment_info("Analyze @/path/to/doc.pdf")

    assert info is not None
    assert "doc.pdf" in info


def test_extract_attachment_info_png():
    """Test extracting attachment info for PNG file."""
    widget = UserQuestionWidget(None)
    info = widget._extract_attachment_info("Check @image.png")

    assert info is not None
    assert "image.png" in info


def test_extract_attachment_info_jpg():
    """Test extracting attachment info for JPG file."""
    widget = UserQuestionWidget(None)
    info = widget._extract_attachment_info("Look at @photo.jpg")

    assert info is not None
    assert "photo.jpg" in info


def test_extract_attachment_info_jpeg():
    """Test extracting attachment info for JPEG file."""
    widget = UserQuestionWidget(None)
    info = widget._extract_attachment_info("Review @picture.jpeg")

    assert info is not None
    assert "picture.jpeg" in info


def test_extract_attachment_info_gif():
    """Test extracting attachment info for GIF file."""
    widget = UserQuestionWidget(None)
    info = widget._extract_attachment_info("See @animation.gif")

    assert info is not None
    assert "animation.gif" in info


def test_extract_attachment_info_webp():
    """Test extracting attachment info for WebP file."""
    widget = UserQuestionWidget(None)
    info = widget._extract_attachment_info("Check @modern.webp")

    assert info is not None
    assert "modern.webp" in info


def test_extract_attachment_info_no_attachment():
    """Test no attachment info when no @path present."""
    widget = UserQuestionWidget(None)
    info = widget._extract_attachment_info("Just a regular message")

    assert info is None


def test_extract_attachment_info_unsupported_extension():
    """Test no attachment info for unsupported file type."""
    widget = UserQuestionWidget(None)
    info = widget._extract_attachment_info("Edit @document.doc")

    assert info is None


def test_extract_attachment_info_with_path():
    """Test extracting filename from path."""
    widget = UserQuestionWidget(None)
    info = widget._extract_attachment_info("Analyze @/very/long/path/to/report.pdf")

    assert info is not None
    assert "report.pdf" in info
    # Should not contain the path, just the filename
    assert "/very/long/path" not in info


def test_extract_attachment_info_home_path():
    """Test extracting filename from home directory path."""
    widget = UserQuestionWidget(None)
    info = widget._extract_attachment_info("Check @~/Documents/screenshot.png")

    assert info is not None
    assert "screenshot.png" in info
