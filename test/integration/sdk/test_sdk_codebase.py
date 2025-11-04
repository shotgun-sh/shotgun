"""Integration tests for CodebaseSDK.

These tests create actual graphs and test the complete SDK workflow.
"""

import asyncio
from pathlib import Path

import pytest

from shotgun.codebase.models import QueryType
from shotgun.sdk import CodebaseSDK
from shotgun.sdk.exceptions import CodebaseNotFoundError, InvalidPathError


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sdk_initialization(temp_storage_dir):
    """Test SDK initializes with custom storage directory."""
    storage_path = temp_storage_dir / "sdk_storage"
    sdk = CodebaseSDK(storage_path)

    assert sdk.service is not None
    assert sdk.service.storage_dir == storage_path
    assert storage_path.exists()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_codebases_empty(temp_storage_dir):
    """Test listing codebases when none exist."""
    sdk = CodebaseSDK(temp_storage_dir / "empty")
    result = await sdk.list_codebases()

    assert result.graphs == []
    assert str(result) == "No codebases found."


@pytest.mark.integration
@pytest.mark.asyncio
async def test_index_codebase_success(temp_storage_dir, simple_python_codebase):
    """Test successfully indexing a codebase."""
    sdk = CodebaseSDK(temp_storage_dir / "index_test")

    result = await sdk.index_codebase(simple_python_codebase, "Test Codebase")

    assert result.graph_id is not None
    assert result.name == "Test Codebase"
    assert result.repo_path == str(simple_python_codebase.resolve())
    assert result.file_count > 0
    assert result.node_count > 0
    assert result.relationship_count > 0

    # Verify it appears in list
    list_result = await sdk.list_codebases()
    assert len(list_result.graphs) == 1
    assert list_result.graphs[0].graph_id == result.graph_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_index_codebase_invalid_path(temp_storage_dir):
    """Test indexing with invalid path raises error."""
    sdk = CodebaseSDK(temp_storage_dir / "invalid_test")
    invalid_path = Path("/nonexistent/path")

    with pytest.raises(InvalidPathError) as exc_info:
        await sdk.index_codebase(invalid_path, "Invalid")

    assert "Path does not exist" in str(exc_info.value)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_info_success(temp_storage_dir, calculator_codebase):
    """Test getting codebase info."""
    sdk = CodebaseSDK(temp_storage_dir / "info_test")

    # Index first
    index_result = await sdk.index_codebase(calculator_codebase, "Calculator")

    # Get info
    info_result = await sdk.get_info(index_result.graph_id)

    assert info_result.graph.graph_id == index_result.graph_id
    assert info_result.graph.name == "Calculator"
    assert info_result.graph.node_count > 0
    assert info_result.graph.relationship_count > 0

    # Test string representation is not empty
    info_str = str(info_result)
    assert len(info_str) > 0
    assert "Calculator" in info_str
    assert "Graph ID:" in info_str


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_info_not_found(temp_storage_dir):
    """Test getting info for nonexistent graph."""
    sdk = CodebaseSDK(temp_storage_dir / "info_not_found_test")

    with pytest.raises(CodebaseNotFoundError) as exc_info:
        await sdk.get_info("nonexistent_id")

    assert "Graph not found" in str(exc_info.value)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_codebase_no_confirmation(
    temp_storage_dir, simple_python_codebase
):
    """Test deleting codebase without confirmation callback."""
    sdk = CodebaseSDK(temp_storage_dir / "delete_test")

    # Index first
    index_result = await sdk.index_codebase(simple_python_codebase, "To Delete")

    # Delete without confirmation
    delete_result = await sdk.delete_codebase(index_result.graph_id)

    assert delete_result.graph_id == index_result.graph_id
    assert delete_result.name == "To Delete"
    assert delete_result.deleted is True
    assert delete_result.cancelled is False

    # Verify it's gone
    list_result = await sdk.list_codebases()
    assert len(list_result.graphs) == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_codebase_with_sync_confirmation_accept(
    temp_storage_dir, simple_python_codebase
):
    """Test deleting codebase with sync confirmation callback that accepts."""
    sdk = CodebaseSDK(temp_storage_dir / "delete_sync_accept")

    # Index first
    index_result = await sdk.index_codebase(simple_python_codebase, "Delete Accept")

    # Delete with confirmation that accepts
    def confirm_delete(_graph):
        return True

    delete_result = await sdk.delete_codebase(index_result.graph_id, confirm_delete)

    assert delete_result.deleted is True
    assert delete_result.cancelled is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_codebase_with_sync_confirmation_reject(
    temp_storage_dir, simple_python_codebase
):
    """Test deleting codebase with sync confirmation callback that rejects."""
    sdk = CodebaseSDK(temp_storage_dir / "delete_sync_reject")

    # Index first
    index_result = await sdk.index_codebase(simple_python_codebase, "Delete Reject")

    # Delete with confirmation that rejects
    def confirm_delete(_graph):
        return False

    delete_result = await sdk.delete_codebase(index_result.graph_id, confirm_delete)

    assert delete_result.deleted is False
    assert delete_result.cancelled is True

    # Verify it's still there
    list_result = await sdk.list_codebases()
    assert len(list_result.graphs) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_codebase_with_async_confirmation_accept(
    temp_storage_dir, simple_python_codebase
):
    """Test deleting codebase with async confirmation callback that accepts."""
    sdk = CodebaseSDK(temp_storage_dir / "delete_async_accept")

    # Index first
    index_result = await sdk.index_codebase(
        simple_python_codebase, "Delete Async Accept"
    )

    # Delete with async confirmation that accepts
    async def confirm_delete(_graph):
        await asyncio.sleep(0.01)  # Simulate async work
        return True

    delete_result = await sdk.delete_codebase(index_result.graph_id, confirm_delete)

    assert delete_result.deleted is True
    assert delete_result.cancelled is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_codebase_not_found(temp_storage_dir):
    """Test deleting nonexistent codebase."""
    sdk = CodebaseSDK(temp_storage_dir / "delete_not_found")

    with pytest.raises(CodebaseNotFoundError) as exc_info:
        await sdk.delete_codebase("nonexistent_id")

    assert "Graph not found" in str(exc_info.value)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_query_codebase_cypher(temp_storage_dir, calculator_codebase):
    """Test querying codebase with Cypher."""
    sdk = CodebaseSDK(temp_storage_dir / "query_cypher_test")

    # Index first
    index_result = await sdk.index_codebase(calculator_codebase, "Query Test")

    # Query with Cypher
    cypher_query = "MATCH (c:Class) RETURN c.name AS name ORDER BY c.name"
    result = await sdk.query_codebase(
        index_result.graph_id, cypher_query, QueryType.CYPHER
    )

    assert result.graph_name == "Query Test"
    assert result.query_type == "Cypher"
    assert result.result.success is True
    assert result.result.row_count > 0

    # Test string representation is not empty
    result_str = str(result)
    assert len(result_str) > 0
    assert "Calculator" in result_str or "Query executed" in result_str


