"""Pydantic models for shared specs TUI screens."""

from enum import StrEnum

from pydantic import BaseModel


class ShareSpecsAction(StrEnum):
    """Actions from share specs dialog."""

    CREATE = "create"
    ADD_VERSION = "add_version"


class UploadScreenResult(BaseModel):
    """Result from UploadProgressScreen.

    Attributes:
        success: Whether the upload completed successfully
        web_url: URL to view the spec version (on success)
        cancelled: Whether the upload was cancelled
    """

    success: bool
    web_url: str | None = None
    cancelled: bool = False


class ShareSpecsResult(BaseModel):
    """Result from ShareSpecsDialog.

    Attributes:
        action: CREATE to create new spec, ADD_VERSION to add to existing, None if cancelled
        workspace_id: Workspace ID (fetched by dialog)
        spec_id: Spec ID if adding version to existing spec
        spec_name: Spec name if adding version to existing spec
    """

    action: ShareSpecsAction | None = None
    workspace_id: str | None = None
    spec_id: str | None = None
    spec_name: str | None = None


class CreateSpecResult(BaseModel):
    """Result from CreateSpecDialog.

    Attributes:
        name: Spec name (required)
        description: Optional description
        is_public: Whether spec should be public (default: False)
    """

    name: str
    description: str | None = None
    is_public: bool = False
