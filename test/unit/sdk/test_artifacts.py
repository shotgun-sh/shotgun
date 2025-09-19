"""Unit tests for sdk.artifacts module."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from shotgun.artifacts.exceptions import (
    ArtifactAlreadyExistsError,
    ArtifactError,
    ArtifactNotFoundError,
    SectionAlreadyExistsError,
    SectionNotFoundError,
)
from shotgun.artifacts.models import (
    AgentMode,
    Artifact,
    ArtifactSection,
    ArtifactSummary,
)
from shotgun.sdk.artifact_models import (
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
from shotgun.sdk.artifacts import ArtifactSDK


@pytest.fixture
def mock_service():
    """Create a mock artifact service."""
    return MagicMock()


@pytest.fixture
def sdk(mock_service):
    """Create SDK instance with mocked service."""
    with patch("shotgun.sdk.artifacts.ArtifactService") as mock_service_class:
        mock_service_class.return_value = mock_service
        return ArtifactSDK()


@pytest.fixture
def sample_artifact():
    """Create sample artifact."""
    return Artifact(
        artifact_id="test-artifact",
        agent_mode=AgentMode.RESEARCH,
        name="Test Artifact",
        sections=[],
    )


@pytest.fixture
def sample_artifact_summary():
    """Create sample artifact summary."""
    from datetime import datetime

    return ArtifactSummary(
        artifact_id="test-artifact",
        agent_mode=AgentMode.RESEARCH,
        name="Test Artifact",
        section_count=2,
        created_at=datetime(2024, 1, 1, 10, 0, 0),
        updated_at=datetime(2024, 1, 1, 12, 0, 0),
        section_titles=["Section 1", "Section 2"],
        template_id=None,
    )


def test_sdk_initialization():
    """Test SDK initialization."""
    with patch("shotgun.sdk.artifacts.ArtifactService") as mock_service_class:
        # Test with default path
        ArtifactSDK()
        mock_service_class.assert_called_once_with(None)

        # Test with custom path
        custom_path = Path("/custom/path")
        ArtifactSDK(custom_path)
        mock_service_class.assert_called_with(custom_path)


def test_list_artifacts_success(sdk, mock_service, sample_artifact_summary):
    """Test successful artifact listing."""
    mock_service.list_artifacts.return_value = [sample_artifact_summary]

    result = sdk.list_artifacts()

    assert isinstance(result, ArtifactListResult)
    assert len(result.artifacts) == 1
    assert result.artifacts[0] == sample_artifact_summary
    assert result.agent_mode is None
    mock_service.list_artifacts.assert_called_once_with(None)


def test_list_artifacts_with_filter(sdk, mock_service, sample_artifact_summary):
    """Test artifact listing with agent mode filter."""
    mock_service.list_artifacts.return_value = [sample_artifact_summary]

    result = sdk.list_artifacts(AgentMode.RESEARCH)

    assert isinstance(result, ArtifactListResult)
    assert result.agent_mode == AgentMode.RESEARCH
    mock_service.list_artifacts.assert_called_once_with(AgentMode.RESEARCH)


def test_list_artifacts_error(sdk, mock_service):
    """Test artifact listing error handling."""
    mock_service.list_artifacts.side_effect = ArtifactError("Service error")

    result = sdk.list_artifacts()

    assert isinstance(result, ArtifactErrorResult)
    assert result.error_message == "Service error"
    assert result.agent_mode is None


def test_create_artifact_success(sdk, mock_service):
    """Test successful artifact creation."""
    result = sdk.create_artifact(
        "test-artifact", AgentMode.RESEARCH, "Test Artifact", "template-1"
    )

    assert isinstance(result, ArtifactCreateResult)
    assert result.artifact_id == "test-artifact"
    assert result.agent_mode == AgentMode.RESEARCH
    assert result.name == "Test Artifact"
    assert result.created is True

    mock_service.create_artifact.assert_called_once_with(
        "test-artifact", AgentMode.RESEARCH, "Test Artifact", "template-1"
    )


def test_create_artifact_already_exists(sdk, mock_service):
    """Test artifact creation when artifact already exists."""
    mock_service.create_artifact.side_effect = ArtifactAlreadyExistsError(
        "test-artifact", "research"
    )

    result = sdk.create_artifact("test-artifact", AgentMode.RESEARCH, "Test Artifact")

    assert isinstance(result, ArtifactErrorResult)
    assert result.error_message == "Artifact already exists"
    assert result.artifact_id == "test-artifact"
    assert result.agent_mode == AgentMode.RESEARCH


def test_create_artifact_general_error(sdk, mock_service):
    """Test artifact creation general error handling."""
    mock_service.create_artifact.side_effect = ArtifactError("General error")

    result = sdk.create_artifact("test-artifact", AgentMode.RESEARCH, "Test Artifact")

    assert isinstance(result, ArtifactErrorResult)
    assert result.error_message == "General error"
    assert result.artifact_id == "test-artifact"
    assert result.agent_mode == AgentMode.RESEARCH


def test_delete_artifact_success(sdk, mock_service):
    """Test successful artifact deletion."""
    result = sdk.delete_artifact("test-artifact", AgentMode.RESEARCH)

    assert isinstance(result, ArtifactDeleteResult)
    assert result.artifact_id == "test-artifact"
    assert result.agent_mode == AgentMode.RESEARCH
    assert result.deleted is True
    assert result.cancelled is False

    mock_service.delete_artifact.assert_called_once_with(
        "test-artifact", AgentMode.RESEARCH
    )


def test_delete_artifact_with_confirmation_accepted(sdk, mock_service):
    """Test artifact deletion with confirmation callback that accepts."""
    confirm_callback = Mock(return_value=True)

    result = sdk.delete_artifact("test-artifact", AgentMode.RESEARCH, confirm_callback)

    assert isinstance(result, ArtifactDeleteResult)
    assert result.deleted is True
    assert result.cancelled is False

    confirm_callback.assert_called_once_with("test-artifact", AgentMode.RESEARCH)
    mock_service.delete_artifact.assert_called_once()


def test_delete_artifact_with_confirmation_rejected(sdk, mock_service):
    """Test artifact deletion with confirmation callback that rejects."""
    confirm_callback = Mock(return_value=False)

    result = sdk.delete_artifact("test-artifact", AgentMode.RESEARCH, confirm_callback)

    assert isinstance(result, ArtifactDeleteResult)
    assert result.deleted is False
    assert result.cancelled is True

    confirm_callback.assert_called_once_with("test-artifact", AgentMode.RESEARCH)
    mock_service.delete_artifact.assert_not_called()


def test_delete_artifact_not_found(sdk, mock_service):
    """Test deleting non-existent artifact."""
    mock_service.delete_artifact.side_effect = ArtifactNotFoundError(
        "test-artifact", "research"
    )

    result = sdk.delete_artifact("test-artifact", AgentMode.RESEARCH)

    assert isinstance(result, ArtifactErrorResult)
    assert "not found" in result.error_message.lower()


def test_delete_artifact_general_error(sdk, mock_service):
    """Test delete artifact general error handling."""
    mock_service.delete_artifact.side_effect = ArtifactError("General error")

    result = sdk.delete_artifact("test-artifact", AgentMode.RESEARCH)

    assert isinstance(result, ArtifactErrorResult)
    assert result.error_message == "General error"


def test_get_artifact_info_success(sdk, mock_service, sample_artifact):
    """Test successful artifact info retrieval."""
    mock_service.get_artifact.return_value = sample_artifact

    result = sdk.get_artifact_info("test-artifact", AgentMode.RESEARCH)

    assert isinstance(result, ArtifactInfoResult)
    assert result.artifact == sample_artifact

    mock_service.get_artifact.assert_called_once_with(
        "test-artifact", AgentMode.RESEARCH, ""
    )


def test_get_artifact_info_not_found(sdk, mock_service):
    """Test artifact info when artifact not found."""
    mock_service.get_artifact.side_effect = ArtifactNotFoundError(
        "test-artifact", "research"
    )

    result = sdk.get_artifact_info("test-artifact", AgentMode.RESEARCH)

    assert isinstance(result, ArtifactErrorResult)
    assert "not found" in result.error_message.lower()


def test_get_artifact_info_general_error(sdk, mock_service):
    """Test artifact info general error handling."""
    mock_service.get_artifact.side_effect = ArtifactError("General error")

    result = sdk.get_artifact_info("test-artifact", AgentMode.RESEARCH)

    assert isinstance(result, ArtifactErrorResult)
    assert result.error_message == "General error"


def test_create_section_success(sdk, mock_service):
    """Test successful section creation."""
    result = sdk.create_section(
        "test-artifact", AgentMode.RESEARCH, 1, "intro", "Introduction", "Content"
    )

    assert isinstance(result, SectionCreateResult)
    assert result.artifact_id == "test-artifact"
    assert result.agent_mode == AgentMode.RESEARCH
    assert result.section_number == 1
    assert result.section_title == "Introduction"
    assert result.created is True

    mock_service.add_section.assert_called_once()
    call_args = mock_service.add_section.call_args

    assert call_args[0][0] == "test-artifact"
    assert call_args[0][1] == AgentMode.RESEARCH

    # Check the ArtifactSection that was passed
    section = call_args[0][2]
    assert isinstance(section, ArtifactSection)
    assert section.number == 1
    assert section.slug == "intro"
    assert section.title == "Introduction"
    assert section.content == "Content"


def test_create_section_already_exists(sdk, mock_service):
    """Test section creation when section already exists."""
    mock_service.add_section.side_effect = SectionAlreadyExistsError(1, "test-artifact")

    result = sdk.create_section(
        "test-artifact", AgentMode.RESEARCH, 1, "intro", "Introduction"
    )

    assert isinstance(result, ArtifactErrorResult)
    assert "already exists" in result.error_message.lower()
    assert result.section_number == 1


def test_create_section_artifact_not_found(sdk, mock_service):
    """Test section creation when artifact not found."""
    mock_service.add_section.side_effect = ArtifactNotFoundError(
        "test-artifact", "research"
    )

    result = sdk.create_section(
        "test-artifact", AgentMode.RESEARCH, 1, "intro", "Introduction"
    )

    assert isinstance(result, ArtifactErrorResult)
    assert "not found" in result.error_message.lower()


def test_create_section_general_error(sdk, mock_service):
    """Test section creation general error handling."""
    mock_service.add_section.side_effect = ArtifactError("General error")

    result = sdk.create_section(
        "test-artifact", AgentMode.RESEARCH, 1, "intro", "Introduction"
    )

    assert isinstance(result, ArtifactErrorResult)
    assert result.error_message == "General error"


def test_update_section_success(sdk, mock_service):
    """Test successful section update."""
    result = sdk.update_section(
        "test-artifact", AgentMode.RESEARCH, 1, title="New Title", content="New Content"
    )

    assert isinstance(result, SectionUpdateResult)
    assert result.artifact_id == "test-artifact"
    assert result.agent_mode == AgentMode.RESEARCH
    assert result.section_number == 1
    assert set(result.updated_fields) == {"title", "content"}

    mock_service.update_section.assert_called_once_with(
        "test-artifact", AgentMode.RESEARCH, 1, title="New Title", content="New Content"
    )


def test_update_section_not_found(sdk, mock_service):
    """Test section update when section not found."""
    mock_service.update_section.side_effect = SectionNotFoundError(1, "test-artifact")

    result = sdk.update_section(
        "test-artifact", AgentMode.RESEARCH, 1, title="New Title"
    )

    assert isinstance(result, ArtifactErrorResult)
    assert "not found" in result.error_message.lower()
    assert result.section_number == 1


def test_update_section_artifact_not_found(sdk, mock_service):
    """Test section update when artifact not found."""
    mock_service.update_section.side_effect = ArtifactNotFoundError(
        "test-artifact", "research"
    )

    result = sdk.update_section(
        "test-artifact", AgentMode.RESEARCH, 1, title="New Title"
    )

    assert isinstance(result, ArtifactErrorResult)
    assert "not found" in result.error_message.lower()


def test_update_section_general_error(sdk, mock_service):
    """Test section update general error handling."""
    mock_service.update_section.side_effect = ArtifactError("General error")

    result = sdk.update_section(
        "test-artifact", AgentMode.RESEARCH, 1, title="New Title"
    )

    assert isinstance(result, ArtifactErrorResult)
    assert result.error_message == "General error"


def test_delete_section_success(sdk, mock_service):
    """Test successful section deletion."""
    result = sdk.delete_section("test-artifact", AgentMode.RESEARCH, 1)

    assert isinstance(result, SectionDeleteResult)
    assert result.artifact_id == "test-artifact"
    assert result.agent_mode == AgentMode.RESEARCH
    assert result.section_number == 1
    assert result.deleted is True

    mock_service.delete_section.assert_called_once_with(
        "test-artifact", AgentMode.RESEARCH, 1
    )


def test_delete_section_not_found(sdk, mock_service):
    """Test section deletion when section not found."""
    mock_service.delete_section.side_effect = SectionNotFoundError(1, "test-artifact")

    result = sdk.delete_section("test-artifact", AgentMode.RESEARCH, 1)

    assert isinstance(result, ArtifactErrorResult)
    assert "not found" in result.error_message.lower()


def test_delete_section_artifact_not_found(sdk, mock_service):
    """Test section deletion when artifact not found."""
    mock_service.delete_section.side_effect = ArtifactNotFoundError(
        "test-artifact", "research"
    )

    result = sdk.delete_section("test-artifact", AgentMode.RESEARCH, 1)

    assert isinstance(result, ArtifactErrorResult)
    assert "not found" in result.error_message.lower()


def test_delete_section_general_error(sdk, mock_service):
    """Test section deletion general error handling."""
    mock_service.delete_section.side_effect = ArtifactError("General error")

    result = sdk.delete_section("test-artifact", AgentMode.RESEARCH, 1)

    assert isinstance(result, ArtifactErrorResult)
    assert result.error_message == "General error"


def test_get_section_content_success(sdk, mock_service):
    """Test successful section content retrieval."""
    mock_service.get_section_content.return_value = "Section content"

    result = sdk.get_section_content("test-artifact", AgentMode.RESEARCH, 1)

    assert isinstance(result, SectionContentResult)
    assert result.artifact_id == "test-artifact"
    assert result.agent_mode == AgentMode.RESEARCH
    assert result.section_number == 1
    assert result.content == "Section content"

    mock_service.get_section_content.assert_called_once_with(
        "test-artifact", AgentMode.RESEARCH, 1
    )


def test_get_section_content_section_not_found(sdk, mock_service):
    """Test section content when section not found."""
    mock_service.get_section_content.side_effect = SectionNotFoundError(
        1, "test-artifact"
    )

    result = sdk.get_section_content("test-artifact", AgentMode.RESEARCH, 1)

    assert isinstance(result, ArtifactErrorResult)
    assert "not found" in result.error_message.lower()


def test_get_section_content_artifact_not_found(sdk, mock_service):
    """Test section content when artifact not found."""
    mock_service.get_section_content.side_effect = ArtifactNotFoundError(
        "test-artifact", "research"
    )

    result = sdk.get_section_content("test-artifact", AgentMode.RESEARCH, 1)

    assert isinstance(result, ArtifactErrorResult)
    assert "not found" in result.error_message.lower()


def test_get_section_content_general_error(sdk, mock_service):
    """Test section content general error handling."""
    mock_service.get_section_content.side_effect = ArtifactError("General error")

    result = sdk.get_section_content("test-artifact", AgentMode.RESEARCH, 1)

    assert isinstance(result, ArtifactErrorResult)
    assert result.error_message == "General error"


def test_list_templates_success(sdk, mock_service):
    """Test successful template listing."""
    templates = [{"id": "template-1", "name": "Template 1"}]
    mock_service.list_templates.return_value = templates

    result = sdk.list_templates()

    assert result == templates
    mock_service.list_templates.assert_called_once_with(None)


def test_list_templates_with_filter(sdk, mock_service):
    """Test template listing with agent mode filter."""
    templates = [{"id": "template-1", "name": "Template 1"}]
    mock_service.list_templates.return_value = templates

    result = sdk.list_templates(AgentMode.RESEARCH)

    assert result == templates
    mock_service.list_templates.assert_called_once_with(AgentMode.RESEARCH)


def test_list_templates_error(sdk, mock_service):
    """Test template listing error handling."""
    mock_service.list_templates.side_effect = Exception("Template error")

    result = sdk.list_templates()

    assert isinstance(result, ArtifactErrorResult)
    assert result.error_message == "Failed to list templates: Template error"


def test_ensure_artifact_exists_already_exists(sdk, mock_service, sample_artifact):
    """Test ensure_artifact_exists when artifact already exists."""
    mock_service.get_artifact.return_value = sample_artifact

    result = sdk.ensure_artifact_exists("test-artifact", AgentMode.RESEARCH)

    assert isinstance(result, ArtifactInfoResult)
    assert result.artifact == sample_artifact


def test_ensure_artifact_exists_create_new(sdk, mock_service):
    """Test ensure_artifact_exists when artifact doesn't exist."""
    # First call (get_artifact) fails, second call (create_artifact) succeeds
    mock_service.get_artifact.side_effect = ArtifactNotFoundError(
        "test-artifact", "research"
    )

    result = sdk.ensure_artifact_exists("test-artifact", AgentMode.RESEARCH)

    assert isinstance(result, ArtifactCreateResult)
    assert result.artifact_id == "test-artifact"
    assert result.agent_mode == AgentMode.RESEARCH


