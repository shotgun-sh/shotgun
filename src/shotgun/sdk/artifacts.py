"""Artifact SDK for framework-agnostic business logic."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from shotgun.artifacts.exceptions import (
    ArtifactAlreadyExistsError,
    ArtifactError,
    ArtifactNotFoundError,
    SectionAlreadyExistsError,
    SectionNotFoundError,
)
from shotgun.artifacts.models import AgentMode, ArtifactSection
from shotgun.artifacts.service import ArtifactService
from shotgun.artifacts.utils import generate_artifact_name

from .artifact_models import (
    ArtifactCreateResult,
    ArtifactDeleteResult,
    ArtifactErrorResult,
    ArtifactInfoResult,
    ArtifactListResult,
    SectionContentResult,
    SectionCreateResult,
    SectionDeleteResult,
    SectionUpdateResult,
)


class ArtifactSDK:
    """Framework-agnostic SDK for artifact operations.

    This SDK provides business logic for artifact management that can be
    used by both CLI and TUI implementations without framework dependencies.
    """

    def __init__(self, base_path: Path | None = None):
        """Initialize SDK with optional base path.

        Args:
            base_path: Optional custom base path for artifacts.
                      Defaults to .shotgun in current directory.
        """
        self.service = ArtifactService(base_path)

    # Artifact operations

    def list_artifacts(
        self, agent_mode: AgentMode | None = None
    ) -> ArtifactListResult | ArtifactErrorResult:
        """List all artifacts, optionally filtered by agent mode.

        Args:
            agent_mode: Optional agent mode filter

        Returns:
            ArtifactListResult containing list of artifacts or ArtifactErrorResult
        """
        try:
            artifacts = self.service.list_artifacts(agent_mode)
            return ArtifactListResult(artifacts=artifacts, agent_mode=agent_mode)
        except ArtifactError as e:
            return ArtifactErrorResult(error_message=str(e), agent_mode=agent_mode)

    def create_artifact(
        self,
        artifact_id: str,
        agent_mode: AgentMode,
        name: str,
        template_id: str | None = None,
    ) -> ArtifactCreateResult | ArtifactErrorResult:
        """Create a new artifact.

        Args:
            artifact_id: Unique identifier for the artifact
            agent_mode: Agent mode this artifact belongs to
            name: Human-readable name for the artifact
            template_id: Optional template ID to use for creating the artifact

        Returns:
            ArtifactCreateResult or ArtifactErrorResult
        """
        try:
            self.service.create_artifact(artifact_id, agent_mode, name, template_id)
            return ArtifactCreateResult(
                artifact_id=artifact_id,
                agent_mode=agent_mode,
                name=name,
            )
        except ArtifactAlreadyExistsError as e:
            return ArtifactErrorResult(
                error_message="Artifact already exists",
                artifact_id=artifact_id,
                agent_mode=agent_mode,
                details=str(e),
            )
        except ArtifactError as e:
            return ArtifactErrorResult(
                error_message=str(e),
                artifact_id=artifact_id,
                agent_mode=agent_mode,
            )

    def delete_artifact(
        self,
        artifact_id: str,
        agent_mode: AgentMode,
        confirm_callback: Callable[[str, AgentMode], bool] | None = None,
    ) -> ArtifactDeleteResult | ArtifactErrorResult:
        """Delete an artifact with optional confirmation.

        Args:
            artifact_id: ID of the artifact to delete
            agent_mode: Agent mode
            confirm_callback: Optional callback for confirmation that receives
                            artifact_id and agent_mode and returns boolean.

        Returns:
            ArtifactDeleteResult or ArtifactErrorResult
        """
        try:
            # Handle confirmation callback if provided
            if confirm_callback and not confirm_callback(artifact_id, agent_mode):
                return ArtifactDeleteResult(
                    artifact_id=artifact_id,
                    agent_mode=agent_mode,
                    deleted=False,
                    cancelled=True,
                )

            self.service.delete_artifact(artifact_id, agent_mode)
            return ArtifactDeleteResult(
                artifact_id=artifact_id,
                agent_mode=agent_mode,
                deleted=True,
            )
        except ArtifactNotFoundError as e:
            return ArtifactErrorResult(
                error_message="Artifact not found",
                artifact_id=artifact_id,
                agent_mode=agent_mode,
                details=str(e),
            )
        except ArtifactError as e:
            return ArtifactErrorResult(
                error_message=str(e),
                artifact_id=artifact_id,
                agent_mode=agent_mode,
            )

    def get_artifact_info(
        self, artifact_id: str, agent_mode: AgentMode
    ) -> ArtifactInfoResult | ArtifactErrorResult:
        """Get detailed information about an artifact.

        Args:
            artifact_id: ID of the artifact to get info for
            agent_mode: Agent mode

        Returns:
            ArtifactInfoResult or ArtifactErrorResult
        """
        try:
            artifact = self.service.get_artifact(artifact_id, agent_mode, "")
            return ArtifactInfoResult(artifact=artifact)
        except ArtifactNotFoundError as e:
            return ArtifactErrorResult(
                error_message="Artifact not found",
                artifact_id=artifact_id,
                agent_mode=agent_mode,
                details=str(e),
            )
        except ArtifactError as e:
            return ArtifactErrorResult(
                error_message=str(e),
                artifact_id=artifact_id,
                agent_mode=agent_mode,
            )

    # Section operations

    def create_section(
        self,
        artifact_id: str,
        agent_mode: AgentMode,
        section_number: int,
        section_slug: str,
        section_title: str,
        content: str = "",
    ) -> SectionCreateResult | ArtifactErrorResult:
        """Create a new section in an artifact.

        Args:
            artifact_id: Artifact identifier
            agent_mode: Agent mode
            section_number: Section number
            section_slug: Section slug
            section_title: Section title
            content: Section content

        Returns:
            SectionCreateResult or ArtifactErrorResult
        """
        try:
            section = ArtifactSection(
                number=section_number,
                slug=section_slug,
                title=section_title,
                content=content,
            )
            self.service.add_section(artifact_id, agent_mode, section)
            return SectionCreateResult(
                artifact_id=artifact_id,
                agent_mode=agent_mode,
                section_number=section_number,
                section_title=section_title,
            )
        except (SectionAlreadyExistsError, ArtifactNotFoundError) as e:
            return ArtifactErrorResult(
                error_message=str(e),
                artifact_id=artifact_id,
                agent_mode=agent_mode,
                section_number=section_number,
            )
        except ArtifactError as e:
            return ArtifactErrorResult(
                error_message=str(e),
                artifact_id=artifact_id,
                agent_mode=agent_mode,
                section_number=section_number,
            )

    def update_section(
        self,
        artifact_id: str,
        agent_mode: AgentMode,
        section_number: int,
        **kwargs: Any,
    ) -> SectionUpdateResult | ArtifactErrorResult:
        """Update a section in an artifact.

        Args:
            artifact_id: Artifact identifier
            agent_mode: Agent mode
            section_number: Section number to update
            **kwargs: Fields to update

        Returns:
            SectionUpdateResult or ArtifactErrorResult
        """
        try:
            self.service.update_section(
                artifact_id, agent_mode, section_number, **kwargs
            )
            return SectionUpdateResult(
                artifact_id=artifact_id,
                agent_mode=agent_mode,
                section_number=section_number,
                updated_fields=list(kwargs.keys()),
            )
        except (SectionNotFoundError, ArtifactNotFoundError) as e:
            return ArtifactErrorResult(
                error_message=str(e),
                artifact_id=artifact_id,
                agent_mode=agent_mode,
                section_number=section_number,
            )
        except ArtifactError as e:
            return ArtifactErrorResult(
                error_message=str(e),
                artifact_id=artifact_id,
                agent_mode=agent_mode,
                section_number=section_number,
            )

    def delete_section(
        self,
        artifact_id: str,
        agent_mode: AgentMode,
        section_number: int,
    ) -> SectionDeleteResult | ArtifactErrorResult:
        """Delete a section from an artifact.

        Args:
            artifact_id: Artifact identifier
            agent_mode: Agent mode
            section_number: Section number to delete

        Returns:
            SectionDeleteResult or ArtifactErrorResult
        """
        try:
            self.service.delete_section(artifact_id, agent_mode, section_number)
            return SectionDeleteResult(
                artifact_id=artifact_id,
                agent_mode=agent_mode,
                section_number=section_number,
            )
        except (SectionNotFoundError, ArtifactNotFoundError) as e:
            return ArtifactErrorResult(
                error_message=str(e),
                artifact_id=artifact_id,
                agent_mode=agent_mode,
                section_number=section_number,
            )
        except ArtifactError as e:
            return ArtifactErrorResult(
                error_message=str(e),
                artifact_id=artifact_id,
                agent_mode=agent_mode,
                section_number=section_number,
            )

    def get_section_content(
        self,
        artifact_id: str,
        agent_mode: AgentMode,
        section_number: int,
    ) -> SectionContentResult | ArtifactErrorResult:
        """Get the content of a section.

        Args:
            artifact_id: Artifact identifier
            agent_mode: Agent mode
            section_number: Section number

        Returns:
            SectionContentResult or ArtifactErrorResult
        """
        try:
            content = self.service.get_section_content(
                artifact_id, agent_mode, section_number
            )
            return SectionContentResult(
                artifact_id=artifact_id,
                agent_mode=agent_mode,
                section_number=section_number,
                content=content,
            )
        except (SectionNotFoundError, ArtifactNotFoundError) as e:
            return ArtifactErrorResult(
                error_message=str(e),
                artifact_id=artifact_id,
                agent_mode=agent_mode,
                section_number=section_number,
            )
        except ArtifactError as e:
            return ArtifactErrorResult(
                error_message=str(e),
                artifact_id=artifact_id,
                agent_mode=agent_mode,
                section_number=section_number,
            )

    # Template operations

    def list_templates(
        self, agent_mode: AgentMode | None = None
    ) -> list[Any] | ArtifactErrorResult:
        """List available artifact templates.

        Args:
            agent_mode: Optional agent mode filter

        Returns:
            List of template summaries or ArtifactErrorResult
        """
        try:
            return self.service.list_templates(agent_mode)
        except Exception as e:
            return ArtifactErrorResult(
                error_message=f"Failed to list templates: {str(e)}",
                agent_mode=agent_mode,
            )

    # Convenience methods

    def ensure_artifact_exists(
        self,
        artifact_id: str,
        agent_mode: AgentMode,
        name: str | None = None,
    ) -> ArtifactCreateResult | ArtifactInfoResult | ArtifactErrorResult:
        """Ensure an artifact exists, creating it if necessary.

        Args:
            artifact_id: Artifact identifier
            agent_mode: Agent mode
            name: Optional name (defaults to formatted artifact_id)

        Returns:
            ArtifactCreateResult if created, ArtifactInfoResult if already existed, ArtifactErrorResult on error
        """
        if name is None:
            name = generate_artifact_name(artifact_id)

        # Try to get existing artifact
        info_result = self.get_artifact_info(artifact_id, agent_mode)
        if isinstance(info_result, ArtifactInfoResult):
            return info_result

        # Create new artifact
        create_result = self.create_artifact(artifact_id, agent_mode, name)
        return create_result

    def ensure_section_exists(
        self,
        artifact_id: str,
        agent_mode: AgentMode,
        section_number: int,
        section_slug: str,
        section_title: str,
        initial_content: str = "",
    ) -> SectionCreateResult | SectionContentResult | ArtifactErrorResult:
        """Ensure a section exists, creating it if necessary.

        Args:
            artifact_id: Artifact identifier
            agent_mode: Agent mode
            section_number: Section number
            section_slug: Section slug
            section_title: Section title
            initial_content: Initial content for new sections

        Returns:
            SectionCreateResult if created, SectionContentResult if already existed, ArtifactErrorResult on error
        """
        # Try to get existing section
        content_result = self.get_section_content(
            artifact_id, agent_mode, section_number
        )
        if isinstance(content_result, SectionContentResult):
            return content_result

        # Ensure artifact exists first
        self.ensure_artifact_exists(artifact_id, agent_mode)

        # Create new section
        create_result = self.create_section(
            artifact_id,
            agent_mode,
            section_number,
            section_slug,
            section_title,
            initial_content,
        )
        return create_result
