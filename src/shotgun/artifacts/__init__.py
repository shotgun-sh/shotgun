"""Artifact system for managing structured content in .shotgun directory."""

__all__ = [
    "ArtifactService",
    "ArtifactManager",
    "Artifact",
    "ArtifactSection",
    "ArtifactSummary",
    "AgentMode",
    "generate_artifact_name",
    "parse_agent_mode_string",
]

from .manager import ArtifactManager
from .models import AgentMode, Artifact, ArtifactSection, ArtifactSummary
from .service import ArtifactService
from .utils import generate_artifact_name, parse_agent_mode_string