def test_ensure_artifact_exists_with_custom_name(sdk, mock_service):
    """Test ensure_artifact_exists with custom name."""
    mock_service.get_artifact.side_effect = ArtifactNotFoundError(
        "test-artifact", "research"
    )

    result = sdk.ensure_artifact_exists(
        "test-artifact", AgentMode.RESEARCH, "Custom Name"
    )

    assert isinstance(result, ArtifactCreateResult)
    assert result.name == "Custom Name"


def test_ensure_artifact_exists_with_generated_name(sdk, mock_service):
    """Test ensure_artifact_exists with generated name."""
    mock_service.get_artifact.side_effect = ArtifactNotFoundError(
        "test-artifact", "research"
    )

    with patch("shotgun.sdk.artifacts.generate_artifact_name") as mock_generate:
        mock_generate.return_value = "Generated Name"

        result = sdk.ensure_artifact_exists("test-artifact", AgentMode.RESEARCH)

        assert isinstance(result, ArtifactCreateResult)
        assert result.name == "Generated Name"
        mock_generate.assert_called_once_with("test-artifact")


def test_ensure_section_exists_already_exists(sdk, mock_service):
    """Test ensure_section_exists when section already exists."""
    mock_service.get_section_content.return_value = "Existing content"

    result = sdk.ensure_section_exists(
        "test-artifact", AgentMode.RESEARCH, 1, "intro", "Introduction"
    )

    assert isinstance(result, SectionContentResult)
    assert result.content == "Existing content"


