"""Multimodal file reading tool that verifies files exist and returns paths.

This tool verifies PDFs, images, and text files exist and returns their paths
for the agent to include in `files_found`. The Router then loads these via
`file_requests`.
"""

from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_ai import RunContext, ToolReturn

from shotgun.agents.constants import (
    MAX_BINARY_FILE_SIZE_BYTES,
    MAX_TEXT_FILE_SIZE_BYTES,
    MIME_TYPES,
    is_binary_extension,
    is_supported_extension,
    is_text_extension,
)
from shotgun.agents.models import AgentDeps
from shotgun.agents.tools.registry import ToolCategory, register_tool
from shotgun.logging_config import get_logger

logger = get_logger(__name__)


class MultimodalFileReadResult(BaseModel):
    """Result from multimodal file read."""

    success: bool = Field(description="Whether the file was successfully found")
    file_path: str = Field(description="The absolute path to the file")
    file_name: str = Field(default="", description="The file name")
    file_size_bytes: int = Field(default=0, description="File size in bytes")
    mime_type: str = Field(default="", description="MIME type of the file (for binary)")
    file_type: str = Field(
        default="", description="File type category (PDF, Image, Text)"
    )
    error: str | None = Field(default=None, description="Error message if failed")

    def __str__(self) -> str:
        if not self.success:
            return f"Error: {self.error}"
        type_info = self.mime_type if self.mime_type else self.file_type
        return f"Found: {self.file_name} ({self.file_size_bytes} bytes, {type_info})"


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


@register_tool(
    category=ToolCategory.CODEBASE_UNDERSTANDING,
    display_text="Reading file (multimodal)",
    key_arg="file_path",
)
async def multimodal_file_read(
    ctx: RunContext[AgentDeps],
    file_path: str,
) -> ToolReturn:
    """Verify a PDF, image, or text file exists and return its path.

    This tool checks that the file exists and is a supported type (PDF, image,
    or text file), then returns the absolute path. Include this path in your
    `files_found` response so the Router can load it via file_requests.

    Supported file types:
    - Binary: .pdf, .png, .jpg, .jpeg, .gif, .webp
    - Text: .md, .txt, .rst, .json, .yaml, .yml, .toml, .xml, .csv,
            .html, .css, .js, .ts, .jsx, .tsx, .py, .java, .go, .rs,
            .rb, .php, .sh, .bash, .sql, .ini, .cfg, .conf, .env, .log

    Args:
        ctx: RunContext containing AgentDeps
        file_path: Path to the file (absolute or relative to CWD)

    Returns:
        ToolReturn with file info and absolute path
    """
    logger.debug("Checking multimodal file: %s", file_path)

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

        # Check if file type is supported
        suffix = path.suffix.lower()
        if not is_supported_extension(suffix):
            error_result = MultimodalFileReadResult(
                success=False,
                file_path=str(path),
                error=f"Unsupported file type: {suffix}. Use file_requests for supported types.",
            )
            return ToolReturn(return_value=str(error_result))

        # Get file size
        file_size = path.stat().st_size

        # Determine file type and check size limits
        if is_binary_extension(suffix):
            # Binary file (PDF, image)
            mime_type = MIME_TYPES.get(suffix, "")
            file_type = "PDF" if mime_type == "application/pdf" else "Image"
            max_size = MAX_BINARY_FILE_SIZE_BYTES

            if file_size > max_size:
                error_result = MultimodalFileReadResult(
                    success=False,
                    file_path=str(path),
                    file_size_bytes=file_size,
                    error=f"File too large: {_format_file_size(file_size)} (max: {_format_file_size(max_size)})",
                )
                return ToolReturn(return_value=str(error_result))

            logger.debug(
                "Found binary file: %s (%s, %s)",
                path.name,
                _format_file_size(file_size),
                mime_type,
            )

            summary = f"""{file_type} found: {path.name}
Size: {_format_file_size(file_size)}
Type: {mime_type}
Absolute path: {path}

IMPORTANT: Include the absolute path above in your `files_found` response field.
The Router will then be able to load and analyze this file's content."""

        elif is_text_extension(suffix):
            # Text file
            file_type = "Text"
            max_size = MAX_TEXT_FILE_SIZE_BYTES

            if file_size > max_size:
                error_result = MultimodalFileReadResult(
                    success=False,
                    file_path=str(path),
                    file_size_bytes=file_size,
                    error=f"File too large: {_format_file_size(file_size)} (max: {_format_file_size(max_size)})",
                )
                return ToolReturn(return_value=str(error_result))

            logger.debug(
                "Found text file: %s (%s)",
                path.name,
                _format_file_size(file_size),
            )

            summary = f"""Text file found: {path.name}
Size: {_format_file_size(file_size)}
Extension: {suffix}
Absolute path: {path}

IMPORTANT: Include the absolute path above in your `files_found` response field.
The Router will then be able to load and analyze this file's content."""

        else:
            # Should not reach here due to is_supported_extension check
            error_result = MultimodalFileReadResult(
                success=False,
                file_path=str(path),
                error=f"Unsupported file type: {suffix}",
            )
            return ToolReturn(return_value=str(error_result))

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
