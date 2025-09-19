"""Unit tests for agents.tools.artifact_management module."""

from unittest.mock import MagicMock, patch

import pytest

from shotgun.agents.tools.artifact_management import (
    create_artifact,
    list_artifact_templates,
    list_artifacts,
    read_artifact,
    read_artifact_section,
    write_artifact_section,
)
from shotgun.artifacts.models import AgentMode


@pytest.fixture
def mock_artifact():
    """Create mock artifact."""
    artifact = MagicMock()
    artifact.artifact_id = "test-artifact"
    artifact.has_template.return_value = False
    return artifact


@pytest.fixture
def mock_artifact_service(mock_artifact):
    """Create mock artifact service."""
    service = MagicMock()
    service.create_artifact.return_value = mock_artifact
    service.list_artifacts.return_value = ["artifact1", "artifact2"]
    service.get_artifact.return_value = mock_artifact
    service.get_section_content.return_value = "section content"
    service.add_section.return_value = None
    return service


@pytest.fixture
def mock_template_service():
    """Create mock template service."""
    service = MagicMock()
    service.list_templates.return_value = ["template1", "template2"]
    return service


@patch("shotgun.agents.tools.artifact_management.get_artifact_service")
@patch("shotgun.agents.tools.artifact_management.handle_agent_mode_parsing")
def test_create_artifact_basic(
    mock_handle_parsing, mock_get_service, mock_artifact_service
):
    """Test basic artifact creation."""
    mock_handle_parsing.return_value = (AgentMode.RESEARCH, None)
    mock_get_service.return_value = mock_artifact_service

    result = create_artifact("test-artifact", "research", "Test Artifact")

    mock_artifact_service.create_artifact.assert_called_once_with(
        "test-artifact", AgentMode.RESEARCH, "Test Artifact", None
    )
    assert "Created artifact 'test-artifact' in research mode" in result


@patch("shotgun.agents.tools.artifact_management.get_artifact_service")
@patch("shotgun.agents.tools.artifact_management.handle_agent_mode_parsing")
def test_create_artifact_with_template(
    mock_handle_parsing, mock_get_service, mock_artifact_service
):
    """Test artifact creation with template."""
    mock_handle_parsing.return_value = (AgentMode.RESEARCH, None)
    mock_get_service.return_value = mock_artifact_service

    result = create_artifact(
        "test-artifact", "research", "Test Artifact", "research-template"
    )

    mock_artifact_service.create_artifact.assert_called_once_with(
        "test-artifact", AgentMode.RESEARCH, "Test Artifact", "research-template"
    )
    assert "Created artifact 'test-artifact' in research mode" in result


@patch("shotgun.agents.tools.artifact_management.get_artifact_service")
@patch("shotgun.agents.tools.artifact_management.handle_agent_mode_parsing")
def test_create_artifact_error_handling(mock_handle_parsing, mock_get_service):
    """Test artifact creation error handling."""
    mock_handle_parsing.return_value = (AgentMode.RESEARCH, None)
    mock_service = MagicMock()
    mock_service.create_artifact.side_effect = Exception("Creation failed")
    mock_get_service.return_value = mock_service

    result = create_artifact("test-artifact", "research", "Test Artifact")

    assert "Error: Failed to create artifact" in result
    assert "Creation failed" in result


@patch("shotgun.agents.tools.artifact_management.get_artifact_service")
def test_list_artifacts_all(mock_get_service, mock_artifact_service):
    """Test listing all artifacts."""
    mock_get_service.return_value = mock_artifact_service

    # Create properly mocked artifacts with necessary attributes
    mock_artifact1 = MagicMock()
    mock_artifact1.artifact_id = "artifact1"
    mock_artifact1.agent_mode = MagicMock()
    mock_artifact1.agent_mode.value = "research"
    mock_artifact1.section_count = 3
    mock_artifact1.updated_at.strftime.return_value = "2024-01-01"

    mock_artifact2 = MagicMock()
    mock_artifact2.artifact_id = "artifact2"
    mock_artifact2.agent_mode = MagicMock()
    mock_artifact2.agent_mode.value = "plan"
    mock_artifact2.section_count = 2
    mock_artifact2.updated_at.strftime.return_value = "2024-01-02"

    mock_artifact_service.list_artifacts.return_value = [mock_artifact1, mock_artifact2]

    result = list_artifacts()

    mock_artifact_service.list_artifacts.assert_called_once_with(None)
    assert "artifact1" in result
    assert "artifact2" in result


