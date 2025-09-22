"""Pydantic models for the artifact system."""

import re
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from shotgun.utils.file_system_utils import get_shotgun_base_path


class AgentMode(str, Enum):
    """Supported agent modes for artifacts."""

    RESEARCH = "research"
    PLAN = "plan"
    TASKS = "tasks"
    SPECIFY = "specify"


class ArtifactSection(BaseModel):
    """A section within an artifact."""

    number: int = Field(..., ge=1, description="Section number for ordering")
    slug: str = Field(..., min_length=1, description="URL-friendly section identifier")
    title: str = Field(..., min_length=1, description="Human-readable section title")
    content: str = Field(default="", description="Markdown content of the section")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """Validate that slug contains only valid characters."""
        if not re.match(r"^[a-z0-9._-]+$", v):
            raise ValueError(
                "Slug must contain only lowercase letters, numbers, hyphens, dots, and underscores"
            )
        if v.startswith("-") or v.endswith("-"):
            raise ValueError("Slug cannot start or end with hyphen")
        if v.startswith(".") or v.endswith("."):
            raise ValueError("Slug cannot start or end with dot")
        if v.startswith("_") or v.endswith("_"):
            raise ValueError("Slug cannot start or end with underscore")
        if "--" in v:
            raise ValueError("Slug cannot contain consecutive hyphens")
        if ".." in v:
            raise ValueError("Slug cannot contain consecutive dots")
        if "__" in v:
            raise ValueError("Slug cannot contain consecutive underscores")
        return v

    @property
    def filename(self) -> str:
        """Generate filename for this section."""
        return f"{self.number:03d}-{self.slug}.md"

    def __str__(self) -> str:
        """String representation for debugging."""
        return f"Section({self.number:03d}-{self.slug})"


