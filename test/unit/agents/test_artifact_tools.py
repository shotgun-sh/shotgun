"""Test artifact management tools."""

from unittest.mock import MagicMock, patch

from shotgun.agents.tools.artifact_management import create_artifact


def test_create_artifact_success():
    """Test successful artifact creation."""
    with patch(
        "shotgun.agents.tools.artifact_management.get_artifact_service"
    ) as mock_get_service:
        mock_service = MagicMock()
        mock_artifact = MagicMock()
        mock_artifact.artifact_id = "test-artifact"
        mock_artifact.name = "Test Artifact"
        mock_service.create_artifact.return_value = mock_artifact
        mock_get_service.return_value = mock_service

        result = create_artifact("test-artifact", "research", "Test Artifact")

        assert "Created artifact" in result


def test_create_artifact_with_template():
    """Test artifact creation with template."""
    with patch(
        "shotgun.agents.tools.artifact_management.get_artifact_service"
    ) as mock_get_service:
        mock_service = MagicMock()
        mock_artifact = MagicMock()
        mock_artifact.artifact_id = "test-artifact"
        mock_artifact.name = "Test Artifact"
        mock_service.create_artifact.return_value = mock_artifact
        mock_get_service.return_value = mock_service

        result = create_artifact(
            "test-artifact", "research", "Test Artifact", "research-template"
        )

        assert "Created artifact" in result


def test_create_artifact_invalid_mode():
    """Test artifact creation with invalid mode."""
    result = create_artifact("test-artifact", "invalid", "Test Artifact")

    assert "Error: Validation error" in result
