"""Test artifact management tools."""

from unittest.mock import MagicMock

import pytest

from shotgun.agents.tools.artifact_management import create_artifact


@pytest.mark.asyncio
async def test_create_artifact_success():
    """Test successful artifact creation."""
    # Create mock context
    mock_context = MagicMock()
    mock_service = MagicMock()
    mock_artifact = MagicMock()
    mock_artifact.artifact_id = "test-artifact"
    mock_artifact.name = "Test Artifact"
    mock_artifact.has_template.return_value = False
    mock_service.create_artifact.return_value = mock_artifact
    mock_context.deps.artifact_service = mock_service

    result = await create_artifact(
        mock_context, "test-artifact", "research", "Test Artifact"
    )

    assert "Created artifact" in result


@pytest.mark.asyncio
async def test_create_artifact_with_template():
    """Test artifact creation with template."""
    # Create mock context
    mock_context = MagicMock()
    mock_service = MagicMock()
    mock_artifact = MagicMock()
    mock_artifact.artifact_id = "test-artifact"
    mock_artifact.name = "Test Artifact"
    mock_artifact.has_template.return_value = False
    mock_service.create_artifact.return_value = mock_artifact
    mock_context.deps.artifact_service = mock_service

    result = await create_artifact(
        mock_context, "test-artifact", "research", "Test Artifact", "research-template"
    )

    assert "Created artifact" in result


@pytest.mark.asyncio
async def test_create_artifact_invalid_mode():
    """Test artifact creation with invalid mode."""
    # Create mock context
    mock_context = MagicMock()
    mock_service = MagicMock()
    mock_context.deps.artifact_service = mock_service

    result = await create_artifact(
        mock_context, "test-artifact", "invalid", "Test Artifact"
    )

    assert "Error: Validation error" in result
