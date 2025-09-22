"""File system manager for artifacts."""

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from shotgun.logging_config import setup_logger
from shotgun.utils.file_system_utils import get_shotgun_base_path

from .exceptions import (
    ArtifactFileSystemError,
    ArtifactNotFoundError,
    InvalidArtifactPathError,
    SectionNotFoundError,
)
from .models import AgentMode, Artifact, ArtifactSection
from .utils import generate_artifact_name

logger = setup_logger(__name__)

TEMPLATE_FILENAME = ".template.yaml"


class ArtifactManager:
    """Manages file system operations for artifacts within .shotgun directory."""

    def __init__(self, base_path: Path | None = None) -> None:
        """Initialize artifact manager.

        Args:
            base_path: Base path for artifacts. Defaults to .shotgun in current directory.
        """
        if base_path is None:
            base_path = get_shotgun_base_path()
        elif isinstance(base_path, str):
            base_path = Path(base_path)

        self.base_path = base_path
        logger.debug("Initialized ArtifactManager with base_path: %s", base_path)

    def _get_artifact_path(self, agent_mode: AgentMode, artifact_id: str) -> Path:
        """Get the full path to an artifact directory."""
        return self.base_path / agent_mode.value / artifact_id

    def _validate_artifact_path(self, path: Path) -> None:
        """Validate that artifact path is within allowed directories."""
        try:
            resolved_path = path.resolve()
            base_resolved = self.base_path.resolve()
            resolved_path.relative_to(base_resolved)
        except ValueError as e:
            raise InvalidArtifactPathError(
                str(path), "Path is outside .shotgun directory"
            ) from e

    def _get_template_path(self, artifact_path: Path) -> Path:
        """Get path to template file for an artifact."""
        return artifact_path / TEMPLATE_FILENAME

    def _save_template(
        self, artifact_path: Path, template_content: dict[str, Any]
    ) -> None:
        """Save template content to artifact directory."""
        template_path = self._get_template_path(artifact_path)
        try:
            with open(template_path, "w", encoding="utf-8") as f:
                yaml.dump(template_content, f, indent=2, default_flow_style=False)
            logger.debug("Saved template file: %s", template_path)
        except Exception as e:
            raise ArtifactFileSystemError(
                "save template", str(template_path), str(e)
            ) from e

    def _load_template(self, artifact_path: Path) -> dict[str, Any] | None:
        """Load template content from artifact directory."""
        template_path = self._get_template_path(artifact_path)
        if not template_path.exists():
            return None

        try:
            with open(template_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data if isinstance(data, dict) else None
        except Exception as e:
            logger.warning("Failed to load template from %s: %s", template_path, str(e))
            return None

    def artifact_exists(self, agent_mode: AgentMode, artifact_id: str) -> bool:
        """Check if an artifact exists."""
        artifact_path = self._get_artifact_path(agent_mode, artifact_id)
        return artifact_path.exists() and artifact_path.is_dir()

    def create_artifact(self, artifact: Artifact) -> None:
        """Create a new artifact on the file system."""
        artifact_path = self._get_artifact_path(
            artifact.agent_mode, artifact.artifact_id
        )
        self._validate_artifact_path(artifact_path)

        if artifact_path.exists():
            raise ArtifactFileSystemError(
                "create artifact",
                str(artifact_path),
                "Directory already exists",
            )

        try:
            # Create artifact directory
            artifact_path.mkdir(parents=True, exist_ok=False)
            logger.debug("Created artifact directory: %s", artifact_path)

            # Save sections
            for section in artifact.sections:
                self._write_section_file(artifact_path, section)

            # Template saving is now handled by the service layer via save_template_file method

        except Exception as e:
            # Clean up on failure
            if artifact_path.exists():
                try:
                    self._remove_directory(artifact_path)
                except Exception as cleanup_error:
                    logger.debug(
                        "Failed to cleanup directory %s: %s",
                        artifact_path,
                        cleanup_error,
                    )
            raise ArtifactFileSystemError(
                "create artifact", str(artifact_path), str(e)
            ) from e

    def load_artifact(
        self, agent_mode: AgentMode, artifact_id: str, name: str | None = None
    ) -> Artifact:
        """Load an artifact from the file system."""
        artifact_path = self._get_artifact_path(agent_mode, artifact_id)

        if not artifact_path.exists():
            raise ArtifactNotFoundError(artifact_id, agent_mode.value)

        try:
            # Load sections
            sections: list[ArtifactSection] = []
            section_files = list(artifact_path.glob("*.md"))

            for section_file in section_files:
                section = self._load_section_from_file(section_file)
                if section:
                    sections.append(section)

            # Sort sections by number
            sections.sort(key=lambda s: s.number)

            # Generate a default name if none provided
            if not name:
                name = generate_artifact_name(artifact_id)

            artifact = Artifact(
                artifact_id=artifact_id,
                agent_mode=agent_mode,
                name=name,
                sections=sections,
            )

            return artifact

        except ArtifactNotFoundError:
            raise
        except Exception as e:
            raise ArtifactFileSystemError(
                "load artifact", str(artifact_path), str(e)
            ) from e

    def save_artifact(self, artifact: Artifact) -> None:
        """Save an existing artifact to the file system."""
        artifact_path = self._get_artifact_path(
            artifact.agent_mode, artifact.artifact_id
        )

        if not artifact_path.exists():
            raise ArtifactNotFoundError(artifact.artifact_id, artifact.agent_mode.value)

        try:
            # Get existing section files
            existing_files = {f.name for f in artifact_path.glob("*.md")}

            # Write current sections
            current_files = set()
            for section in artifact.sections:
                filename = section.filename
                self._write_section_file(artifact_path, section)
                current_files.add(filename)

            # Remove orphaned section files
            orphaned_files = existing_files - current_files
            for filename in orphaned_files:
                file_path = artifact_path / filename
                try:
                    file_path.unlink()
                    logger.debug("Removed orphaned section file: %s", file_path)
                except Exception as e:
                    logger.warning(
                        "Failed to remove orphaned file %s: %s", file_path, e
                    )

            # No metadata to save - all artifact state is in sections and template files

        except ArtifactNotFoundError:
            raise
        except Exception as e:
            raise ArtifactFileSystemError(
                "save artifact", str(artifact_path), str(e)
            ) from e

    def delete_artifact(self, agent_mode: AgentMode, artifact_id: str) -> None:
        """Delete an artifact from the file system."""
        artifact_path = self._get_artifact_path(agent_mode, artifact_id)

        if not artifact_path.exists():
            raise ArtifactNotFoundError(artifact_id, agent_mode.value)

        try:
            self._remove_directory(artifact_path)
            logger.debug("Deleted artifact directory: %s", artifact_path)
        except Exception as e:
            raise ArtifactFileSystemError(
                "delete artifact", str(artifact_path), str(e)
            ) from e

    def list_artifacts(
        self, agent_mode: AgentMode | None = None
    ) -> list[dict[str, Any]]:
        """List all artifacts, optionally filtered by agent mode."""
        artifacts = []

        try:
            if agent_mode:
                agent_dirs = [self.base_path / agent_mode.value]
            else:
                agent_dirs = [
                    self.base_path / mode.value
                    for mode in AgentMode
                    if (self.base_path / mode.value).exists()
                ]

            for agent_dir in agent_dirs:
                if not agent_dir.exists():
                    continue

                mode = AgentMode(agent_dir.name)
                for artifact_dir in agent_dir.iterdir():
                    if artifact_dir.is_dir() and not artifact_dir.name.startswith("."):
                        try:
                            section_titles = self._get_section_titles(artifact_dir)

                            artifacts.append(
                                {
                                    "artifact_id": artifact_dir.name,
                                    "agent_mode": mode,
                                    "section_count": len(section_titles),
                                    "section_titles": section_titles,
                                    "created_at": self._get_artifact_created_at(
                                        artifact_dir
                                    ),
                                    "updated_at": self._get_artifact_updated_at(
                                        artifact_dir
                                    ),
                                    "description": "",  # No longer stored
                                }
                            )
                        except Exception as e:
                            logger.warning(
                                "Failed to load artifact info from %s: %s",
                                artifact_dir,
                                e,
                            )
                            continue

        except Exception as e:
            raise ArtifactFileSystemError(
                "list artifacts", str(self.base_path), str(e)
            ) from e

        return artifacts

    def _write_section_file(
        self, artifact_path: Path, section: ArtifactSection
    ) -> None:
        """Write a section to its markdown file."""
        section_path = artifact_path / section.filename
        try:
            content = f"# {section.title}\n\n{section.content}"
            section_path.write_text(content, encoding="utf-8")
            logger.debug("Wrote section file: %s", section_path)
        except Exception as e:
            raise ArtifactFileSystemError(
                "write section", str(section_path), str(e)
            ) from e

    def _load_section_from_file(self, section_file: Path) -> ArtifactSection | None:
        """Load a section from a markdown file."""
        try:
            # Parse filename for number and slug
            filename = section_file.name
            if not filename.endswith(".md"):
                return None

            name_part = filename[:-3]  # Remove .md
            if not name_part or "-" not in name_part:
                return None

            try:
                number_str, slug = name_part.split("-", 1)
                number = int(number_str)
            except (ValueError, IndexError):
                logger.warning("Invalid section filename format: %s", filename)
                return None

            # Read content
            content = section_file.read_text(encoding="utf-8")

            # Extract title from first heading if present
            lines = content.split("\n")
            title = slug.replace("-", " ").title()  # Default title
            content_lines = lines

            if lines and lines[0].startswith("# "):
                title = lines[0][2:].strip()
                content_lines = (
                    lines[2:] if len(lines) > 1 and not lines[1].strip() else lines[1:]
                )

            content_text = "\n".join(content_lines).strip()

            return ArtifactSection(
                number=number,
                slug=slug,
                title=title,
                content=content_text,
            )

        except Exception as e:
            logger.warning("Failed to load section from %s: %s", section_file, e)
            return None

    def _get_section_titles(self, artifact_path: Path) -> list[str]:
        """Get list of section titles from artifact directory."""
        titles = []
        section_files = sorted(artifact_path.glob("*.md"))

        for section_file in section_files:
            section = self._load_section_from_file(section_file)
            if section:
                titles.append(section.title)

        return titles

    def _ensure_artifact_exists(self, agent_mode: AgentMode, artifact_id: str) -> Path:
        """Ensure artifact exists and return its path.

        Args:
            agent_mode: Agent mode
            artifact_id: Artifact ID

        Returns:
            Path to the artifact directory

        Raises:
            ArtifactNotFoundError: If artifact doesn't exist
        """
        artifact_path = self._get_artifact_path(agent_mode, artifact_id)
        if not artifact_path.exists():
            raise ArtifactNotFoundError(artifact_id, agent_mode.value)
        return artifact_path

    def _find_section_file_by_number(
        self, artifact_path: Path, section_number: int
    ) -> Path:
        """Find section file by number.

        Args:
            artifact_path: Path to artifact directory
            section_number: Section number to find

        Returns:
            Path to the section file

        Raises:
            SectionNotFoundError: If section file doesn't exist
        """
        for file in artifact_path.glob("*.md"):
            filename = file.name
            if filename.startswith(f"{section_number:03d}-"):
                return file

        raise SectionNotFoundError(section_number, artifact_path.name)

    def _remove_directory(self, path: Path) -> None:
        """Recursively remove a directory."""
        if not path.exists():
            return

        for item in path.iterdir():
            if item.is_dir():
                self._remove_directory(item)
            else:
                item.unlink()

        path.rmdir()

    def _get_artifact_created_at(self, artifact_path: Path) -> datetime:
        """Get artifact creation time from filesystem."""
        if artifact_path.exists():
            return datetime.fromtimestamp(artifact_path.stat().st_ctime)
        return datetime.now()

    def _get_artifact_updated_at(self, artifact_path: Path) -> datetime:
        """Get artifact last updated time from filesystem."""
        if not artifact_path.exists():
            return datetime.now()

        # Find the most recently modified file in the artifact directory
        most_recent = artifact_path.stat().st_mtime
        for file_path in artifact_path.rglob("*"):
            if file_path.is_file():
                file_mtime = file_path.stat().st_mtime
                most_recent = max(most_recent, file_mtime)

        return datetime.fromtimestamp(most_recent)

    def save_template_file(
        self, agent_mode: AgentMode, artifact_id: str, template_content: dict[str, Any]
    ) -> None:
        """Save template content to an artifact's .template.yaml file.

        Args:
            agent_mode: Agent mode
            artifact_id: Artifact ID
            template_content: Template content as dictionary

        Raises:
            ArtifactNotFoundError: If artifact doesn't exist
            ArtifactFileSystemError: If template file cannot be saved
        """
        artifact_path = self._ensure_artifact_exists(agent_mode, artifact_id)
        self._save_template(artifact_path, template_content)

    def write_section(
        self, agent_mode: AgentMode, artifact_id: str, section: ArtifactSection
    ) -> None:
        """Write a single section to its file without affecting other sections.

        Args:
            agent_mode: Agent mode
            artifact_id: Artifact ID
            section: Section to write

        Raises:
            ArtifactNotFoundError: If artifact doesn't exist
            ArtifactFileSystemError: If section file cannot be written
        """
        artifact_path = self._ensure_artifact_exists(agent_mode, artifact_id)
        self._write_section_file(artifact_path, section)

    def update_section_file(
        self, agent_mode: AgentMode, artifact_id: str, section: ArtifactSection
    ) -> None:
        """Update a single section file without affecting other sections.

        Args:
            agent_mode: Agent mode
            artifact_id: Artifact ID
            section: Updated section data

        Raises:
            ArtifactNotFoundError: If artifact doesn't exist
            SectionNotFoundError: If section file doesn't exist
            ArtifactFileSystemError: If section file cannot be updated
        """
        artifact_path = self._ensure_artifact_exists(agent_mode, artifact_id)

        # Verify section file exists
        section_path = artifact_path / section.filename
        if not section_path.exists():
            raise SectionNotFoundError(section.number, artifact_id)

        self._write_section_file(artifact_path, section)

    def delete_section_file(
        self, agent_mode: AgentMode, artifact_id: str, section_number: int
    ) -> None:
        """Delete a single section file without affecting other sections.

        Args:
            agent_mode: Agent mode
            artifact_id: Artifact ID
            section_number: Section number to delete

        Raises:
            ArtifactNotFoundError: If artifact doesn't exist
            SectionNotFoundError: If section file doesn't exist
            ArtifactFileSystemError: If section file cannot be deleted
        """
        artifact_path = self._ensure_artifact_exists(agent_mode, artifact_id)
        section_file = self._find_section_file_by_number(artifact_path, section_number)

        try:
            section_file.unlink()
            logger.debug("Deleted section file: %s", section_file)
        except Exception as e:
            raise ArtifactFileSystemError(
                "delete section", str(section_file), str(e)
            ) from e

    def read_section(
        self, agent_mode: AgentMode, artifact_id: str, section_number: int
    ) -> str:
        """Read content of a specific section."""
        artifact_path = self._ensure_artifact_exists(agent_mode, artifact_id)
        section_file = self._find_section_file_by_number(artifact_path, section_number)

        try:
            return section_file.read_text(encoding="utf-8")
        except Exception as e:
            raise ArtifactFileSystemError(
                "read section", str(section_file), str(e)
            ) from e
