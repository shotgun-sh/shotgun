"""Integration tests for file attachment flow.

Tests the full flow from @path parsing through AgentManager.run() with multimodal content.
"""

import base64
from pathlib import Path

import pytest
from pydantic_ai.messages import DocumentUrl, ImageUrl

from shotgun.agents.config.models import ProviderType
from shotgun.attachments import (
    parse_attachment_reference,
    process_attachment,
)
from shotgun.attachments.models import AttachmentType


@pytest.fixture
def sample_png_file(tmp_path: Path) -> Path:
    """Create a sample PNG file for testing."""
    png_file = tmp_path / "test_image.png"
    # Write minimal PNG header + some content
    png_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    png_file.write_bytes(png_content)
    return png_file


@pytest.fixture
def sample_pdf_file(tmp_path: Path) -> Path:
    """Create a sample PDF file for testing."""
    pdf_file = tmp_path / "test_document.pdf"
    # Write minimal PDF content
    pdf_content = b"%PDF-1.4\n%test content for PDF"
    pdf_file.write_bytes(pdf_content)
    return pdf_file


@pytest.fixture
def large_file(tmp_path: Path) -> Path:
    """Create a file that exceeds provider size limits."""
    large_file = tmp_path / "large_file.pdf"
    # Create a file larger than Gemini's 4MB limit
    large_content = b"x" * (5 * 1024 * 1024)  # 5MB
    large_file.write_bytes(large_content)
    return large_file


def test_parse_png_attachment(sample_png_file: Path) -> None:
    """Test parsing @path for PNG image creates correct FileAttachment."""
    text = f"What is in this image? @{sample_png_file}"
    result = parse_attachment_reference(text)

    assert result.error_message is None
    assert result.attachment is not None
    assert result.attachment.file_type == AttachmentType.PNG
    assert result.attachment.file_name == "test_image.png"
    assert result.attachment.mime_type == "image/png"
    assert result.original_text == text  # @path preserved


def test_parse_pdf_attachment(sample_pdf_file: Path) -> None:
    """Test parsing @path for PDF creates correct FileAttachment."""
    text = f"Analyze @{sample_pdf_file} please"
    result = parse_attachment_reference(text)

    assert result.error_message is None
    assert result.attachment is not None
    assert result.attachment.file_type == AttachmentType.PDF
    assert result.attachment.file_name == "test_document.pdf"
    assert result.attachment.mime_type == "application/pdf"


@pytest.mark.asyncio
async def test_process_png_attachment_encodes_base64(sample_png_file: Path) -> None:
    """Test that processing PNG attachment encodes content to base64."""
    parse_result = parse_attachment_reference(f"Check @{sample_png_file}")
    assert parse_result.attachment is not None

    processed, error = await process_attachment(
        parse_result.attachment,
        ProviderType.OPENAI,
    )

    assert error is None
    assert processed.content_base64 is not None
    assert len(processed.content_base64) > 0
    # Verify it's valid base64
    decoded = base64.b64decode(processed.content_base64)
    assert decoded.startswith(b"\x89PNG")


@pytest.mark.asyncio
async def test_process_pdf_attachment_encodes_base64(sample_pdf_file: Path) -> None:
    """Test that processing PDF attachment encodes content to base64."""
    parse_result = parse_attachment_reference(f"Analyze @{sample_pdf_file}")
    assert parse_result.attachment is not None

    processed, error = await process_attachment(
        parse_result.attachment,
        ProviderType.ANTHROPIC,
    )

    assert error is None
    assert processed.content_base64 is not None
    # Verify it's valid base64
    decoded = base64.b64decode(processed.content_base64)
    assert decoded.startswith(b"%PDF")


def test_attachment_file_not_found() -> None:
    """Test error message for non-existent file."""
    result = parse_attachment_reference("Check @/nonexistent/file.pdf")

    assert result.attachment is None
    assert result.error_message is not None
    assert "not found" in result.error_message.lower()


