"""Unit tests for attachment parser module."""

from pathlib import Path

from shotgun.attachments.models import AttachmentType
from shotgun.attachments.parser import (
    ATTACHMENT_PATH_PATTERN,
    MIME_TYPES,
    SUPPORTED_EXTENSIONS,
    _extract_path_reference,
    _get_mime_type,
    _resolve_path,
    _validate_file_extension,
    is_image_type,
    parse_attachment_reference,
)


# Test _extract_path_reference
def test_extract_path_reference_absolute_path():
    """Test extracting absolute path reference."""
    result = _extract_path_reference("Check @/path/to/file.pdf please")
    assert result == "/path/to/file.pdf"


def test_extract_path_reference_home_path():
    """Test extracting home directory path reference."""
    result = _extract_path_reference("Analyze @~/documents/report.png")
    assert result == "~/documents/report.png"


def test_extract_path_reference_relative_current():
    """Test extracting relative path with ./"""
    result = _extract_path_reference("Look at @./local/image.jpg")
    assert result == "./local/image.jpg"


def test_extract_path_reference_relative_parent():
    """Test extracting relative path with ../"""
    result = _extract_path_reference("See @../parent/doc.gif")
    assert result == "../parent/doc.gif"


def test_extract_path_reference_no_match():
    """Test no path reference found."""
    result = _extract_path_reference("No attachment here")
    assert result is None


def test_extract_path_reference_email_not_matched():
    """Test that email addresses are not matched."""
    result = _extract_path_reference("Contact user@example.com")
    assert result is None


def test_extract_path_reference_first_match_only():
    """Test that only first match is returned."""
    result = _extract_path_reference("@/first.pdf and @/second.png")
    assert result == "/first.pdf"


# Test _resolve_path
def test_resolve_path_absolute():
    """Test resolving absolute path."""
    result = _resolve_path("/absolute/path/file.pdf")
    assert result == Path("/absolute/path/file.pdf")
    assert result.is_absolute()


def test_resolve_path_home_directory():
    """Test resolving home directory path."""
    result = _resolve_path("~/documents/file.png")
    assert result.is_absolute()
    assert "~" not in str(result)


def test_resolve_path_relative_current(tmp_path, monkeypatch):
    """Test resolving relative path from current directory."""
    monkeypatch.chdir(tmp_path)
    result = _resolve_path("./subdir/file.jpg")
    assert result.is_absolute()
    assert str(tmp_path) in str(result)


def test_resolve_path_relative_parent(tmp_path, monkeypatch):
    """Test resolving parent directory path."""
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    monkeypatch.chdir(subdir)
    result = _resolve_path("../file.gif")
    assert result.is_absolute()


# Test _validate_file_extension
def test_validate_extension_pdf():
    """Test PDF extension is valid."""
    result = _validate_file_extension(Path("/path/to/doc.pdf"))
    assert result == AttachmentType.PDF


def test_validate_extension_png():
    """Test PNG extension is valid."""
    result = _validate_file_extension(Path("/path/to/image.png"))
    assert result == AttachmentType.PNG


def test_validate_extension_jpg():
    """Test JPG extension is valid."""
    result = _validate_file_extension(Path("/path/to/photo.jpg"))
    assert result == AttachmentType.JPG


def test_validate_extension_jpeg():
    """Test JPEG extension is valid."""
    result = _validate_file_extension(Path("/path/to/photo.jpeg"))
    assert result == AttachmentType.JPEG


def test_validate_extension_gif():
    """Test GIF extension is valid."""
    result = _validate_file_extension(Path("/path/to/anim.gif"))
    assert result == AttachmentType.GIF


def test_validate_extension_webp():
    """Test WEBP extension is valid."""
    result = _validate_file_extension(Path("/path/to/modern.webp"))
    assert result == AttachmentType.WEBP


def test_validate_extension_unsupported():
    """Test unsupported extension returns None."""
    result = _validate_file_extension(Path("/path/to/file.txt"))
    assert result is None


def test_validate_extension_case_insensitive():
    """Test extension validation is case-insensitive."""
    result = _validate_file_extension(Path("/path/to/IMAGE.PNG"))
    assert result == AttachmentType.PNG


def test_validate_extension_no_extension():
    """Test file with no extension returns None."""
    result = _validate_file_extension(Path("/path/to/noextension"))
    assert result is None


# Test _get_mime_type
def test_get_mime_type_pdf():
    """Test MIME type for PDF."""
    assert _get_mime_type(AttachmentType.PDF) == "application/pdf"


def test_get_mime_type_png():
    """Test MIME type for PNG."""
    assert _get_mime_type(AttachmentType.PNG) == "image/png"


def test_get_mime_type_jpg():
    """Test MIME type for JPG."""
    assert _get_mime_type(AttachmentType.JPG) == "image/jpeg"


def test_get_mime_type_jpeg():
    """Test MIME type for JPEG."""
    assert _get_mime_type(AttachmentType.JPEG) == "image/jpeg"


def test_get_mime_type_gif():
    """Test MIME type for GIF."""
    assert _get_mime_type(AttachmentType.GIF) == "image/gif"


def test_get_mime_type_webp():
    """Test MIME type for WEBP."""
    assert _get_mime_type(AttachmentType.WEBP) == "image/webp"


# Test is_image_type
def test_is_image_type_png():
    """Test PNG is an image type."""
    assert is_image_type(AttachmentType.PNG) is True


def test_is_image_type_jpg():
    """Test JPG is an image type."""
    assert is_image_type(AttachmentType.JPG) is True


