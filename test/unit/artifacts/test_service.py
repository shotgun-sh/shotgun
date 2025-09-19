"""Unit tests for artifacts.service module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from shotgun.artifacts.exceptions import (
    ArtifactAlreadyExistsError,
    ArtifactNotFoundError,
)
from shotgun.artifacts.models import AgentMode, Artifact
from shotgun.artifacts.service import ArtifactService


@pytest.fixture
def artifact_service():
    """Create ArtifactService instance."""
    with patch("shotgun.artifacts.service.ArtifactManager") as mock_manager_class:
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager
        service = ArtifactService()
        service.manager = mock_manager
        return service


@pytest.fixture
def sample_artifact():
    """Create sample artifact for testing."""
    artifact = MagicMock(spec=Artifact)
    artifact.artifact_id = "test-id"
    artifact.agent_mode = AgentMode.RESEARCH
    artifact.name = "Test Artifact"
    return artifact


def test_artifact_service_initialization():
    """Test ArtifactService initialization."""
    with patch("shotgun.artifacts.service.ArtifactManager") as mock_manager_class:
        service = ArtifactService()
        mock_manager_class.assert_called_once()
        assert service.manager is not None


def test_artifact_service_initialization_with_path():
    """Test ArtifactService initialization with custom path."""
    test_path = Path("/test/path")
    with patch("shotgun.artifacts.service.ArtifactManager") as mock_manager_class:
        ArtifactService(base_path=test_path)
        mock_manager_class.assert_called_once_with(test_path)


def test_create_artifact_without_template(artifact_service, sample_artifact):
    """Test creating artifact without template."""
    # Mock that artifact doesn't exist
    artifact_service.manager.artifact_exists.return_value = False

    result = artifact_service.create_artifact(
        "test-id", AgentMode.RESEARCH, "Test Artifact"
    )

    artifact_service.manager.create_artifact.assert_called_once()
    assert result.artifact_id == "test-id"
    assert result.agent_mode == AgentMode.RESEARCH
    assert result.name == "Test Artifact"


def test_create_artifact_with_template(artifact_service, sample_artifact):
    """Test creating artifact with template."""
    with patch("shotgun.artifacts.service.ArtifactTemplateLoader") as mock_loader_class:
        mock_loader = MagicMock()
        mock_template = MagicMock()
        mock_template.agent_mode = AgentMode.RESEARCH
        mock_template.to_yaml_dict.return_value = {"template": "data"}
        mock_loader.get_template.return_value = mock_template
        mock_loader_class.return_value = mock_loader

        # Mock that artifact doesn't exist
        artifact_service.manager.artifact_exists.return_value = False

        result = artifact_service.create_artifact(
            "test-id", AgentMode.RESEARCH, "Test Artifact", "research-template"
        )

        mock_loader.get_template.assert_called_once_with("research-template")
        artifact_service.manager.create_artifact.assert_called_once()
        artifact_service.manager.save_template_file.assert_called_once()
        assert result.artifact_id == "test-id"
        assert result.agent_mode == AgentMode.RESEARCH
        assert result.name == "Test Artifact"


def test_list_artifacts_all(artifact_service):
    """Test listing all artifacts."""
    mock_artifacts_data = [
        {
            "artifact_id": "artifact1",
            "agent_mode": AgentMode.RESEARCH,
            "section_count": 3,
            "created_at": MagicMock(),
            "updated_at": MagicMock(),
            "section_titles": ["Section 1", "Section 2"],
        },
        {
            "artifact_id": "artifact2",
            "agent_mode": AgentMode.PLAN,
            "section_count": 2,
            "created_at": MagicMock(),
            "updated_at": MagicMock(),
            "section_titles": ["Section A"],
        },
    ]
    artifact_service.manager.list_artifacts.return_value = mock_artifacts_data

    result = artifact_service.list_artifacts()

    artifact_service.manager.list_artifacts.assert_called_once_with(None)
    assert len(result) == 2
    assert result[0].artifact_id == "artifact1"
    assert result[1].artifact_id == "artifact2"


def test_list_artifacts_by_mode(artifact_service):
    """Test listing artifacts by agent mode."""
    mock_artifacts_data = [
        {
            "artifact_id": "artifact1",
            "agent_mode": AgentMode.RESEARCH,
            "section_count": 3,
            "created_at": MagicMock(),
            "updated_at": MagicMock(),
            "section_titles": ["Section 1"],
        }
    ]
    artifact_service.manager.list_artifacts.return_value = mock_artifacts_data

    result = artifact_service.list_artifacts(AgentMode.RESEARCH)

    artifact_service.manager.list_artifacts.assert_called_once_with(AgentMode.RESEARCH)
    assert len(result) == 1
    assert result[0].artifact_id == "artifact1"


def test_get_artifact(artifact_service, sample_artifact):
    """Test getting artifact by ID and agent mode."""
    artifact_service.manager.load_artifact.return_value = sample_artifact

    result = artifact_service.get_artifact("test-id", AgentMode.RESEARCH)

    artifact_service.manager.load_artifact.assert_called_once_with(
        AgentMode.RESEARCH, "test-id", ""
    )
    assert result == sample_artifact


def test_get_artifact_not_found(artifact_service):
    """Test getting non-existent artifact."""
    artifact_service.manager.load_artifact.side_effect = ArtifactNotFoundError(
        "Not found"
    )

    with pytest.raises(ArtifactNotFoundError):
        artifact_service.get_artifact("nonexistent", AgentMode.RESEARCH)


def test_update_artifact(artifact_service, sample_artifact):
    """Test updating artifact."""
    result = artifact_service.update_artifact(sample_artifact)

    artifact_service.manager.save_artifact.assert_called_once_with(sample_artifact)
    assert result == sample_artifact


def test_delete_artifact(artifact_service):
    """Test deleting artifact."""
    artifact_service.delete_artifact("test-id", AgentMode.RESEARCH)

    artifact_service.manager.delete_artifact.assert_called_once_with(
        AgentMode.RESEARCH, "test-id"
    )


def test_delete_artifact_not_found(artifact_service):
    """Test deleting non-existent artifact."""
    artifact_service.manager.delete_artifact.side_effect = ArtifactNotFoundError(
        "Not found"
    )

    with pytest.raises(ArtifactNotFoundError):
        artifact_service.delete_artifact("nonexistent", AgentMode.RESEARCH)


def test_add_section(artifact_service):
    """Test adding section to artifact."""
    from shotgun.artifacts.models import ArtifactSection

    # Mock artifact loading and section creation
    mock_artifact = MagicMock()
    mock_artifact.get_section_by_number.return_value = None  # No existing section
    mock_artifact.get_section_by_slug.return_value = None  # No existing section
    artifact_service.manager.load_artifact.return_value = mock_artifact

    section = ArtifactSection(
        number=1, slug="section-slug", title="Section Title", content="Content"
    )

    result = artifact_service.add_section("test-id", AgentMode.RESEARCH, section)

    artifact_service.manager.load_artifact.assert_called_once_with(
        AgentMode.RESEARCH, "test-id", ""
    )
    mock_artifact.add_section.assert_called_once_with(section)
    artifact_service.manager.write_section.assert_called_once_with(
        AgentMode.RESEARCH, "test-id", section
    )
    assert result == mock_artifact


def test_update_section(artifact_service):
    """Test updating artifact section."""
    # Mock artifact loading and section update
    mock_artifact = MagicMock()
    mock_artifact.update_section.return_value = True
    mock_section = MagicMock()
    mock_artifact.get_section_by_number.return_value = mock_section
    artifact_service.manager.load_artifact.return_value = mock_artifact

    result = artifact_service.update_section(
        "test-id", AgentMode.RESEARCH, 1, content="Updated content"
    )

    artifact_service.manager.load_artifact.assert_called_once_with(
        AgentMode.RESEARCH, "test-id", ""
    )
    mock_artifact.update_section.assert_called_once_with(1, content="Updated content")
    artifact_service.manager.update_section_file.assert_called_once_with(
        AgentMode.RESEARCH, "test-id", mock_section
    )
    assert result == mock_artifact


def test_delete_section(artifact_service):
    """Test deleting artifact section."""
    # Mock artifact loading and section deletion
    mock_artifact = MagicMock()
    mock_artifact.remove_section.return_value = True
    artifact_service.manager.load_artifact.return_value = mock_artifact

    result = artifact_service.delete_section("test-id", AgentMode.RESEARCH, 1)

    artifact_service.manager.load_artifact.assert_called_once_with(
        AgentMode.RESEARCH, "test-id", ""
    )
    mock_artifact.remove_section.assert_called_once_with(1)
    artifact_service.manager.delete_section_file.assert_called_once_with(
        AgentMode.RESEARCH, "test-id", 1
    )
    assert result == mock_artifact


def test_get_section_content(artifact_service):
    """Test getting artifact section content."""
    artifact_service.manager.read_section.return_value = "Section content"

    result = artifact_service.get_section_content("test-id", AgentMode.RESEARCH, 1)

    artifact_service.manager.read_section.assert_called_once_with(
        AgentMode.RESEARCH, "test-id", 1
    )
    assert result == "Section content"


def test_list_templates(artifact_service):
    """Test listing artifact templates."""
    with patch("shotgun.artifacts.service.ArtifactTemplateLoader") as mock_loader_class:
        mock_loader = MagicMock()
        mock_templates = [MagicMock(), MagicMock()]
        mock_loader.list_templates.return_value = mock_templates
        mock_loader_class.return_value = mock_loader

        result = artifact_service.list_templates()

        mock_loader.list_templates.assert_called_once()
        assert result == mock_templates


def test_create_artifact_already_exists(artifact_service):
    """Test create_artifact when artifact already exists."""
    artifact_service.manager.artifact_exists.return_value = True

    with pytest.raises(ArtifactAlreadyExistsError):
        artifact_service.create_artifact("test-id", AgentMode.RESEARCH, "Test Artifact")


@patch("shotgun.artifacts.service.ArtifactTemplateLoader")
def test_create_artifact_template_not_found(mock_loader_class, artifact_service):
    """Test create_artifact with invalid template."""
    artifact_service.manager.artifact_exists.return_value = False
    mock_loader = MagicMock()
    mock_loader.get_template.return_value = None
    mock_loader_class.return_value = mock_loader

    with pytest.raises(ValueError, match="Template 'invalid-template' not found"):
        artifact_service.create_artifact(
            "test-id",
            AgentMode.RESEARCH,
            "Test Artifact",
            template_id="invalid-template",
        )


@patch("shotgun.artifacts.service.ArtifactTemplateLoader")
def test_create_artifact_wrong_agent_mode_template(mock_loader_class, artifact_service):
    """Test create_artifact with template for wrong agent mode."""
    artifact_service.manager.artifact_exists.return_value = False
    mock_template = MagicMock()
    mock_template.agent_mode = AgentMode.PLAN
    mock_loader = MagicMock()
    mock_loader.get_template.return_value = mock_template
    mock_loader_class.return_value = mock_loader

    with pytest.raises(
        ValueError,
        match="Template 'plan-template' is for agent mode 'plan', but artifact is being created for 'research'",
    ):
        artifact_service.create_artifact(
            "test-id", AgentMode.RESEARCH, "Test Artifact", template_id="plan-template"
        )
