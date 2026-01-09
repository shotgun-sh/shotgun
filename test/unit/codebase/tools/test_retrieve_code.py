"""Tests for retrieve_code tool."""

import importlib
from unittest.mock import AsyncMock, patch

import pytest

from shotgun.agents.tools.codebase import CodeSnippetResult
from shotgun.codebase.core.code_retrieval import CodeSnippet

# Import the actual module, not the function
retrieve_code_module = importlib.import_module(
    "shotgun.agents.tools.codebase.retrieve_code"
)


@pytest.mark.asyncio
async def test_retrieve_code_success(mock_run_context, mock_codebase_service):
    """Test successful code retrieval."""
    # Mock the code retrieval function
    with patch.object(
        retrieve_code_module, "retrieve_code_by_qualified_name", new_callable=AsyncMock
    ) as mock_retrieve:
        code_snippet = CodeSnippet(
            qualified_name="test.module.Class",
            source_code="class TestClass:\n    pass",
            file_path="test/module.py",
            line_start=1,
            line_end=2,
            found=True,
            docstring="Test class",
        )
        mock_retrieve.return_value = code_snippet

        # Execute
        result = await retrieve_code_module.retrieve_code(
            mock_run_context, "graph-id", "test.module.Class"
        )

        # Verify
        assert isinstance(result, CodeSnippetResult)
        assert result.found is True
        assert result.qualified_name == "test.module.Class"
        assert result.source_code == "class TestClass:\n    pass"
        assert "```python" in str(result)


@pytest.mark.asyncio
async def test_retrieve_code_not_found(mock_run_context, mock_codebase_service):
    """Test code retrieval when entity not found."""
    with patch.object(
        retrieve_code_module, "retrieve_code_by_qualified_name", new_callable=AsyncMock
    ) as mock_retrieve:
        code_snippet = CodeSnippet(
            qualified_name="test.module.Missing",
            source_code="",
            file_path="",
            line_start=0,
            line_end=0,
            found=False,
            error_message="Entity not found",
        )
        mock_retrieve.return_value = code_snippet

        result = await retrieve_code_module.retrieve_code(
            mock_run_context, "graph-id", "test.module.Missing"
        )

        assert isinstance(result, CodeSnippetResult)
        assert result.found is False
        assert "Not Found" in str(result)


@pytest.mark.asyncio
async def test_retrieve_code_while_indexing(mock_run_context, mock_codebase_service):
    """Test retrieve_code returns error when graph is being indexed."""
    # Mark graph as currently being indexed
    mock_codebase_service.indexing.is_active.return_value = True

    result = await retrieve_code_module.retrieve_code(
        mock_run_context, "graph-id", "test.module.Class"
    )

    assert isinstance(result, CodeSnippetResult)
    assert result.found is False
    assert result.error is not None
    assert "currently being indexed" in result.error
