"""Integration test for artifact template functionality."""

import tempfile
from pathlib import Path

from shotgun.artifacts.models import AgentMode
from shotgun.artifacts.service import ArtifactService


def test_artifact_with_template():
    """Test creating an artifact with a template and loading template content from file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        service = ArtifactService(Path(temp_dir))

        # Create artifact with template
        artifact = service.create_artifact(
            "test-artifact",
            AgentMode.RESEARCH,
            "Test Artifact",
            "research/market_research",
        )

        # Verify artifact has template
        assert artifact.has_template(Path(temp_dir))
        assert artifact.get_template_id(Path(temp_dir)) == "research/market_research"

        # Load template from file
        template_content = artifact.load_template_from_file(Path(temp_dir))
        assert template_content is not None
        assert "name" in template_content
        assert template_content["name"] == "Market Research Template"
        assert "sections" in template_content

        # Verify template file was created
        template_path = Path(temp_dir) / "research" / "test-artifact" / ".template.yaml"
        assert template_path.exists()


def test_artifact_without_template():
    """Test creating an artifact without a template."""
    with tempfile.TemporaryDirectory() as temp_dir:
        service = ArtifactService(Path(temp_dir))

        # Create artifact without template
        artifact = service.create_artifact(
            "no-template-artifact", AgentMode.PLAN, "No Template Artifact"
        )

        # Verify artifact has no template
        assert not artifact.has_template(Path(temp_dir))
        assert artifact.get_template_id(Path(temp_dir)) is None

        # Loading template from file should return None
        template_content = artifact.load_template_from_file(Path(temp_dir))
        assert template_content is None

        # Verify no template file was created
        template_path = (
            Path(temp_dir) / "plan" / "no-template-artifact" / ".template.yaml"
        )
        assert not template_path.exists()