class Artifact(BaseModel):
    """Main artifact model containing sections."""

    artifact_id: str = Field(
        ..., min_length=1, description="Unique artifact identifier"
    )
    agent_mode: AgentMode = Field(
        ..., description="Agent mode this artifact belongs to"
    )
    name: str = Field(..., min_length=1, description="Human-readable artifact name")
    sections: list[ArtifactSection] = Field(default_factory=list)

    @field_validator("artifact_id")
    @classmethod
    def validate_artifact_id(cls, v: str) -> str:
        """Validate that artifact_id is a valid slug."""
        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError(
                "Artifact ID must contain only lowercase letters, numbers, and hyphens"
            )
        if v.startswith("-") or v.endswith("-"):
            raise ValueError("Artifact ID cannot start or end with hyphen")
        if "--" in v:
            raise ValueError("Artifact ID cannot contain consecutive hyphens")
        return v

    @model_validator(mode="after")
    def validate_section_numbers(self) -> "Artifact":
        """Ensure section numbers are unique and sequential."""
        if not self.sections:
            return self

        numbers = [section.number for section in self.sections]
        if len(numbers) != len(set(numbers)):
            raise ValueError("Section numbers must be unique")

        # Check for reasonable numbering (starting from 1, no big gaps)
        sorted_numbers = sorted(numbers)
        if sorted_numbers[0] != 1:
            raise ValueError("Section numbers should start from 1")

        # Allow gaps but warn about unreasonable ones
        max_gap = (
            max(
                sorted_numbers[i + 1] - sorted_numbers[i]
                for i in range(len(sorted_numbers) - 1)
            )
            if len(sorted_numbers) > 1
            else 0
        )

        if max_gap > 10:
            # This is just a warning, not an error
            pass

        return self

    @property
    def directory_path(self) -> str:
        """Get the relative directory path for this artifact."""
        return f"{self.agent_mode.value}/{self.artifact_id}"

    def get_section_by_number(self, number: int) -> ArtifactSection | None:
        """Get section by number."""
        for section in self.sections:
            if section.number == number:
                return section
        return None

    def get_section_by_slug(self, slug: str) -> ArtifactSection | None:
        """Get section by slug."""
        for section in self.sections:
            if section.slug == slug:
                return section
        return None

    def add_section(self, section: ArtifactSection) -> None:
        """Add a section to the artifact."""
        # Check for conflicts
        if self.get_section_by_number(section.number):
            raise ValueError(f"Section number {section.number} already exists")
        if self.get_section_by_slug(section.slug):
            raise ValueError(f"Section slug '{section.slug}' already exists")

        self.sections.append(section)
        self.sections.sort(key=lambda s: s.number)

    def remove_section(self, number: int) -> bool:
        """Remove a section by number. Returns True if section was removed."""
        original_count = len(self.sections)
        self.sections = [s for s in self.sections if s.number != number]
        removed = len(self.sections) < original_count
        return removed

    def update_section(self, number: int, **kwargs: Any) -> bool:
        """Update a section's fields. Returns True if section was found and updated."""
        section = self.get_section_by_number(number)
        if not section:
            return False

        # Handle special case of changing number
        if "number" in kwargs and kwargs["number"] != section.number:
            new_number = kwargs["number"]
            if self.get_section_by_number(new_number):
                raise ValueError(f"Section number {new_number} already exists")

        # Update fields
        for field, value in kwargs.items():
            setattr(section, field, value)

        # Re-sort if number changed
        if "number" in kwargs:
            self.sections.sort(key=lambda s: s.number)

        return True

    def get_ordered_sections(self) -> list[ArtifactSection]:
        """Get sections ordered by number."""
        return sorted(self.sections, key=lambda s: s.number)

    def has_template(self, base_path: Path | None = None) -> bool:
        """Check if this artifact was created from a template."""
        if base_path is None:
            base_path = get_shotgun_base_path()
        elif isinstance(base_path, str):
            base_path = Path(base_path)

        template_path = (
            base_path / self.agent_mode.value / self.artifact_id / ".template.yaml"
        )
        return template_path.exists()

    def get_template_id(self, base_path: Path | None = None) -> str | None:
        """Get the template ID from the template file."""
        template_content = self.load_template_from_file(base_path)
        if template_content and "template_id" in template_content:
            template_id = template_content["template_id"]
            return str(template_id) if template_id is not None else None
        return None

    def load_template_from_file(
        self, base_path: Path | None = None
    ) -> dict[str, Any] | None:
        """Load template content from the artifact's .template.yaml file.

        Args:
            base_path: Base path for artifacts. Defaults to .shotgun in current directory.

        Returns:
            Template content as dict or None if no template file exists.
        """
        import yaml

        if base_path is None:
            base_path = get_shotgun_base_path()
        elif isinstance(base_path, str):
            base_path = Path(base_path)

        template_path = (
            base_path / self.agent_mode.value / self.artifact_id / ".template.yaml"
        )

        if not template_path.exists():
            return None

        try:
            with open(template_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data if isinstance(data, dict) else None
        except Exception:
            return None

    def get_section_count(self) -> int:
        """Get section count based on current sections."""
        return len(self.sections)

    def get_total_content_length(self) -> int:
        """Calculate total content length from all sections."""
        return sum(len(section.content) for section in self.sections)

    def get_created_at(self, base_path: Path | None = None) -> datetime:
        """Get artifact creation time from filesystem.

        Args:
            base_path: Base path for artifacts. Defaults to .shotgun in current directory.

        Returns:
            Creation timestamp based on artifact directory creation time.
        """
        if base_path is None:
            base_path = get_shotgun_base_path()
        elif isinstance(base_path, str):
            base_path = Path(base_path)

        artifact_path = base_path / self.agent_mode.value / self.artifact_id
        if artifact_path.exists():
            return datetime.fromtimestamp(artifact_path.stat().st_ctime)
        return datetime.now()

    def get_updated_at(self, base_path: Path | None = None) -> datetime:
        """Get artifact last updated time from filesystem.

        Args:
            base_path: Base path for artifacts. Defaults to .shotgun in current directory.

        Returns:
            Last modified timestamp based on most recently modified file in artifact directory.
        """
        if base_path is None:
            base_path = get_shotgun_base_path()
        elif isinstance(base_path, str):
            base_path = Path(base_path)

        artifact_path = base_path / self.agent_mode.value / self.artifact_id
        if not artifact_path.exists():
            return datetime.now()

        # Find the most recently modified file in the artifact directory
        most_recent = artifact_path.stat().st_mtime
        for file_path in artifact_path.rglob("*"):
            if file_path.is_file():
                file_mtime = file_path.stat().st_mtime
                most_recent = max(most_recent, file_mtime)

        return datetime.fromtimestamp(most_recent)

    def __str__(self) -> str:
        """String representation for debugging."""
        template_info = " (template)" if self.has_template() else ""
        return f"Artifact({self.agent_mode.value}/{self.artifact_id}, {len(self.sections)} sections{template_info})"


class ArtifactSummary(BaseModel):
    """Summary information about an artifact without full content."""

    artifact_id: str
    agent_mode: AgentMode
    name: str
    section_count: int
    created_at: datetime
    updated_at: datetime
    section_titles: list[str] = Field(default_factory=list)
    template_id: str | None = Field(
        default=None, description="ID of template used to create this artifact"
    )

    @classmethod
    def from_artifact(
        cls, artifact: Artifact, base_path: Path | None = None
    ) -> "ArtifactSummary":
        """Create summary from full artifact.

        Args:
            artifact: The artifact to create summary from
            base_path: Base path for artifacts. Used for filesystem-based timestamps.
        """
        return cls(
            artifact_id=artifact.artifact_id,
            agent_mode=artifact.agent_mode,
            name=artifact.name,
            section_count=artifact.get_section_count(),
            created_at=artifact.get_created_at(base_path),
            updated_at=artifact.get_updated_at(base_path),
            section_titles=[
                section.title for section in artifact.get_ordered_sections()
            ],
            template_id=artifact.get_template_id(base_path),
        )

    def __str__(self) -> str:
        """String representation for debugging."""
        return f"ArtifactSummary({self.agent_mode.value}/{self.artifact_id})"
