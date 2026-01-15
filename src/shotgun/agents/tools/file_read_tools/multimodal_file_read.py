"""Multimodal file reading tool that returns BinaryContent for the agent to analyze."""

from pathlib import Path

import pymupdf  # type: ignore[import-untyped]
from pydantic import BaseModel, Field
from pydantic_ai import BinaryContent, RunContext, ToolReturn

from shotgun.agents.models import AgentDeps
from shotgun.agents.tools.registry import ToolCategory, register_tool
from shotgun.logging_config import get_logger

logger = get_logger(__name__)

# Maximum text length to extract from PDFs (to avoid huge responses)
MAX_TEXT_LENGTH = 50_000

# MIME type mapping for supported file types
MIME_TYPES: dict[str, str] = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

# Maximum file size for multimodal reading (32MB - Anthropic's limit)
MAX_FILE_SIZE_BYTES = 32 * 1024 * 1024


class MultimodalFileReadResult(BaseModel):
    """Result from multimodal file read."""

    success: bool = Field(description="Whether the file was successfully read")
    file_path: str = Field(description="The absolute path to the file")
    file_name: str = Field(default="", description="The file name")
    file_size_bytes: int = Field(default=0, description="File size in bytes")
    mime_type: str = Field(default="", description="MIME type of the file")
    error: str | None = Field(default=None, description="Error message if failed")

    def __str__(self) -> str:
        if not self.success:
            return f"Error reading file: {self.error}"
        return f"Read file: {self.file_name} ({self.file_size_bytes} bytes, {self.mime_type})"


def _get_mime_type(file_path: Path) -> str | None:
    """Get MIME type for a file based on extension."""
    suffix = file_path.suffix.lower()
    return MIME_TYPES.get(suffix)


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def _extract_pdf_text(path: Path) -> tuple[str, int]:
    """Extract text from a PDF file using PyMuPDF.

    Args:
        path: Path to the PDF file

    Returns:
        Tuple of (extracted_text, page_count)
    """
    try:
        doc = pymupdf.open(path)
        page_count = len(doc)
        text_parts = []

        for page_num, page in enumerate(doc):
            page_text = page.get_text()
            if page_text.strip():
                text_parts.append(f"--- Page {page_num + 1} ---\n{page_text}")

        doc.close()

        full_text = "\n\n".join(text_parts)

        # Truncate if too long
        if len(full_text) > MAX_TEXT_LENGTH:
            full_text = full_text[:MAX_TEXT_LENGTH] + "\n\n[... text truncated ...]"

        return full_text, page_count
    except Exception as e:
        logger.warning("Failed to extract PDF text: %s", e)
        return "", 0


@register_tool(
    category=ToolCategory.CODEBASE_UNDERSTANDING,
    display_text="Reading file (multimodal)",
    key_arg="file_path",
)
async def multimodal_file_read(
    ctx: RunContext[AgentDeps],
    file_path: str,
) -> ToolReturn:
    """Read a PDF or image file and return its content for visual analysis.

    This tool reads binary files (PDFs, images) and returns them as multimodal
    content so you can see and analyze the file contents directly.

    Args:
        ctx: RunContext containing AgentDeps
        file_path: Path to the file (absolute or relative to CWD)

    Returns:
        ToolReturn with BinaryContent for the agent to analyze visually
    """
    logger.debug("Reading multimodal file: %s", file_path)

    try:
        # Resolve the path
        path = Path(file_path).expanduser().resolve()

        # Check if file exists
        if not path.exists():
            error_result = MultimodalFileReadResult(
                success=False,
                file_path=str(path),
                error=f"File not found: {file_path}",
            )
            return ToolReturn(return_value=str(error_result))

        if path.is_dir():
            error_result = MultimodalFileReadResult(
                success=False,
                file_path=str(path),
                error=f"'{file_path}' is a directory, not a file",
            )
            return ToolReturn(return_value=str(error_result))

        # Check MIME type
        mime_type = _get_mime_type(path)
        if mime_type is None:
            supported = ", ".join(MIME_TYPES.keys())
            error_result = MultimodalFileReadResult(
                success=False,
                file_path=str(path),
                error=f"Unsupported file type: {path.suffix}. Supported: {supported}",
            )
            return ToolReturn(return_value=str(error_result))

        # Check file size
        file_size = path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            error_result = MultimodalFileReadResult(
                success=False,
                file_path=str(path),
                file_size_bytes=file_size,
                error=f"File too large: {_format_file_size(file_size)} (max: {_format_file_size(MAX_FILE_SIZE_BYTES)})",
            )
            return ToolReturn(return_value=str(error_result))

        # Read file bytes
        content = path.read_bytes()

        logger.debug(
            "Successfully read multimodal file: %s (%d bytes, %s)",
            path.name,
            file_size,
            mime_type,
        )

        # Create success result
        result = MultimodalFileReadResult(
            success=True,
            file_path=str(path),
            file_name=path.name,
            file_size_bytes=file_size,
            mime_type=mime_type,
        )

        # Return with BinaryContent so the agent can see the file
        return ToolReturn(
            return_value=str(result),
            content=[
                f"Contents of {path.name} ({_format_file_size(file_size)}):",
                BinaryContent(data=content, media_type=mime_type),
            ],
        )

    except PermissionError:
        error_result = MultimodalFileReadResult(
            success=False,
            file_path=file_path,
            error=f"Permission denied: {file_path}",
        )
        return ToolReturn(return_value=str(error_result))

    except Exception as e:
        logger.error("Error reading multimodal file: %s", str(e))
        error_result = MultimodalFileReadResult(
            success=False,
            file_path=file_path,
            error=f"Error reading file: {str(e)}",
        )
        return ToolReturn(return_value=str(error_result))