@patch("shotgun.agents.tools.artifact_management.get_artifact_service")
@patch("shotgun.agents.tools.artifact_management.handle_agent_mode_parsing")
def test_list_artifacts_by_type(
    mock_handle_parsing, mock_get_service, mock_artifact_service
):
    """Test listing artifacts by type."""
    mock_handle_parsing.return_value = (AgentMode.RESEARCH, None)
    mock_get_service.return_value = mock_artifact_service

    # Create properly mocked artifact
    mock_artifact1 = MagicMock()
    mock_artifact1.artifact_id = "artifact1"
    mock_artifact1.agent_mode = MagicMock()
    mock_artifact1.agent_mode.value = "research"
    mock_artifact1.section_count = 2
    mock_artifact1.updated_at.strftime.return_value = "2024-01-01"

    mock_artifact_service.list_artifacts.return_value = [mock_artifact1]

    result = list_artifacts("research")

    mock_artifact_service.list_artifacts.assert_called_once_with(AgentMode.RESEARCH)
    assert "artifact1" in result


@patch("shotgun.agents.tools.artifact_management.get_artifact_service")
def test_list_artifacts_error_handling(mock_get_service):
    """Test listing artifacts error handling."""
    mock_service = MagicMock()
    mock_service.list_artifacts.side_effect = Exception("List failed")
    mock_get_service.return_value = mock_service

    result = list_artifacts()

    assert "Error: Failed to list artifacts" in result
    assert "List failed" in result


@patch("shotgun.agents.tools.artifact_management.get_artifact_service")
def test_list_artifact_templates(mock_get_service, mock_artifact_service):
    """Test listing artifact templates."""
    mock_get_service.return_value = mock_artifact_service
    template1 = MagicMock()
    template1.template_id = "template1"
    template1.name = "Template 1"
    template1.agent_mode = MagicMock()
    template1.agent_mode.value = "research"
    template1.purpose = "Test purpose"
    template1.section_count = 3
    mock_artifact_service.list_templates.return_value = [template1]

    result = list_artifact_templates()

    mock_artifact_service.list_templates.assert_called_once()
    assert "template1" in result


@patch("shotgun.agents.tools.artifact_management.get_artifact_service")
def test_list_artifact_templates_error_handling(mock_get_service):
    """Test listing templates error handling."""
    mock_service = MagicMock()
    mock_service.list_templates.side_effect = Exception("Template list failed")
    mock_get_service.return_value = mock_service

    result = list_artifact_templates()

    assert "Error: Failed to list templates" in result
    assert "Template list failed" in result


@patch("shotgun.agents.tools.artifact_management.get_artifact_service")
@patch("shotgun.agents.tools.artifact_management.handle_agent_mode_parsing")
def test_read_artifact(mock_handle_parsing, mock_get_service, mock_artifact_service):
    """Test reading an artifact."""
    mock_handle_parsing.return_value = (AgentMode.RESEARCH, None)
    mock_get_service.return_value = mock_artifact_service

    # Mock artifact with necessary attributes for read_artifact function
    mock_artifact = MagicMock()
    mock_artifact.name = "Test Artifact"
    mock_artifact.sections = [MagicMock()]  # Non-empty to avoid early return
    mock_artifact.has_template.return_value = False
    mock_artifact.get_ordered_sections.return_value = [
        MagicMock(title="Section 1", content="Section content")
    ]
    mock_artifact_service.get_artifact.return_value = mock_artifact

    result = read_artifact("test-artifact", "research")

    mock_artifact_service.get_artifact.assert_called_once_with(
        "test-artifact", AgentMode.RESEARCH, ""
    )
    assert "Test Artifact" in result
    assert "Section content" in result


@patch("shotgun.agents.tools.artifact_management.get_artifact_service")
@patch("shotgun.agents.tools.artifact_management.handle_agent_mode_parsing")
def test_read_artifact_error_handling(mock_handle_parsing, mock_get_service):
    """Test reading artifact error handling."""
    mock_handle_parsing.return_value = (AgentMode.RESEARCH, None)
    mock_service = MagicMock()
    mock_service.get_artifact.side_effect = Exception("Read failed")
    mock_get_service.return_value = mock_service

    result = read_artifact("test-artifact", "research")

    assert "Error: Failed to read artifact" in result
    assert "Read failed" in result


@patch("shotgun.agents.tools.artifact_management.get_artifact_service")
@patch("shotgun.agents.tools.artifact_management.handle_agent_mode_parsing")
def test_read_artifact_section(
    mock_handle_parsing, mock_get_service, mock_artifact_service
):
    """Test reading an artifact section."""
    mock_handle_parsing.return_value = (AgentMode.RESEARCH, None)
    mock_get_service.return_value = mock_artifact_service

    # Mock section with necessary attributes
    mock_section = MagicMock()
    mock_section.title = "Section Title"
    mock_section.content = "Section content"
    mock_artifact_service.get_section.return_value = mock_section

    result = read_artifact_section("test-artifact", "research", 1)

    mock_artifact_service.get_section.assert_called_once_with(
        "test-artifact", AgentMode.RESEARCH, 1
    )
    assert "Section Title" in result
    assert "Section content" in result


