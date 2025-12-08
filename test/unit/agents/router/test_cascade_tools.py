"""Tests for router agent cascade tools."""

from unittest.mock import MagicMock

import pytest

from shotgun.agents.router.tools.cascade_tools import (
    check_dependents,
    get_file_dependencies,
)


@pytest.fixture
def mock_run_context():
    """Create a mock RunContext."""
    ctx = MagicMock()
    ctx.deps = MagicMock()
    return ctx


@pytest.mark.asyncio
async def test_check_dependents_research(mock_run_context):
    """Test checking dependents for research.md."""
    result = await check_dependents(mock_run_context, "research.md")

    assert "specification.md" in result
    assert "plan.md" in result
    assert "tasks.md" in result
    assert "depend on" in result.lower()


@pytest.mark.asyncio
async def test_check_dependents_specification(mock_run_context):
    """Test checking dependents for specification.md."""
    result = await check_dependents(mock_run_context, "specification.md")

    assert "plan.md" in result
    assert "tasks.md" in result
    # research.md is upstream, not downstream
    assert "research.md" not in result


@pytest.mark.asyncio
async def test_check_dependents_plan(mock_run_context):
    """Test checking dependents for plan.md."""
    result = await check_dependents(mock_run_context, "plan.md")

    assert "tasks.md" in result


@pytest.mark.asyncio
async def test_check_dependents_tasks_leaf_node(mock_run_context):
    """Test checking dependents for tasks.md (leaf node)."""
    result = await check_dependents(mock_run_context, "tasks.md")

    assert "leaf node" in result.lower()
    assert "no files depend" in result.lower()


@pytest.mark.asyncio
async def test_check_dependents_unknown_file(mock_run_context):
    """Test checking dependents for unknown file."""
    result = await check_dependents(mock_run_context, "unknown.md")

    assert "leaf node" in result.lower() or "no files" in result.lower()


@pytest.mark.asyncio
async def test_check_dependents_with_path(mock_run_context):
    """Test checking dependents with full path."""
    result = await check_dependents(mock_run_context, ".shotgun/specification.md")

    # Should still find dependents based on filename
    assert "plan.md" in result
    assert "tasks.md" in result


@pytest.mark.asyncio
async def test_get_file_dependencies(mock_run_context):
    """Test getting full dependency map."""
    result = await get_file_dependencies(mock_run_context)

    # Should contain header/title
    assert "dependency" in result.lower()

    # Should show the dependency chain
    assert "research.md" in result
    assert "specification.md" in result
    assert "plan.md" in result
    assert "tasks.md" in result

    # Should indicate tasks.md is a leaf
    assert "leaf" in result.lower() or "no dependents" in result.lower()


@pytest.mark.asyncio
async def test_check_dependents_suggests_asking_user(mock_run_context):
    """Test that check_dependents suggests asking user."""
    result = await check_dependents(mock_run_context, "specification.md")

    # Should suggest asking user about updates
    assert "ask" in result.lower() or "user" in result.lower()