def test_is_image_type_jpeg():
    """Test JPEG is an image type."""
    assert is_image_type(AttachmentType.JPEG) is True


def test_is_image_type_gif():
    """Test GIF is an image type."""
    assert is_image_type(AttachmentType.GIF) is True


def test_is_image_type_webp():
    """Test WEBP is an image type."""
    assert is_image_type(AttachmentType.WEBP) is True


def test_is_image_type_pdf():
    """Test PDF is not an image type."""
    assert is_image_type(AttachmentType.PDF) is False


# Test parse_attachment_reference (integration)
def test_parse_attachment_no_reference():
    """Test parsing text with no attachment reference."""
    result = parse_attachment_reference("Just regular text")
    assert result.original_text == "Just regular text"
    assert result.attachment is None
    assert result.error_message is None


def test_parse_attachment_file_not_found():
    """Test parsing with non-existent file."""
    result = parse_attachment_reference("Check @/nonexistent/file.pdf")
    assert result.original_text == "Check @/nonexistent/file.pdf"
    assert result.attachment is None
    assert result.error_message is not None
    assert "not found" in result.error_message.lower()


def test_parse_attachment_unsupported_extension(tmp_path):
    """Test parsing with unsupported file type."""
    txt_file = tmp_path / "doc.txt"
    txt_file.write_text("content")

    result = parse_attachment_reference(f"Check @{txt_file}")
    assert result.attachment is None
    assert result.error_message is not None
    assert "unsupported" in result.error_message.lower()


def test_parse_attachment_success_pdf(tmp_path):
    """Test successful PDF attachment parsing."""
    pdf_file = tmp_path / "document.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 test content")

    result = parse_attachment_reference(f"Analyze @{pdf_file} please")

    assert result.original_text == f"Analyze @{pdf_file} please"
    assert result.attachment is not None
    assert result.attachment.file_name == "document.pdf"
    assert result.attachment.file_type == AttachmentType.PDF
    assert result.attachment.mime_type == "application/pdf"
    assert result.attachment.file_path == pdf_file
    assert result.attachment.file_size_bytes > 0
    assert result.attachment.content_base64 is None  # Not encoded yet
    assert result.error_message is None


def test_parse_attachment_success_image(tmp_path):
    """Test successful image attachment parsing."""
    png_file = tmp_path / "screenshot.png"
    # Write minimal PNG header
    png_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    result = parse_attachment_reference(f"What is in @{png_file}?")

    assert result.attachment is not None
    assert result.attachment.file_name == "screenshot.png"
    assert result.attachment.file_type == AttachmentType.PNG
    assert result.attachment.mime_type == "image/png"
    assert result.error_message is None


def test_parse_attachment_preserves_original_text(tmp_path):
    """Test that original text is preserved with @path intact."""
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(b"test content")

    original = f"Please review @{pdf_file} and summarize"
    result = parse_attachment_reference(original)

    assert result.original_text == original
    assert f"@{pdf_file}" in result.original_text


def test_parse_attachment_directory_not_file(tmp_path):
    """Test that directories are rejected."""
    result = parse_attachment_reference(f"Check @{tmp_path}")
    assert result.attachment is None
    assert result.error_message is not None
    assert "not a file" in result.error_message.lower()


def test_parse_attachment_all_image_types(tmp_path):
    """Test all image types are correctly parsed."""
    test_cases = [
        ("test.jpg", AttachmentType.JPG, "image/jpeg"),
        ("test.jpeg", AttachmentType.JPEG, "image/jpeg"),
        ("test.gif", AttachmentType.GIF, "image/gif"),
        ("test.webp", AttachmentType.WEBP, "image/webp"),
    ]

    for filename, expected_type, expected_mime in test_cases:
        file_path = tmp_path / filename
        file_path.write_bytes(b"fake image content")

        result = parse_attachment_reference(f"Check @{file_path}")

        assert result.attachment is not None, f"Failed for {filename}"
        assert result.attachment.file_type == expected_type
        assert result.attachment.mime_type == expected_mime


# Test regex pattern directly
def test_attachment_pattern_matches_absolute():
    """Test regex pattern matches absolute paths."""
    match = ATTACHMENT_PATH_PATTERN.search("text @/path/to/file.pdf more")
    assert match is not None
    assert match.group(1) == "/path/to/file.pdf"


def test_attachment_pattern_matches_tilde():
    """Test regex pattern matches tilde paths."""
    match = ATTACHMENT_PATH_PATTERN.search("@~/docs/file.png")
    assert match is not None
    assert match.group(1) == "~/docs/file.png"


def test_attachment_pattern_no_match_bare_at():
    """Test regex pattern does not match bare @ symbol."""
    match = ATTACHMENT_PATH_PATTERN.search("email@domain.com")
    assert match is None


def test_attachment_pattern_stops_at_whitespace():
    """Test regex pattern stops at whitespace."""
    match = ATTACHMENT_PATH_PATTERN.search("@/path/file.pdf more text")
    assert match is not None
    assert match.group(1) == "/path/file.pdf"


# Test constants are properly defined
def test_supported_extensions_completeness():
    """Test all expected extensions are in SUPPORTED_EXTENSIONS."""
    expected = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp"}
    assert set(SUPPORTED_EXTENSIONS.keys()) == expected


def test_mime_types_completeness():
    """Test all AttachmentTypes have MIME types defined."""
    for attachment_type in AttachmentType:
        assert attachment_type in MIME_TYPES
