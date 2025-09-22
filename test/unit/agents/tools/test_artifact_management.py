"""Unit tests for agents.tools.artifact_management module."""

from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic_ai import RunContext

from shotgun.agents.models import AgentDeps
from shotgun.agents.tools.artifact_management import (
    create_artifact,
    list_artifact_templates,
    list_artifacts,
    read_artifact,
    read_artifact_section,
    write_artifact_section,
)
from shotgun.artifacts.models import AgentMode
from shotgun.artifacts.service import ArtifactService


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
    service = create_autospec(ArtifactService, spec_set=True)
    service.create_artifact.return_value = mock_artifact
    service.list_artifacts.return_value = []
    service.get_artifact.return_value = mock_artifact
    service.get_section.return_value = MagicMock(
        title="Test Section", content="section content"
    )
    service.get_or_create_section.return_value = (MagicMock(), True)
    service.update_section.return_value = None
    service.list_templates.return_value = []
    return service


@pytest.fixture
def mock_context(mock_artifact_service):
    """Create mock RunContext with AgentDeps."""
    ctx = MagicMock(spec=RunContext)
    deps = MagicMock(spec=AgentDeps)
    deps.artifact_service = mock_artifact_service
    ctx.deps = deps
    return ctx


@pytest.mark.asyncio
async def test_create_artifact_basic(mock_context):
    """Test basic artifact creation."""
    result = await create_artifact(
        mock_context, "test-artifact", "research", "Test Artifact"
    )

    mock_context.deps.artifact_service.create_artifact.assert_called_once_with(
        "test-artifact", AgentMode.RESEARCH, "Test Artifact", None
    )
    assert "Created artifact 'test-artifact' in research mode" in result


@pytest.mark.asyncio
async def test_create_artifact_with_template(mock_context):
    """Test artifact creation with template."""
    result = await create_artifact(
        mock_context, "test-artifact", "research", "Test Artifact", "research-template"
    )

    mock_context.deps.artifact_service.create_artifact.assert_called_once_with(
        "test-artifact", AgentMode.RESEARCH, "Test Artifact", "research-template"
    )
    assert "Created artifact 'test-artifact' in research mode" in result


@pytest.mark.asyncio
async def test_create_artifact_error_handling(mock_context):
    """Test artifact creation error handling."""
    mock_context.deps.artifact_service.create_artifact.side_effect = Exception(
        "Creation failed"
    )

    result = await create_artifact(
        mock_context, "test-artifact", "research", "Test Artifact"
    )

    assert "Error: Failed to create artifact" in result
    assert "Creation failed" in result


@pytest.mark.asyncio
async def test_list_artifacts_all(mock_context):
    """Test listing all artifacts."""
    from datetime import datetime

    from shotgun.artifacts.models import ArtifactSummary

    mock_summaries = [
        ArtifactSummary(
            artifact_id="artifact1",
            name="Artifact 1",
            agent_mode=AgentMode.RESEARCH,
            section_count=3,
            created_at=datetime(2024, 1, 1),
            updated_at=datetime(2024, 1, 1),
        ),
        ArtifactSummary(
            artifact_id="artifact2",
            name="Artifact 2",
            agent_mode=AgentMode.PLAN,
            section_count=2,
            created_at=datetime(2024, 1, 2),
            updated_at=datetime(2024, 1, 2),
        ),
    ]
    mock_context.deps.artifact_service.list_artifacts.return_value = mock_summaries

    result = await list_artifacts(mock_context)

    mock_context.deps.artifact_service.list_artifacts.assert_called_once_with(None)
    assert "artifact1" in result
    assert "artifact2" in result
    assert "Total: 2 artifacts" in result


@pytest.mark.asyncio
async def test_list_artifacts_by_type(mock_context):
    """Test listing artifacts by type."""
    from datetime import datetime

    from shotgun.artifacts.models import ArtifactSummary

    mock_summaries = [
        ArtifactSummary(
            artifact_id="artifact1",
            name="Artifact 1",
            agent_mode=AgentMode.RESEARCH,
            section_count=3,
            created_at=datetime(2024, 1, 1),
            updated_at=datetime(2024, 1, 1),
        ),
    ]
    mock_context.deps.artifact_service.list_artifacts.return_value = mock_summaries

    result = await list_artifacts(mock_context, "research")

    mock_context.deps.artifact_service.list_artifacts.assert_called_once_with(
        AgentMode.RESEARCH
    )
    assert "artifact1" in result
    assert "Total: 1 artifacts" in result


@pytest.mark.asyncio
async def test_list_artifacts_error_handling(mock_context):
    """Test list artifacts error handling."""
    mock_context.deps.artifact_service.list_artifacts.side_effect = Exception(
        "List failed"
    )

    result = await list_artifacts(mock_context)

    assert "Error: Failed to list artifacts" in result
    assert "List failed" in result


@pytest.mark.asyncio
async def test_list_artifact_templates(mock_context):
    """Test listing artifact templates."""
    from shotgun.artifacts.templates.models import TemplateSummary

    mock_templates = [
        TemplateSummary(
            template_id="template1",
            name="Template 1",
            agent_mode=AgentMode.RESEARCH,
            purpose="Research template",
            section_count=3,
        ),
    ]
    mock_context.deps.artifact_service.list_templates.return_value = mock_templates

    result = await list_artifact_templates(mock_context, "research")

    mock_context.deps.artifact_service.list_templates.assert_called_once_with(
        AgentMode.RESEARCH
    )
    assert "template1" in result
    assert "Template 1" in result
    assert "Research template" in result


@pytest.mark.asyncio
async def test_list_artifact_templates_error_handling(mock_context):
    """Test list templates error handling."""
    mock_context.deps.artifact_service.list_templates.side_effect = Exception(
        "List failed"
    )

    result = await list_artifact_templates(mock_context)

    assert "Error: Failed to list templates" in result
    assert "List failed" in result


