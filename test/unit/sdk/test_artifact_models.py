"""Unit tests for sdk.artifact_models module."""

import pytest

from shotgun.artifacts.models import AgentMode, Artifact, ArtifactSummary
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


@pytest.fixture
def sample_artifact_summary():
    """Create sample artifact summary."""
    from datetime import datetime

    return ArtifactSummary(
        artifact_id="artifact-123",
        agent_mode=AgentMode.RESEARCH,
        name="Test Artifact",
        section_count=3,
        created_at=datetime(2024, 1, 1, 10, 0, 0),
        updated_at=datetime(2024, 1, 1, 12, 0, 0),
        section_titles=["Section 1", "Section 2"],
        template_id=None,
    )


@pytest.fixture
def sample_artifact():
    """Create sample artifact."""
    return Artifact(
        artifact_id="artifact-123",
        agent_mode=AgentMode.RESEARCH,
        name="Test Artifact",
        sections=[],
    )


def test_artifact_list_result_empty():
    """Test ArtifactListResult with empty list."""
    result = ArtifactListResult(artifacts=[])

    assert result.artifacts == []
    assert result.agent_mode is None
    assert "No artifacts found" in str(result)


def test_artifact_list_result_with_mode():
    """Test ArtifactListResult with specific agent mode."""
    result = ArtifactListResult(artifacts=[], agent_mode=AgentMode.RESEARCH)

    assert result.agent_mode == AgentMode.RESEARCH
    assert "for research" in str(result)


def test_artifact_list_result_with_artifacts(sample_artifact_summary):
    """Test ArtifactListResult with artifacts."""
    result = ArtifactListResult(artifacts=[sample_artifact_summary])

    assert len(result.artifacts) == 1
    str_result = str(result)
    assert "Agent" in str_result
    assert "research" in str_result


def test_artifact_create_result():
    """Test ArtifactCreateResult."""
    result = ArtifactCreateResult(
        artifact_id="artifact-123", agent_mode=AgentMode.RESEARCH, name="Test Artifact"
    )

    assert result.artifact_id == "artifact-123"
    assert result.agent_mode == AgentMode.RESEARCH
    assert result.name == "Test Artifact"
    assert result.created is True
    assert "Created artifact" in str(result)
    assert "research mode" in str(result)


def test_artifact_delete_result_success():
    """Test ArtifactDeleteResult for successful deletion."""
    result = ArtifactDeleteResult(
        artifact_id="artifact-123", agent_mode=AgentMode.RESEARCH, deleted=True
    )

    assert result.deleted is True
    assert result.cancelled is False
    assert "Deleted artifact" in str(result)


def test_artifact_delete_result_cancelled():
    """Test ArtifactDeleteResult for cancelled deletion."""
    result = ArtifactDeleteResult(
        artifact_id="artifact-123",
        agent_mode=AgentMode.RESEARCH,
        cancelled=True,
        deleted=False,
    )

    assert result.cancelled is True
    assert "Deletion cancelled" in str(result)


def test_artifact_delete_result_failed():
    """Test ArtifactDeleteResult for failed deletion."""
    result = ArtifactDeleteResult(
        artifact_id="artifact-123", agent_mode=AgentMode.RESEARCH, deleted=False
    )

    assert result.deleted is False
    assert "Failed to delete" in str(result)


def test_artifact_info_result(sample_artifact):
    """Test ArtifactInfoResult."""
    result = ArtifactInfoResult(artifact=sample_artifact)

    assert result.artifact == sample_artifact
    str_result = str(result)
    assert "Artifact ID: artifact-123" in str_result
    assert "Name: Test Artifact" in str_result
    assert "Agent Mode: research" in str_result


def test_section_create_result():
    """Test SectionCreateResult."""
    result = SectionCreateResult(
        artifact_id="artifact-123",
        agent_mode=AgentMode.RESEARCH,
        section_number=1,
        section_title="Introduction",
    )

    assert result.section_number == 1
    assert result.section_title == "Introduction"
    assert result.created is True
    str_result = str(result)
    assert "Created section 1" in str_result
    assert "Introduction" in str_result


def test_section_update_result():
    """Test SectionUpdateResult."""
    result = SectionUpdateResult(
        artifact_id="artifact-123",
        agent_mode=AgentMode.RESEARCH,
        section_number=2,
        updated_fields=["title", "content"],
    )

    assert result.section_number == 2
    assert result.updated_fields == ["title", "content"]
    str_result = str(result)
    assert "Updated section 2" in str_result
    assert "title, content" in str_result


def test_section_delete_result_success():
    """Test SectionDeleteResult for successful deletion."""
    result = SectionDeleteResult(
        artifact_id="artifact-123",
        agent_mode=AgentMode.RESEARCH,
        section_number=3,
        deleted=True,
    )

    assert result.deleted is True
    assert "Deleted section 3" in str(result)


def test_section_delete_result_failed():
    """Test SectionDeleteResult for failed deletion."""
    result = SectionDeleteResult(
        artifact_id="artifact-123",
        agent_mode=AgentMode.RESEARCH,
        section_number=3,
        deleted=False,
    )

    assert result.deleted is False
    assert "Failed to delete section 3" in str(result)


def test_section_content_result():
    """Test SectionContentResult."""
    content = "This is the section content."
    result = SectionContentResult(
        artifact_id="artifact-123",
        agent_mode=AgentMode.RESEARCH,
        section_number=1,
        content=content,
    )

    assert result.content == content
    assert str(result) == content


def test_artifact_error_result_minimal():
    """Test ArtifactErrorResult with minimal information."""
    result = ArtifactErrorResult(error_message="Something went wrong")

    assert result.error_message == "Something went wrong"
    assert "Error: Something went wrong" in str(result)


def test_artifact_error_result_full():
    """Test ArtifactErrorResult with all information."""
    result = ArtifactErrorResult(
        error_message="Section not found",
        artifact_id="artifact-123",
        agent_mode=AgentMode.RESEARCH,
        section_number=5,
        details="Section 5 does not exist in this artifact",
    )

    str_result = str(result)
    assert "Error: Section not found" in str_result
    assert "Artifact: artifact-123" in str_result
    assert "Mode: research" in str_result
    assert "Section: 5" in str_result
    assert "Details: Section 5 does not exist" in str_result


def test_model_initialization():
    """Test that all models can be initialized properly."""
    # Test basic initialization
    list_result = ArtifactListResult(artifacts=[])
    assert isinstance(list_result, ArtifactListResult)

    create_result = ArtifactCreateResult(
        artifact_id="test", agent_mode=AgentMode.PLAN, name="Test"
    )
    assert isinstance(create_result, ArtifactCreateResult)

    error_result = ArtifactErrorResult(error_message="Test error")
    assert isinstance(error_result, ArtifactErrorResult)
