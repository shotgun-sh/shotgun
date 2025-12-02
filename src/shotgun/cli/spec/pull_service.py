"""Shared spec pull service for CLI and TUI."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from shotgun.logging_config import get_logger
from shotgun.shotgun_web.specs_client import SpecsClient
from shotgun.shotgun_web.supabase_client import download_file_from_url

from .backup import clear_shotgun_dir, create_backup
from .models import SpecMeta

logger = get_logger(__name__)


@dataclass
class PullProgress:
    """Progress update during spec pull."""

    phase: str
    file_index: int | None = None
    total_files: int | None = None
    current_file: str | None = None


@dataclass
class PullResult:
    """Result of a spec pull operation."""

    success: bool
    spec_name: str | None = None
    file_count: int = 0
    backup_path: str | None = None
    web_url: str | None = None
    error: str | None = None


class CancelledError(Exception):
    """Raised when pull is cancelled."""


class SpecPullService:
    """Service for pulling spec versions from cloud."""

    def __init__(self) -> None:
        self._client = SpecsClient()

    async def pull_version(
        self,
        version_id: str,
        shotgun_dir: Path,
        on_progress: Callable[[PullProgress], None] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> PullResult:
        """Pull a spec version to the local directory.

        Args:
            version_id: The version UUID to pull
            shotgun_dir: Target directory (typically .shotgun/)
            on_progress: Optional callback for progress updates
            is_cancelled: Optional callback to check if cancelled

        Returns:
            PullResult with success status and details
        """

        def report(
            phase: str,
            file_index: int | None = None,
            total_files: int | None = None,
            current_file: str | None = None,
        ) -> None:
            if on_progress:
                on_progress(
                    PullProgress(
                        phase=phase,
                        file_index=file_index,
                        total_files=total_files,
                        current_file=current_file,
                    )
                )

        def check_cancelled() -> None:
            if is_cancelled and is_cancelled():
                raise CancelledError()

        # Phase 1: Fetch version metadata
        report("Fetching version info...")
        check_cancelled()

        response = await self._client.get_version_with_files(version_id)
        spec_name = response.spec_name
        files = response.files

        if not files:
            return PullResult(
                success=False,
                spec_name=spec_name,
                error="No files in this version.",
            )

        # Phase 2: Backup existing content
        backup_path: str | None = None
        if shotgun_dir.exists():
            report("Backing up existing files...")
            check_cancelled()

            backup_path = await create_backup(shotgun_dir)
            if backup_path:
                clear_shotgun_dir(shotgun_dir)

        # Ensure directory exists
        shotgun_dir.mkdir(parents=True, exist_ok=True)

        # Phase 3: Download files
        total_files = len(files)
        for idx, file_info in enumerate(files):
            check_cancelled()

            report(
                f"Downloading files ({idx + 1}/{total_files})...",
                file_index=idx,
                total_files=total_files,
                current_file=file_info.relative_path,
            )

            if not file_info.download_url:
                logger.warning(
                    "Skipping file without download URL: %s",
                    file_info.relative_path,
                )
                continue

            content = await download_file_from_url(file_info.download_url)

            local_path = shotgun_dir / file_info.relative_path
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(content)

        # Phase 4: Write meta.json
        report("Finalizing...")
        check_cancelled()

        meta = SpecMeta(
            version_id=response.version.id,
            spec_id=response.spec_id,
            spec_name=response.spec_name,
            workspace_id=response.workspace_id,
            is_latest=response.version.is_latest,
            pulled_at=datetime.now(timezone.utc),
            backup_path=backup_path,
            web_url=response.web_url,
        )
        meta_path = shotgun_dir / "meta.json"
        meta_path.write_text(meta.model_dump_json(indent=2))

        return PullResult(
            success=True,
            spec_name=spec_name,
            file_count=total_files,
            backup_path=backup_path,
            web_url=response.web_url,
        )