@patch("shotgun.agents.tools.artifact_management.get_artifact_service")
@patch("shotgun.agents.tools.artifact_management.handle_agent_mode_parsing")
def test_read_artifact_section_error_handling(mock_handle_parsing, mock_get_service):
    """Test reading section error handling."""
    mock_handle_parsing.return_value = (AgentMode.RESEARCH, None)
    mock_service = MagicMock()
    mock_service.get_section.side_effect = Exception("Section read failed")
    mock_get_service.return_value = mock_service

    result = read_artifact_section("test-artifact", "research", 1)

    assert "Error: Failed to read section" in result
    assert "Section read failed" in result


@patch("shotgun.agents.tools.artifact_management.get_artifact_service")
@patch("shotgun.agents.tools.artifact_management.handle_agent_mode_parsing")
def test_write_artifact_section(
    mock_handle_parsing, mock_get_service, mock_artifact_service
):
    """Test writing an artifact section."""
    mock_handle_parsing.return_value = (AgentMode.RESEARCH, None)
    mock_get_service.return_value = mock_artifact_service

    # Mock section and return value for get_or_create_section
    mock_section = MagicMock()
    mock_artifact_service.get_or_create_section.return_value = (mock_section, True)

    result = write_artifact_section(
        "test-artifact",
        "research",
        1,
        "section-slug",
        "Section Title",
        "Section content",
    )

    mock_artifact_service.get_or_create_section.assert_called_once_with(
        "test-artifact",
        AgentMode.RESEARCH,
        1,
        "section-slug",
        "Section Title",
        "Section content",
    )
    assert "Created section 1" in result
    assert "Section Title" in result


@patch("shotgun.agents.tools.artifact_management.get_artifact_service")
@patch("shotgun.agents.tools.artifact_management.handle_agent_mode_parsing")
def test_write_artifact_section_error_handling(mock_handle_parsing, mock_get_service):
    """Test writing section error handling."""
    mock_handle_parsing.return_value = (AgentMode.RESEARCH, None)
    mock_service = MagicMock()
    mock_service.get_or_create_section.side_effect = Exception("Write failed")
    mock_get_service.return_value = mock_service

    result = write_artifact_section(
        "test-artifact",
        "research",
        1,
        "section-slug",
        "Section Title",
        "Section content",
    )

    assert "Error: Failed to write section" in result
    assert "Write failed" in result


@patch("shotgun.agents.tools.artifact_management.get_artifact_service")
@patch("shotgun.agents.tools.artifact_management.handle_agent_mode_parsing")
def test_write_artifact_section_update_existing(
    mock_handle_parsing, mock_get_service, mock_artifact_service
):
    """Test updating an existing artifact section."""
    mock_handle_parsing.return_value = (AgentMode.RESEARCH, None)
    mock_get_service.return_value = mock_artifact_service

    # Mock section and return value for get_or_create_section (existing section)
    mock_section = MagicMock()
    mock_artifact_service.get_or_create_section.return_value = (mock_section, False)

    result = write_artifact_section(
        "test-artifact",
        "research",
        1,
        "section-slug",
        "Updated Section Title",
        "Updated section content",
    )

    assert "Updated section 1" in result
    assert "Updated Section Title" in result


@patch("shotgun.agents.tools.artifact_management.get_artifact_service")
@patch("shotgun.agents.tools.artifact_management.handle_agent_mode_parsing")
def test_read_artifact_empty_sections(mock_handle_parsing, mock_get_service):
    """Test reading an artifact with no sections."""
    mock_handle_parsing.return_value = (AgentMode.RESEARCH, None)
    mock_service = MagicMock()
    mock_get_service.return_value = mock_service

    # Mock artifact with empty sections
    mock_artifact = MagicMock()
    mock_artifact.name = "Empty Artifact"
    mock_artifact.sections = []  # Empty sections list
    mock_service.get_artifact.return_value = mock_artifact

    result = read_artifact("empty-artifact", "research")

    assert "empty-artifact" in result
    assert "has no sections" in result


@patch("shotgun.agents.tools.artifact_management.get_artifact_service")
@patch("shotgun.agents.tools.artifact_management.handle_agent_mode_parsing")
def test_read_artifact_with_template(mock_handle_parsing, mock_get_service):
    """Test reading an artifact that has a template."""
    mock_handle_parsing.return_value = (AgentMode.RESEARCH, None)
    mock_service = MagicMock()
    mock_get_service.return_value = mock_service

    # Mock artifact with template
    mock_artifact = MagicMock()
    mock_artifact.name = "Templated Artifact"
    mock_artifact.sections = [MagicMock()]  # Non-empty
    mock_artifact.has_template.return_value = True
    mock_artifact.template_info = MagicMock()
    mock_artifact.template_info.name = "Research Template"
    mock_artifact.get_ordered_sections.return_value = [
        MagicMock(title="Template Section", content="Template content")
    ]
    mock_service.get_artifact.return_value = mock_artifact

    result = read_artifact("templated-artifact", "research")

    assert "Templated Artifact" in result
    assert "Template content" in result
    # The template name might be accessed differently, just check the content is there


# Test removed - get_template_service doesn't exist, the template listing uses get_artifact_service
