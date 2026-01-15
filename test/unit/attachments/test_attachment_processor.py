"""Unit tests for attachment processor module."""

import base64
from pathlib import Path

import pytest

from shotgun.agents.config.models import ProviderType
from shotgun.attachments.models import AttachmentType, FileAttachment
from shotgun.attachments.processor import (
    DEFAULT_SIZE_LIMIT,
    PROVIDER_SIZE_LIMITS,
    create_attachment_hint_display,
    encode_file_to_base64,
    format_file_size,
    get_attachment_icon,
    get_provider_size_limit,
    process_attachment,
    validate_file_size,
)


# Test get_provider_size_limit
def test_get_provider_size_limit_openai():
    """Test OpenAI size limit is 20MB."""
    limit = get_provider_size_limit(ProviderType.OPENAI)
    assert limit == 20 * 1024 * 1024


def test_get_provider_size_limit_anthropic():
    """Test Anthropic size limit is 32MB."""
    limit = get_provider_size_limit(ProviderType.ANTHROPIC)
    assert limit == 32 * 1024 * 1024


def test_get_provider_size_limit_google():
    """Test Google size limit is 4MB."""
    limit = get_provider_size_limit(ProviderType.GOOGLE)
    assert limit == 4 * 1024 * 1024


# Test format_file_size
def test_format_file_size_bytes():
    """Test formatting small sizes in bytes."""
    assert format_file_size(512) == "512 B"
    assert format_file_size(0) == "0 B"
    assert format_file_size(1023) == "1023 B"


def test_format_file_size_kilobytes():
    """Test formatting sizes in kilobytes."""
    assert format_file_size(1024) == "1.0 KB"
    assert format_file_size(1536) == "1.5 KB"
    assert format_file_size(512 * 1024) == "512.0 KB"


def test_format_file_size_megabytes():
    """Test formatting sizes in megabytes."""
    assert format_file_size(1024 * 1024) == "1.0 MB"
    assert format_file_size(int(2.5 * 1024 * 1024)) == "2.5 MB"
    assert format_file_size(20 * 1024 * 1024) == "20.0 MB"


# Test validate_file_size
def test_validate_file_size_within_limit():
    """Test validation passes for file within limit."""
    attachment = FileAttachment(
        file_path=Path("/test.pdf"),
        file_name="test.pdf",
        file_type=AttachmentType.PDF,
        file_size_bytes=1024 * 1024,  # 1MB
        mime_type="application/pdf",
    )

    is_valid, error = validate_file_size(attachment, ProviderType.OPENAI)
    assert is_valid is True
    assert error is None


def test_validate_file_size_exceeds_openai_limit():
    """Test validation fails for file exceeding OpenAI limit."""
    attachment = FileAttachment(
        file_path=Path("/large.pdf"),
        file_name="large.pdf",
        file_type=AttachmentType.PDF,
        file_size_bytes=25 * 1024 * 1024,  # 25MB
        mime_type="application/pdf",
    )

    is_valid, error = validate_file_size(attachment, ProviderType.OPENAI)
    assert is_valid is False
    assert error is not None
    assert "25.0 MB" in error
    assert "20.0 MB" in error


def test_validate_file_size_exceeds_google_limit():
    """Test validation fails for file exceeding Google limit."""
    attachment = FileAttachment(
        file_path=Path("/medium.pdf"),
        file_name="medium.pdf",
        file_type=AttachmentType.PDF,
        file_size_bytes=5 * 1024 * 1024,  # 5MB
        mime_type="application/pdf",
    )

    is_valid, error = validate_file_size(attachment, ProviderType.GOOGLE)
    assert is_valid is False
    assert error is not None
    assert "5.0 MB" in error
    assert "4.0 MB" in error


def test_validate_file_size_at_exact_limit():
    """Test validation passes at exact limit."""
    attachment = FileAttachment(
        file_path=Path("/exact.pdf"),
        file_name="exact.pdf",
        file_type=AttachmentType.PDF,
        file_size_bytes=4 * 1024 * 1024,  # Exactly 4MB
        mime_type="application/pdf",
    )

    is_valid, error = validate_file_size(attachment, ProviderType.GOOGLE)
    assert is_valid is True
    assert error is None


def test_validate_file_size_anthropic():
    """Test validation with Anthropic's larger limit."""
    attachment = FileAttachment(
        file_path=Path("/large.pdf"),
        file_name="large.pdf",
        file_type=AttachmentType.PDF,
        file_size_bytes=30 * 1024 * 1024,  # 30MB
        mime_type="application/pdf",
    )

    # Should pass for Anthropic (32MB limit)
    is_valid, error = validate_file_size(attachment, ProviderType.ANTHROPIC)
    assert is_valid is True
    assert error is None

    # Should fail for OpenAI (20MB limit)
    is_valid, error = validate_file_size(attachment, ProviderType.OPENAI)
    assert is_valid is False


