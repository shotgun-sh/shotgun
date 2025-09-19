"""Result models for SDK artifact operations."""

from pydantic import BaseModel

from shotgun.artifacts.models import AgentMode, Artifact, ArtifactSummary


class ArtifactListResult(BaseModel):
    """Result for artifact list command."""

    artifacts: list[ArtifactSummary]
    agent_mode: AgentMode | None = None

    def __str__(self) -> str:
        """Format list result as plain text table."""
        if not self.artifacts:
            mode_text = f" for {self.agent_mode.value}" if self.agent_mode else ""
            return f"No artifacts found{mode_text}."

        lines = [
            f"{'Agent':<10} {'ID':<25} {'Name':<30} {'Sections':<8} {'Updated'}",
            "-" * 85,
        ]

        for artifact in self.artifacts:
            lines.append(
                f"{artifact.agent_mode.value:<10} "
                f"{artifact.artifact_id[:25]:<25} "
                f"{artifact.name[:30]:<30} "
                f"{artifact.section_count:<8} "
                f"{artifact.updated_at.strftime('%Y-%m-%d')}"
            )

        return "\n".join(lines)


class ArtifactCreateResult(BaseModel):
    """Result for artifact create command."""

    artifact_id: str
    agent_mode: AgentMode
    name: str
    created: bool = True

    def __str__(self) -> str:
        """Format create result as success message."""
        return f"Created artifact '{self.artifact_id}' in {self.agent_mode.value} mode"


class ArtifactDeleteResult(BaseModel):
    """Result for artifact delete command."""

    artifact_id: str
    agent_mode: AgentMode
    deleted: bool = True
    cancelled: bool = False

    def __str__(self) -> str:
        """Format delete result message."""
        if self.cancelled:
            return "Deletion cancelled."
        elif self.deleted:
            return f"Deleted artifact '{self.artifact_id}' from {self.agent_mode.value} mode"
        else:
            return f"Failed to delete artifact '{self.artifact_id}'"


class ArtifactInfoResult(BaseModel):
    """Result for artifact info command."""

    artifact: Artifact

    def __str__(self) -> str:
        """Format detailed artifact information."""
        artifact = self.artifact
        lines = [
            f"Artifact ID: {artifact.artifact_id}",
            f"Name: {artifact.name}",
            f"Agent Mode: {artifact.agent_mode.value}",
            f"Created: {artifact.get_created_at()}",
            f"Updated: {artifact.get_updated_at()}",
            f"Sections: {artifact.get_section_count()}",
            f"Total Content Length: {artifact.get_total_content_length()} characters",
        ]

        if artifact.sections:
            lines.append("\nSections:")
            for section in artifact.get_ordered_sections():
                content_preview = (
                    section.content[:50] + "..."
                    if len(section.content) > 50
                    else section.content
                ).replace("\n", " ")
                lines.append(f"  {section.number:03d}. {section.title}")
                if content_preview:
                    lines.append(f"       {content_preview}")

        return "\n".join(lines)


class SectionCreateResult(BaseModel):
    """Result for section create command."""

    artifact_id: str
    agent_mode: AgentMode
    section_number: int
    section_title: str
    created: bool = True

    def __str__(self) -> str:
        """Format section create result."""
        return (
            f"Created section {self.section_number} '{self.section_title}' "
            f"in artifact '{self.artifact_id}'"
        )


class SectionUpdateResult(BaseModel):
    """Result for section update command."""

    artifact_id: str
    agent_mode: AgentMode
    section_number: int
    updated_fields: list[str]

    def __str__(self) -> str:
        """Format section update result."""
        fields_text = ", ".join(self.updated_fields)
        return (
            f"Updated section {self.section_number} in artifact '{self.artifact_id}' "
            f"(fields: {fields_text})"
        )


class SectionDeleteResult(BaseModel):
    """Result for section delete command."""

    artifact_id: str
    agent_mode: AgentMode
    section_number: int
    deleted: bool = True

    def __str__(self) -> str:
        """Format section delete result."""
        if self.deleted:
            return f"Deleted section {self.section_number} from artifact '{self.artifact_id}'"
        else:
            return f"Failed to delete section {self.section_number}"


class SectionContentResult(BaseModel):
    """Result for section content read command."""

    artifact_id: str
    agent_mode: AgentMode
    section_number: int
    content: str

    def __str__(self) -> str:
        """Format section content."""
        return self.content


class ArtifactErrorResult(BaseModel):
    """Result for error cases in artifact operations."""

    error_message: str
    artifact_id: str | None = None
    agent_mode: AgentMode | None = None
    section_number: int | None = None
    details: str | None = None

    def __str__(self) -> str:
        """Format error message."""
        parts = [f"Error: {self.error_message}"]

        if self.artifact_id:
            parts.append(f"Artifact: {self.artifact_id}")
        if self.agent_mode:
            parts.append(f"Mode: {self.agent_mode.value}")
        if self.section_number:
            parts.append(f"Section: {self.section_number}")
        if self.details:
            parts.append(f"Details: {self.details}")

        return " | ".join(parts)
