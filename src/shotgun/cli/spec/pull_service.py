"""Shared spec pull service for CLI and TUI."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from shotgun.logging_config import get_logger
from shotgun.posthog_telemetry import track_event
from shotgun.shotgun_web.specs_client import SpecsClient
from shotgun.shotgun_web.supabase_client import download_file_from_url

from .backup import clear_shotgun_dir, create_backup
from .models import PullPhase, PullSource, SpecMeta

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
        source: PullSource = PullSource.CLI,
    ) -> PullResult:
        """Pull a spec version to the local directory.

        Args:
            version_id: The version UUID to pull
            shotgun_dir: Target directory (typically .shotgun/)
            on_progress: Optional callback for progress updates
            is_cancelled: Optional callback to check if cancelled
            source: Source of the pull request (CLI or TUI)

        Returns:
            PullResult with success status and details
        """
        start_time = time.time()
        current_phase: PullPhase = PullPhase.STARTING
        track_event("spec_pull_started", {"source": source.value})

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
            nonlocal current_phase
            if is_cancelled and is_cancelled():
                track_event(
                    "spec_pull_cancelled",
                    {"source": source.value, "phase": current_phase.value},
                )
                raise CancelledError()

        try:
            # Phase 1: Fetch version metadata
            current_phase = PullPhase.FETCHING
            report("Fetching version info...")
            check_cancelled()

            response = await self._client.get_version_with_files(version_id)
            spec_name = response.spec_name
            files = response.files

            if not files:
                track_event(
                    "spec_pull_failed",
                    {
                        "source": source.value,
                        "error_type": "EmptyVersion",
                        "phase": current_phase.value,
                    },
                )
                return PullResult(
                    success=False,
                    spec_name=spec_name,
                    error="No files in this version.",
                )

            # Phase 2: Backup existing content
            current_phase = PullPhase.BACKUP
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
            current_phase = PullPhase.DOWNLOADING
            total_files = len(files)
            total_bytes = 0
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
                total_bytes += file_info.size_bytes

                local_path = shotgun_dir / file_info.relative_path
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_bytes(content)

            # Phase 4: Write meta.json
            current_phase = PullPhase.FINALIZING
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

            # Track successful completion
            duration = time.time() - start_time
            track_event(
                "spec_pull_completed",
                {
                    "source": source.value,
                    "file_count": total_files,
                    "total_bytes": total_bytes,
                    "duration_seconds": round(duration, 2),
                    "had_backup": backup_path is not None,
                },
            )

            return PullResult(
                success=True,
                spec_name=spec_name,
                file_count=total_files,
                backup_path=backup_path,
                web_url=response.web_url,
            )

        except CancelledError:
            # Already tracked in check_cancelled()
            raise
        except Exception as e:
            track_event(
                "spec_pull_failed",
                {
                    "source": source.value,
                    "error_type": type(e).__name__,
                    "phase": current_phase.value,
                },
            )
            raise
