"""Utilities for collecting and organizing artifact state information."""

from datetime import datetime
from typing import TypedDict

from shotgun.artifacts.models import ArtifactSummary
from shotgun.artifacts.templates.models import TemplateSummary
from shotgun.sdk.services import get_artifact_service


class ArtifactState(TypedDict):
    """Type definition for artifact state information."""

    available_templates: dict[str, list[TemplateSummary]]
    existing_artifacts: dict[str, list[ArtifactSummary]]
    current_date: str


def collect_artifact_state() -> ArtifactState:
    """Collect and organize artifact state information for system context.

    Returns:
        ArtifactState containing organized templates and artifacts by mode, plus current date
    """
    artifact_service = get_artifact_service()

    # Get available templates
    available_templates_list = artifact_service.list_templates()

    # Group templates by mode for better organization
    templates_by_mode: dict[str, list[TemplateSummary]] = {}
    for template in available_templates_list:
        mode_name = template.template_id.split("/")[0]
        if mode_name not in templates_by_mode:
            templates_by_mode[mode_name] = []
        templates_by_mode[mode_name].append(template)

    # Get ALL existing artifacts regardless of current agent mode for complete visibility
    existing_artifacts_list = (
        artifact_service.list_artifacts()
    )  # No mode filter = all modes

    # Group artifacts by mode for organized display
    artifacts_by_mode: dict[str, list[ArtifactSummary]] = {}
    for artifact in existing_artifacts_list:
        mode_name = artifact.agent_mode.value
        if mode_name not in artifacts_by_mode:
            artifacts_by_mode[mode_name] = []
        artifacts_by_mode[mode_name].append(artifact)

    # Get current date for temporal context (month in words for clarity)
    current_date = datetime.now().strftime("%B %d, %Y")

    return {
        "available_templates": templates_by_mode,
        "existing_artifacts": artifacts_by_mode,
        "current_date": current_date,
    }