# Test encode_file_to_base64
@pytest.mark.asyncio
async def test_encode_file_to_base64_success(tmp_path):
    """Test successful file encoding."""
    test_file = tmp_path / "test.txt"
    content = b"Hello, World!"
    test_file.write_bytes(content)

    result = await encode_file_to_base64(test_file)

    assert result == base64.b64encode(content).decode("utf-8")


@pytest.mark.asyncio
async def test_encode_file_to_base64_binary_file(tmp_path):
    """Test encoding binary file (like PDF)."""
    test_file = tmp_path / "test.pdf"
    content = b"%PDF-1.4\x00\x01\x02\x03binary content"
    test_file.write_bytes(content)

    result = await encode_file_to_base64(test_file)

    # Verify we can decode it back
    decoded = base64.b64decode(result)
    assert decoded == content


@pytest.mark.asyncio
async def test_encode_file_to_base64_file_not_found():
    """Test encoding non-existent file raises error."""
    with pytest.raises(FileNotFoundError):
        await encode_file_to_base64(Path("/nonexistent/file.pdf"))


@pytest.mark.asyncio
async def test_encode_file_to_base64_empty_file(tmp_path):
    """Test encoding empty file."""
    test_file = tmp_path / "empty.txt"
    test_file.write_bytes(b"")

    result = await encode_file_to_base64(test_file)

    assert result == ""  # base64 of empty content


# Test process_attachment
@pytest.mark.asyncio
async def test_process_attachment_success(tmp_path):
    """Test successful attachment processing."""
    test_file = tmp_path / "document.pdf"
    content = b"%PDF-1.4 test content"
    test_file.write_bytes(content)

    attachment = FileAttachment(
        file_path=test_file,
        file_name="document.pdf",
        file_type=AttachmentType.PDF,
        file_size_bytes=len(content),
        mime_type="application/pdf",
    )

    result, error = await process_attachment(attachment, ProviderType.OPENAI)

    assert error is None
    assert result.content_base64 is not None
    assert result.content_base64 == base64.b64encode(content).decode("utf-8")
    # Original fields preserved
    assert result.file_name == "document.pdf"
    assert result.file_type == AttachmentType.PDF


@pytest.mark.asyncio
async def test_process_attachment_size_validation_fails(tmp_path):
    """Test processing fails when file exceeds size limit."""
    test_file = tmp_path / "large.pdf"
    # Create a file larger than Google's 4MB limit
    content = b"x" * (5 * 1024 * 1024)
    test_file.write_bytes(content)

    attachment = FileAttachment(
        file_path=test_file,
        file_name="large.pdf",
        file_type=AttachmentType.PDF,
        file_size_bytes=len(content),
        mime_type="application/pdf",
    )

    result, error = await process_attachment(attachment, ProviderType.GOOGLE)

    assert error is not None
    assert "File too large" in error
    assert result.content_base64 is None  # Not encoded


@pytest.mark.asyncio
async def test_process_attachment_file_read_error():
    """Test processing handles file read errors gracefully."""
    attachment = FileAttachment(
        file_path=Path("/nonexistent/file.pdf"),
        file_name="missing.pdf",
        file_type=AttachmentType.PDF,
        file_size_bytes=1024,
        mime_type="application/pdf",
    )

    result, error = await process_attachment(attachment, ProviderType.OPENAI)

    assert error is not None
    assert result.content_base64 is None


@pytest.mark.asyncio
async def test_process_attachment_preserves_metadata(tmp_path):
    """Test that processing preserves all metadata fields."""
    test_file = tmp_path / "image.png"
    content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    test_file.write_bytes(content)

    attachment = FileAttachment(
        file_path=test_file,
        file_name="image.png",
        file_type=AttachmentType.PNG,
        file_size_bytes=len(content),
        mime_type="image/png",
    )

    result, error = await process_attachment(attachment, ProviderType.ANTHROPIC)

    assert error is None
    assert result.file_path == test_file
    assert result.file_name == "image.png"
    assert result.file_type == AttachmentType.PNG
    assert result.file_size_bytes == len(content)
    assert result.mime_type == "image/png"


# Test create_attachment_hint_display
def test_create_attachment_hint_display_pdf():
    """Test display string for PDF attachment."""
    attachment = FileAttachment(
        file_path=Path("/test/document.pdf"),
        file_name="document.pdf",
        file_type=AttachmentType.PDF,
        file_size_bytes=int(2.5 * 1024 * 1024),
        mime_type="application/pdf",
    )

    display = create_attachment_hint_display(attachment)

    assert "document.pdf" in display
    assert "2.5 MB" in display


