"""Integration tests for SDK service factory functions."""

import pytest

from shotgun.sdk.services import get_codebase_service


@pytest.mark.integration
def test_get_codebase_service_default_storage(isolated_shotgun_home):
    """Test get_codebase_service with default storage directory."""
    service = get_codebase_service()

    assert service is not None
    # Should use the test home directory
    assert service.storage_dir.parent == isolated_shotgun_home
    assert service.storage_dir.name == "codebases"
    assert service.storage_dir.exists()  # Directory should be created


@pytest.mark.integration
def test_get_codebase_service_custom_storage(temp_storage_dir):
    """Test get_codebase_service with custom storage directory."""
    custom_dir = temp_storage_dir / "custom_storage"
    service = get_codebase_service(custom_dir)

    assert service is not None
    assert service.storage_dir == custom_dir
    assert custom_dir.exists()


@pytest.mark.integration
def test_get_codebase_service_string_path(temp_storage_dir):
    """Test get_codebase_service with string path."""
    custom_dir = temp_storage_dir / "string_storage"
    service = get_codebase_service(str(custom_dir))

    assert service is not None
    assert service.storage_dir == custom_dir
    assert custom_dir.exists()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_service_functionality(temp_storage_dir):
    """Test that returned service is functional."""
    custom_dir = temp_storage_dir / "functional_test"
    service = get_codebase_service(custom_dir)

    # Should be able to list graphs (empty initially)
    graphs = await service.list_graphs()
    assert graphs == []
