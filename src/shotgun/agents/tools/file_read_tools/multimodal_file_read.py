"""Multimodal file reading tool that verifies files exist and returns paths.

This tool verifies PDFs/images exist and returns their paths for the agent
to include in `files_found`. The Router then loads these via `file_requests`.
"""

from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_ai import RunContext, ToolReturn

from shotgun.agents.models import AgentDeps
from shotgun.agents.tools.registry import ToolCategory, register_tool
from shotgun.logging_config import get_logger

logger = get_logger(__name__)

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

    success: bool = Field(description="Whether the file was successfully found")
    file_path: str = Field(description="The absolute path to the file")
    file_name: str = Field(default="", description="The file name")
    file_size_bytes: int = Field(default=0, description="File size in bytes")
    mime_type: str = Field(default="", description="MIME type of the file")
    error: str | None = Field(default=None, description="Error message if failed")

    def __str__(self) -> str:
        if not self.success:
            return f"Error: {self.error}"
        return (
            f"Found: {self.file_name} ({self.file_size_bytes} bytes, {self.mime_type})"
        )


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


# Image file extensions
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


@register_tool(
    category=ToolCategory.CODEBASE_UNDERSTANDING,
    display_text="Reading file (multimodal)",
    key_arg="file_path",
)
async def multimodal_file_read(
    ctx: RunContext[AgentDeps],
    file_path: str,
) -> ToolReturn:
    """Verify a PDF or image file exists and return its path.

    This tool checks that the file exists and is a supported type (PDF, image),
    then returns the absolute path. Include this path in your `files_found`
    response so the Router can load it for visual analysis.

    Args:
        ctx: RunContext containing AgentDeps
        file_path: Path to the file (absolute or relative to CWD)

    Returns:
        ToolReturn with file info and absolute path
    """
    logger.debug("Checking multimodal file: %s", file_path)

    # Check model capabilities before proceeding
    model_config = ctx.deps.llm_model
    path = Path(file_path)
    suffix = path.suffix.lower()

    # Check PDF support
    if suffix == ".pdf" and not model_config.supports_pdf:
        return ToolReturn(
            return_value=f"PDF files are not supported by this model ({model_config.name_str}). "
            "Please ask the user to copy/paste relevant text content instead."
        )

    # Check image support
    if suffix in IMAGE_EXTENSIONS and not model_config.supports_images:
        return ToolReturn(
            return_value=f"Image files are not supported by this model ({model_config.name_str}). "
            "Please ask the user to describe the image content instead."
        )

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

        logger.debug(
            "Found multimodal file: %s (%s, %s)",
            path.name,
            _format_file_size(file_size),
            mime_type,
        )

        # Return file info with absolute path
        file_type = "PDF" if mime_type == "application/pdf" else "Image"
        summary = f"""{file_type} found: {path.name}
Size: {_format_file_size(file_size)}
Type: {mime_type}
Absolute path: {path}

IMPORTANT: Include the absolute path above in your `files_found` response field.
The Router will then be able to load and analyze this file's visual content."""

        return ToolReturn(return_value=summary)

    except PermissionError:
        error_result = MultimodalFileReadResult(
            success=False,
            file_path=file_path,
            error=f"Permission denied: {file_path}",
        )
        return ToolReturn(return_value=str(error_result))

    except Exception as e:
        logger.error("Error checking multimodal file: %s", str(e))
        error_result = MultimodalFileReadResult(
            success=False,
            file_path=file_path,
            error=f"Error: {str(e)}",
        )
        return ToolReturn(return_value=str(error_result))