@pytest.mark.asyncio
async def test_read_artifact(mock_context):
    """Test reading an artifact."""
    mock_artifact = MagicMock()
    mock_artifact.name = "Test Artifact"
    mock_artifact.sections = [
        MagicMock(title="Section 1", content="Content 1", number=1),
    ]
    mock_artifact.has_template.return_value = False
    mock_artifact.get_ordered_sections.return_value = mock_artifact.sections

    mock_context.deps.artifact_service.get_artifact.return_value = mock_artifact

    result = await read_artifact(mock_context, "test-artifact", "research")

    mock_context.deps.artifact_service.get_artifact.assert_called_once_with(
        "test-artifact", AgentMode.RESEARCH, ""
    )
    assert "Test Artifact" in result
    assert "Section 1" in result
    assert "Content 1" in result


@pytest.mark.asyncio
async def test_read_artifact_error_handling(mock_context):
    """Test read artifact error handling."""
    mock_context.deps.artifact_service.get_artifact.side_effect = Exception(
        "Read failed"
    )

    result = await read_artifact(mock_context, "test-artifact", "research")

    assert "Error: Failed to read artifact" in result
    assert "Read failed" in result


@pytest.mark.asyncio
async def test_read_artifact_section(mock_context):
    """Test reading a specific artifact section."""
    mock_section = MagicMock()
    mock_section.title = "Test Section"
    mock_section.content = "Test content"
    mock_context.deps.artifact_service.get_section.return_value = mock_section

    result = await read_artifact_section(
        mock_context, "test-artifact", "research", 1
    )

    mock_context.deps.artifact_service.get_section.assert_called_once_with(
        "test-artifact", AgentMode.RESEARCH, 1
    )
    assert "Test Section" in result
    assert "Test content" in result


@pytest.mark.asyncio
async def test_read_artifact_section_error_handling(mock_context):
    """Test read artifact section error handling."""
    mock_context.deps.artifact_service.get_section.side_effect = Exception(
        "Section read failed"
    )

    result = await read_artifact_section(
        mock_context, "test-artifact", "research", 1
    )

    assert "Error: Failed to read section" in result
    assert "Section read failed" in result


@pytest.mark.asyncio
async def test_write_artifact_section(mock_context):
    """Test writing to an artifact section."""
    mock_section = MagicMock()
    mock_context.deps.artifact_service.get_or_create_section.return_value = (
        mock_section,
        True,  # created=True
    )

    result = await write_artifact_section(
        mock_context,
        "test-artifact",
        "research",
        1,
        "test-section",
        "Test Section",
        "Test content",
    )

    mock_context.deps.artifact_service.get_or_create_section.assert_called_once_with(
        "test-artifact",
        AgentMode.RESEARCH,
        1,
        "test-section",
        "Test Section",
        "Test content",
    )
    assert "Created section 1 'Test Section'" in result
    assert "with 12 characters" in result


@pytest.mark.asyncio
async def test_write_artifact_section_error_handling(mock_context):
    """Test write artifact section error handling."""
    mock_context.deps.artifact_service.get_or_create_section.side_effect = Exception(
        "Write failed"
    )

    result = await write_artifact_section(
        mock_context,
        "test-artifact",
        "research",
        1,
        "test-section",
        "Test Section",
        "Test content",
    )

    assert "Error: Failed to write section" in result
    assert "Write failed" in result


@pytest.mark.asyncio
async def test_write_artifact_section_update_existing(mock_context):
    """Test updating an existing artifact section."""
    mock_section = MagicMock()
    mock_context.deps.artifact_service.get_or_create_section.return_value = (
        mock_section,
        False,  # created=False (already exists)
    )

    result = await write_artifact_section(
        mock_context,
        "test-artifact",
        "research",
        1,
        "test-section",
        "Test Section",
        "Updated content",
    )

    mock_context.deps.artifact_service.update_section.assert_called_once_with(
        "test-artifact", AgentMode.RESEARCH, 1, content="Updated content"
    )
    assert "Updated section 1 'Test Section'" in result
    assert "with 15 characters" in result


@pytest.mark.asyncio
async def test_read_artifact_empty_sections(mock_context):
    """Test reading artifact with empty sections."""
    mock_artifact = MagicMock()
    mock_artifact.name = "Test Artifact"
    mock_artifact.sections = []
    mock_artifact.has_template.return_value = False

    mock_context.deps.artifact_service.get_artifact.return_value = mock_artifact

    result = await read_artifact(mock_context, "test-artifact", "research")

    assert "exists but has no sections" in result


@pytest.mark.asyncio
async def test_read_artifact_with_template(mock_context):
    """Test reading artifact with template information."""
    mock_artifact = MagicMock()
    mock_artifact.name = "Test Artifact"
    mock_artifact.sections = [
        MagicMock(title="Section 1", content="Content 1", number=1),
    ]
    mock_artifact.has_template.return_value = True
    mock_artifact.get_template_id.return_value = "test-template"
    mock_artifact.load_template_from_file.return_value = {
        "name": "Test Template",
        "purpose": "Testing",
        "prompt": "Test prompt",
        "sections": {
            "section1": {"instructions": "Do something", "order": 1},
        },
    }
    mock_artifact.get_ordered_sections.return_value = mock_artifact.sections

    mock_context.deps.artifact_service.get_artifact.return_value = mock_artifact

    result = await read_artifact(mock_context, "test-artifact", "research")

    assert "Test Artifact" in result
    assert "Template Information" in result
    assert "Test Template" in result
    assert "Testing" in result
    assert "Test prompt" in result
    assert "section1" in result
    assert "Do something" in result
