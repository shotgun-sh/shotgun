"""Type contracts for file attachment support.

These models define the shape of file attachment data throughout the system.
"""

from enum import StrEnum
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, Field


class AttachmentType(StrEnum):
    """Supported attachment file types."""

    PDF = "pdf"
    PNG = "png"
    JPG = "jpg"
    JPEG = "jpeg"
    GIF = "gif"
    WEBP = "webp"


class FileAttachment(BaseModel):
    """Represents a file attachment pending submission.

    This model tracks attachment state from parsing through submission.
    """

    file_path: Path = Field(..., description="Absolute path to the attached file")
    file_name: str = Field(..., description="Display name (basename)")
    file_type: AttachmentType = Field(..., description="File type enum")
    file_size_bytes: int = Field(..., description="File size in bytes")
    content_base64: str | None = Field(
        default=None, description="Base64-encoded content (populated on submission)"
    )
    mime_type: str = Field(..., description="MIME type for API submission")


class AttachmentHint(BaseModel):
    """Hint message variant for displaying attachments in chat history.

    Used by UIHint system to render attachment indicators in the conversation.
    """

    filename: str = Field(..., description="Display filename")
    file_type: AttachmentType = Field(..., description="File type for icon selection")
    file_size_display: str = Field(
        ..., description="Human-readable size (e.g., '2.5 MB')"
    )
    kind: Literal["attachment"] = "attachment"


class AttachmentBarState(BaseModel):
    """State model for the AttachmentBar widget.

    Tracks current attachment for display above the input.
    """

    attachment: FileAttachment | None = Field(
        default=None, description="Currently attached file, or None if no attachment"
    )


class AttachmentParseResult(BaseModel):
    """Result of parsing @path references from user input.

    Contains the original text (with @path preserved) and any successfully
    parsed attachment. The @path reference is kept in the text so the LLM
    knows which file is being referenced.
    """

    original_text: str = Field(
        ...,
        description="Original input text with @path reference preserved for LLM context",
    )
    attachment: FileAttachment | None = Field(
        default=None, description="Parsed attachment, or None if no valid @path found"
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if parsing failed (file not found, unsupported type, etc.)",
    )


class AttachmentCapability(Protocol):
    """Protocol for checking provider attachment capabilities.

    Note: All three providers (OpenAI, Anthropic, Gemini) support both images
    and PDFs. OpenAI requires vision-capable models (GPT-4o, GPT-4o mini,
    GPT-5.2) for PDF support.
    """

    @property
    def supports_images(self) -> bool:
        """Whether provider supports image attachments."""
        ...

    @property
    def supports_pdf(self) -> bool:
        """Whether provider supports native PDF attachments."""
        ...

    @property
    def max_file_size_bytes(self) -> int:
        """Maximum file size in bytes for this provider."""
        ...