def test_ensure_section_exists_create_new(sdk, mock_service):
    """Test ensure_section_exists when section doesn't exist."""
    # get_section_content fails, but ensure_artifact_exists succeeds
    mock_service.get_section_content.side_effect = SectionNotFoundError(
        1, "test-artifact"
    )
    mock_service.get_artifact.side_effect = ArtifactNotFoundError(
        "test-artifact", "research"
    )

    result = sdk.ensure_section_exists(
        "test-artifact",
        AgentMode.RESEARCH,
        1,
        "intro",
        "Introduction",
        "Initial content",
    )

    assert isinstance(result, SectionCreateResult)
    assert result.section_number == 1
    assert result.section_title == "Introduction"


def test_ensure_section_exists_artifact_exists(sdk, mock_service, sample_artifact):
    """Test ensure_section_exists when artifact exists but section doesn't."""
    # get_section_content fails, but get_artifact succeeds
    mock_service.get_section_content.side_effect = SectionNotFoundError(
        1, "test-artifact"
    )
    mock_service.get_artifact.return_value = sample_artifact

    result = sdk.ensure_section_exists(
        "test-artifact", AgentMode.RESEARCH, 1, "intro", "Introduction"
    )

    assert isinstance(result, SectionCreateResult)
    assert result.section_number == 1
    assert result.section_title == "Introduction"