def test_attachment_unsupported_type(tmp_path: Path) -> None:
    """Test error message for unsupported file type."""
    doc_file = tmp_path / "document.doc"
    doc_file.write_text("content")

    result = parse_attachment_reference(f"Check @{doc_file}")

    assert result.attachment is None
    assert result.error_message is not None
    assert "unsupported" in result.error_message.lower()


@pytest.mark.asyncio
async def test_attachment_size_limit_error(large_file: Path) -> None:
    """Test error message for file exceeding provider size limit."""
    parse_result = parse_attachment_reference(f"Check @{large_file}")
    assert parse_result.attachment is not None

    # Gemini has a 4MB limit, our file is 5MB
    processed, error = await process_attachment(
        parse_result.attachment,
        ProviderType.GOOGLE,
    )

    assert error is not None
    assert "exceeds" in error.lower()
    assert "limit" in error.lower()


def test_attachment_preserves_original_text(sample_pdf_file: Path) -> None:
    """Test that original text with @path is preserved."""
    original_text = f"Please analyze @{sample_pdf_file} and summarize the content."
    result = parse_attachment_reference(original_text)

    assert result.original_text == original_text
    assert f"@{sample_pdf_file}" in result.original_text


def test_no_attachment_returns_none() -> None:
    """Test that text without @path returns no attachment."""
    result = parse_attachment_reference("Just a regular message without attachment")

    assert result.attachment is None
    assert result.error_message is None
    assert result.original_text == "Just a regular message without attachment"


@pytest.mark.asyncio
async def test_image_attachment_creates_image_url(sample_png_file: Path) -> None:
    """Test that image attachment would create ImageUrl for multimodal content."""
    from shotgun.attachments import is_image_type

    parse_result = parse_attachment_reference(f"Check @{sample_png_file}")
    assert parse_result.attachment is not None

    processed, _ = await process_attachment(
        parse_result.attachment,
        ProviderType.OPENAI,
    )

    assert is_image_type(processed.file_type) is True

    # Verify ImageUrl can be constructed
    image_url = ImageUrl(
        url=f"data:{processed.mime_type};base64,{processed.content_base64}"
    )
    assert image_url.url.startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_pdf_attachment_creates_document_url(sample_pdf_file: Path) -> None:
    """Test that PDF attachment would create DocumentUrl for multimodal content."""
    from shotgun.attachments import is_image_type

    parse_result = parse_attachment_reference(f"Check @{sample_pdf_file}")
    assert parse_result.attachment is not None

    processed, _ = await process_attachment(
        parse_result.attachment,
        ProviderType.ANTHROPIC,
    )

    assert is_image_type(processed.file_type) is False

    # Verify DocumentUrl can be constructed
    doc_url = DocumentUrl(
        url=f"data:{processed.mime_type};base64,{processed.content_base64}"
    )
    assert doc_url.url.startswith("data:application/pdf;base64,")


@pytest.mark.asyncio
async def test_all_image_types_create_image_url(tmp_path: Path) -> None:
    """Test all image file types create ImageUrl."""
    from shotgun.attachments import is_image_type

    image_extensions = [".jpg", ".jpeg", ".gif", ".webp"]

    for ext in image_extensions:
        img_file = tmp_path / f"test{ext}"
        img_file.write_bytes(b"fake image content")

        parse_result = parse_attachment_reference(f"Check @{img_file}")
        assert parse_result.attachment is not None, f"Failed for {ext}"

        processed, _ = await process_attachment(
            parse_result.attachment,
            ProviderType.OPENAI,
        )

        assert is_image_type(processed.file_type) is True, f"Failed for {ext}"


@pytest.mark.asyncio
async def test_different_providers_have_different_limits(tmp_path: Path) -> None:
    """Test that different providers have different file size limits."""
    from shotgun.attachments.processor import (
        get_provider_size_limit,
    )

    # Verify known limits
    assert get_provider_size_limit(ProviderType.OPENAI) == 20 * 1024 * 1024  # 20MB
    assert get_provider_size_limit(ProviderType.ANTHROPIC) == 32 * 1024 * 1024  # 32MB
    assert get_provider_size_limit(ProviderType.GOOGLE) == 4 * 1024 * 1024  # 4MB