def test_create_attachment_hint_display_image():
    """Test display string for image attachment."""
    attachment = FileAttachment(
        file_path=Path("/test/screenshot.png"),
        file_name="screenshot.png",
        file_type=AttachmentType.PNG,
        file_size_bytes=512 * 1024,
        mime_type="image/png",
    )

    display = create_attachment_hint_display(attachment)

    assert "screenshot.png" in display
    assert "512.0 KB" in display


def test_create_attachment_hint_display_small_file():
    """Test display string for small file."""
    attachment = FileAttachment(
        file_path=Path("/test/tiny.gif"),
        file_name="tiny.gif",
        file_type=AttachmentType.GIF,
        file_size_bytes=256,
        mime_type="image/gif",
    )

    display = create_attachment_hint_display(attachment)

    assert "tiny.gif" in display
    assert "256 B" in display


# Test get_attachment_icon
def test_get_attachment_icon_pdf():
    """Test icon for PDF is document emoji."""
    icon = get_attachment_icon(AttachmentType.PDF)
    assert icon == "\U0001f4c4"  # document emoji


def test_get_attachment_icon_images():
    """Test icon for images is picture emoji."""
    image_types = [
        AttachmentType.PNG,
        AttachmentType.JPG,
        AttachmentType.JPEG,
        AttachmentType.GIF,
        AttachmentType.WEBP,
    ]
    for img_type in image_types:
        icon = get_attachment_icon(img_type)
        assert icon == "\U0001f5bc\ufe0f"  # framed picture emoji


# Test provider size limits are correct
def test_provider_limits_defined():
    """Test all providers have size limits defined."""
    assert ProviderType.OPENAI in PROVIDER_SIZE_LIMITS
    assert ProviderType.ANTHROPIC in PROVIDER_SIZE_LIMITS
    assert ProviderType.GOOGLE in PROVIDER_SIZE_LIMITS


def test_default_size_limit_is_most_restrictive():
    """Test default limit is the most restrictive (Google's 4MB)."""
    assert DEFAULT_SIZE_LIMIT == 4 * 1024 * 1024
    assert DEFAULT_SIZE_LIMIT == min(PROVIDER_SIZE_LIMITS.values())


def test_provider_limits_values():
    """Test provider limits have expected values."""
    assert PROVIDER_SIZE_LIMITS[ProviderType.OPENAI] == 20 * 1024 * 1024
    assert PROVIDER_SIZE_LIMITS[ProviderType.ANTHROPIC] == 32 * 1024 * 1024
    assert PROVIDER_SIZE_LIMITS[ProviderType.GOOGLE] == 4 * 1024 * 1024


# Test error message formats match specification
def test_validate_file_size_error_message_format():
    """Test file size error message matches specification format."""
    attachment = FileAttachment(
        file_path=Path("/large.pdf"),
        file_name="large.pdf",
        file_type=AttachmentType.PDF,
        file_size_bytes=45 * 1024 * 1024,  # 45MB
        mime_type="application/pdf",
    )
    is_valid, error = validate_file_size(attachment, ProviderType.ANTHROPIC)
    assert is_valid is False
    assert error is not None
    # Format: "⚠️ File too large: 45.0 MB (max: 32.0 MB for Anthropic)"
    assert error.startswith("⚠️ File too large:")
    assert "45.0 MB" in error
    assert "32.0 MB" in error
    assert "Anthropic" in error


def test_validate_file_size_error_message_format_openai():
    """Test file size error message format for OpenAI."""
    attachment = FileAttachment(
        file_path=Path("/large.png"),
        file_name="large.png",
        file_type=AttachmentType.PNG,
        file_size_bytes=25 * 1024 * 1024,  # 25MB
        mime_type="image/png",
    )
    is_valid, error = validate_file_size(attachment, ProviderType.OPENAI)
    assert is_valid is False
    assert error is not None
    assert error.startswith("⚠️ File too large:")
    assert "25.0 MB" in error
    assert "20.0 MB" in error
    assert "Openai" in error


def test_validate_file_size_error_message_format_google():
    """Test file size error message format for Google."""
    attachment = FileAttachment(
        file_path=Path("/medium.pdf"),
        file_name="medium.pdf",
        file_type=AttachmentType.PDF,
        file_size_bytes=5 * 1024 * 1024,  # 5MB
        mime_type="application/pdf",
    )
    is_valid, error = validate_file_size(attachment, ProviderType.GOOGLE)
    assert is_valid is False
    assert error is not None
    assert error.startswith("⚠️ File too large:")
    assert "5.0 MB" in error
    assert "4.0 MB" in error
    assert "Google" in error
