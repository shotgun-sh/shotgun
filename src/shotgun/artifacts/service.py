"""High-level service for artifact management and operations."""

from pathlib import Path
from typing import Any

from shotgun.logging_config import setup_logger

from .exceptions import (
    ArtifactAlreadyExistsError,
    ArtifactNotFoundError,
    SectionAlreadyExistsError,
    SectionNotFoundError,
)
from .manager import ArtifactManager
from .models import AgentMode, Artifact, ArtifactSection, ArtifactSummary
from .templates.loader import ArtifactTemplateLoader
from .templates.models import ArtifactTemplate, TemplateSummary
from .utils import generate_artifact_name

logger = setup_logger(__name__)


class ArtifactService:
    """High-level service for artifact management and operations."""

    def __init__(self, base_path: Path | None = None) -> None:
        """Initialize artifact service.

        Args:
            base_path: Base path for artifacts. Defaults to .shotgun in current directory.
        """
        self.manager = ArtifactManager(base_path)
        logger.debug("Initialized ArtifactService")

    def create_artifact(
        self,
        artifact_id: str,
        agent_mode: AgentMode,
        name: str,
        template_id: str | None = None,
    ) -> Artifact:
        """Create a new artifact.

        Args:
            artifact_id: Unique identifier for the artifact
            agent_mode: Agent mode this artifact belongs to
            name: Human-readable name for the artifact
            template_id: Optional template ID to use for creating the artifact

        Returns:
            Created artifact

        Raises:
            ArtifactAlreadyExistsError: If artifact already exists
            ValueError: If template is invalid or not found
        """
        if self.manager.artifact_exists(agent_mode, artifact_id):
            raise ArtifactAlreadyExistsError(artifact_id, agent_mode.value)

        # Load and validate template if provided
        template = None
        if template_id:
            template_loader = ArtifactTemplateLoader()
            template = template_loader.get_template(template_id)
            if not template:
                raise ValueError(f"Template '{template_id}' not found")

            # Validate template is for correct agent mode
            if template.agent_mode != agent_mode:
                raise ValueError(
                    f"Template '{template_id}' is for agent mode '{template.agent_mode.value}', "
                    f"but artifact is being created for '{agent_mode.value}'"
                )

        artifact = Artifact(
            artifact_id=artifact_id,
            agent_mode=agent_mode,
            name=name,
            sections=[],
        )

        # Create artifact first
        self.manager.create_artifact(artifact)

        # Apply template if provided
        if template and template_id:
            # Save template content to .template.yaml file
            self.manager.save_template_file(
                agent_mode, artifact_id, template.to_yaml_dict()
            )
            logger.info("Applied template '%s' to artifact", template_id)

        logger.info("Created artifact: %s/%s", agent_mode.value, artifact_id)
        return artifact

    def get_artifact(
        self, artifact_id: str, agent_mode: AgentMode, name: str = ""
    ) -> Artifact:
        """Get an artifact by ID and agent mode.

        Args:
            artifact_id: Artifact identifier
            agent_mode: Agent mode
            name: Artifact name (for display, not used for lookup)

        Returns:
            Artifact object

        Raises:
            ArtifactNotFoundError: If artifact is not found
        """
        return self.manager.load_artifact(agent_mode, artifact_id, name)

    def update_artifact(self, artifact: Artifact) -> Artifact:
        """Update an existing artifact.

        Args:
            artifact: Artifact to update

        Returns:
            Updated artifact

        Raises:
            ArtifactNotFoundError: If artifact is not found
        """
        self.manager.save_artifact(artifact)
        logger.info(
            "Updated artifact: %s/%s", artifact.agent_mode.value, artifact.artifact_id
        )
        return artifact

    def delete_artifact(self, artifact_id: str, agent_mode: AgentMode) -> None:
        """Delete an artifact.

        Args:
            artifact_id: Artifact identifier
            agent_mode: Agent mode

        Raises:
            ArtifactNotFoundError: If artifact is not found
        """
        self.manager.delete_artifact(agent_mode, artifact_id)
        logger.info("Deleted artifact: %s/%s", agent_mode.value, artifact_id)

    def list_artifacts(
        self, agent_mode: AgentMode | None = None
    ) -> list[ArtifactSummary]:
        """List all artifacts, optionally filtered by agent mode.

        Args:
            agent_mode: Optional agent mode filter

        Returns:
            List of artifact summaries
        """
        artifacts_data = self.manager.list_artifacts(agent_mode)
        summaries = []

        for data in artifacts_data:
            summary = ArtifactSummary(
                artifact_id=data["artifact_id"],
                agent_mode=data["agent_mode"],
                name=data["artifact_id"]
                .replace("-", " ")
                .title(),  # Default name from ID
                section_count=data["section_count"],
                created_at=data["created_at"],
                updated_at=data["updated_at"],
                section_titles=data["section_titles"],
                template_id=None,  # Will be detected from file when needed
            )
            summaries.append(summary)

        return summaries

    def artifact_exists(self, artifact_id: str, agent_mode: AgentMode) -> bool:
        """Check if an artifact exists.

        Args:
            artifact_id: Artifact identifier
            agent_mode: Agent mode

        Returns:
            True if artifact exists, False otherwise
        """
        return self.manager.artifact_exists(agent_mode, artifact_id)

    # Section operations

    def add_section(
        self,
        artifact_id: str,
        agent_mode: AgentMode,
        section: ArtifactSection,
    ) -> Artifact:
        """Add a section to an artifact.

        Args:
            artifact_id: Artifact identifier
            agent_mode: Agent mode
            section: Section to add

        Returns:
            Updated artifact

        Raises:
            ArtifactNotFoundError: If artifact is not found
            SectionAlreadyExistsError: If section number or slug already exists
        """
        artifact = self.manager.load_artifact(agent_mode, artifact_id, "")

        # Check for conflicts
        if artifact.get_section_by_number(section.number):
            raise SectionAlreadyExistsError(section.number, artifact_id)
        if artifact.get_section_by_slug(section.slug):
            raise SectionAlreadyExistsError(section.slug, artifact_id)

        artifact.add_section(section)
        # Write only the new section to disk, not all sections
        self.manager.write_section(agent_mode, artifact_id, section)

        logger.info(
            "Added section %d to artifact: %s/%s",
            section.number,
            agent_mode.value,
            artifact_id,
        )
        return artifact

    def get_section(
        self,
        artifact_id: str,
        agent_mode: AgentMode,
        section_number: int,
    ) -> ArtifactSection:
        """Get a section from an artifact.

        Args:
            artifact_id: Artifact identifier
            agent_mode: Agent mode
            section_number: Section number

        Returns:
            The section

        Raises:
            ArtifactNotFoundError: If artifact is not found
            SectionNotFoundError: If section is not found
        """
        artifact = self.manager.load_artifact(agent_mode, artifact_id, "")
        section = artifact.get_section_by_number(section_number)

        if not section:
            raise SectionNotFoundError(section_number, artifact_id)

        return section

    def update_section(
        self,
        artifact_id: str,
        agent_mode: AgentMode,
        section_number: int,
        **kwargs: Any,
    ) -> Artifact:
        """Update a section in an artifact.

        Args:
            artifact_id: Artifact identifier
            agent_mode: Agent mode
            section_number: Section number to update
            **kwargs: Fields to update

        Returns:
            Updated artifact

        Raises:
            ArtifactNotFoundError: If artifact is not found
            SectionNotFoundError: If section is not found
        """
        artifact = self.manager.load_artifact(agent_mode, artifact_id, "")

        if not artifact.update_section(section_number, **kwargs):
            raise SectionNotFoundError(section_number, artifact_id)

        # Write only the updated section to disk, not all sections
        updated_section = artifact.get_section_by_number(section_number)
        if updated_section:
            self.manager.update_section_file(agent_mode, artifact_id, updated_section)

        logger.info(
            "Updated section %d in artifact: %s/%s",
            section_number,
            agent_mode.value,
            artifact_id,
        )
        return artifact

    def delete_section(
        self,
        artifact_id: str,
        agent_mode: AgentMode,
        section_number: int,
    ) -> Artifact:
        """Delete a section from an artifact.

        Args:
            artifact_id: Artifact identifier
            agent_mode: Agent mode
            section_number: Section number to delete

        Returns:
            Updated artifact

        Raises:
            ArtifactNotFoundError: If artifact is not found
            SectionNotFoundError: If section is not found
        """
        artifact = self.manager.load_artifact(agent_mode, artifact_id, "")

        if not artifact.remove_section(section_number):
            raise SectionNotFoundError(section_number, artifact_id)

        # Delete only the specific section file, not rewrite all sections
        self.manager.delete_section_file(agent_mode, artifact_id, section_number)

        logger.info(
            "Deleted section %d from artifact: %s/%s",
            section_number,
            agent_mode.value,
            artifact_id,
        )
        return artifact

    def get_section_content(
        self,
        artifact_id: str,
        agent_mode: AgentMode,
        section_number: int,
    ) -> str:
        """Get the raw content of a section.

        Args:
            artifact_id: Artifact identifier
            agent_mode: Agent mode
            section_number: Section number

        Returns:
            Raw markdown content of the section

        Raises:
            ArtifactNotFoundError: If artifact is not found
            SectionNotFoundError: If section is not found
        """
        return self.manager.read_section(agent_mode, artifact_id, section_number)

    # Convenience methods

    def get_or_create_artifact(
        self,
        artifact_id: str,
        agent_mode: AgentMode,
        name: str,
        template_id: str | None = None,
    ) -> tuple[Artifact, bool]:
        """Get an existing artifact or create a new one.

        Args:
            artifact_id: Artifact identifier
            agent_mode: Agent mode
            name: Artifact name
            template_id: Optional template ID to use when creating

        Returns:
            Tuple of (artifact, created) where created is True if newly created
        """
        try:
            artifact = self.get_artifact(artifact_id, agent_mode, name)
            return artifact, False
        except ArtifactNotFoundError:
            artifact = self.create_artifact(artifact_id, agent_mode, name, template_id)
            return artifact, True

    def get_or_create_section(
        self,
        artifact_id: str,
        agent_mode: AgentMode,
        section_number: int,
        section_slug: str,
        section_title: str,
        initial_content: str = "",
    ) -> tuple[ArtifactSection, bool]:
        """Get an existing section or create a new one.

        Args:
            artifact_id: Artifact identifier
            agent_mode: Agent mode
            section_number: Section number
            section_slug: Section slug
            section_title: Section title
            initial_content: Initial content for new sections

        Returns:
            Tuple of (section, created) where created is True if newly created
        """
        try:
            section = self.get_section(artifact_id, agent_mode, section_number)
            return section, False
        except (ArtifactNotFoundError, SectionNotFoundError):
            # Create artifact if it doesn't exist
            artifact, _ = self.get_or_create_artifact(
                artifact_id, agent_mode, generate_artifact_name(artifact_id)
            )

            # Create section
            section = ArtifactSection(
                number=section_number,
                slug=section_slug,
                title=section_title,
                content=initial_content,
            )

            self.add_section(artifact_id, agent_mode, section)
            return section, True

    # Template operations

    def list_templates(
        self, agent_mode: AgentMode | None = None
    ) -> list[TemplateSummary]:
        """List available artifact templates.

        Args:
            agent_mode: Optional agent mode filter

        Returns:
            List of template summaries
        """
        template_loader = ArtifactTemplateLoader()
        return template_loader.list_templates(agent_mode)

    def get_template(self, template_id: str) -> ArtifactTemplate | None:
        """Get a specific template by ID.

        Args:
            template_id: Template identifier

        Returns:
            Template object or None if not found
        """
        template_loader = ArtifactTemplateLoader()
        return template_loader.get_template(template_id)

    def get_templates_for_mode(self, agent_mode: AgentMode) -> list[ArtifactTemplate]:
        """Get all templates for a specific agent mode.

        Args:
            agent_mode: Agent mode to filter by

        Returns:
            List of templates for the specified mode
        """
        template_loader = ArtifactTemplateLoader()
        return template_loader.get_templates_for_mode(agent_mode)
