"""Pydantic models for spec CLI commands."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class PullSource(StrEnum):
    """Source of spec pull operation for analytics."""

    CLI = "cli"
    TUI = "tui"


class PullPhase(StrEnum):
    """Phases during spec pull operation for analytics."""

    STARTING = "starting"
    FETCHING = "fetching"
    BACKUP = "backup"
    DOWNLOADING = "downloading"
    FINALIZING = "finalizing"


class SpecMeta(BaseModel):
    """Metadata stored in .shotgun/meta.json after pulling a spec.

    This file tracks the source of the local spec files and is used
    by the TUI to display version information and enable future sync operations.
    """

    version_id: str = Field(description="Pulled version UUID")
    spec_id: str = Field(description="Spec UUID")
    spec_name: str = Field(description="Spec name at time of pull")
    workspace_id: str = Field(description="Workspace UUID")
    is_latest: bool = Field(
        description="Whether this was the latest version when pulled"
    )
    pulled_at: datetime = Field(description="Timestamp when spec was pulled (UTC)")
    backup_path: str | None = Field(
        default=None,
        description="Path where previous .shotgun/ files were backed up",
    )
    web_url: str | None = Field(
        default=None,
        description="URL to view this version in the web UI",
    )