@pytest.mark.integration
@pytest.mark.asyncio
async def test_query_codebase_not_found(temp_storage_dir):
    """Test querying nonexistent codebase."""
    sdk = CodebaseSDK(temp_storage_dir / "query_not_found")

    with pytest.raises(CodebaseNotFoundError) as exc_info:
        await sdk.query_codebase("nonexistent_id", "test query", QueryType.CYPHER)

    assert "Graph not found" in str(exc_info.value)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reindex_codebase_success(temp_storage_dir, simple_python_codebase):
    """Test reindexing a codebase."""
    sdk = CodebaseSDK(temp_storage_dir / "reindex_test")

    # Index first
    index_result = await sdk.index_codebase(simple_python_codebase, "Reindex Test")

    # Reindex
    reindex_result = await sdk.reindex_codebase(index_result.graph_id)

    assert reindex_result.graph_id == index_result.graph_id
    assert reindex_result.name == "Reindex Test"
    assert reindex_result.stats is not None

    # Test string representation
    result_str = str(reindex_result)
    assert "Reindexing completed!" in result_str


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reindex_codebase_not_found(temp_storage_dir):
    """Test reindexing nonexistent codebase."""
    sdk = CodebaseSDK(temp_storage_dir / "reindex_not_found")

    with pytest.raises(CodebaseNotFoundError) as exc_info:
        await sdk.reindex_codebase("nonexistent_id")

    assert "Graph not found" in str(exc_info.value)
