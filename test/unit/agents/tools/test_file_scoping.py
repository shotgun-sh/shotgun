"""Test file scoping restrictions for agents."""

from unittest.mock import MagicMock

import pytest
from pydantic_ai import RunContext

from shotgun.agents.models import AgentDeps, AgentType, FileOperationTracker
from shotgun.agents.tools.file_management import (
    _normalize_shotgun_filename,
    read_file,
    write_file,
)


@pytest.fixture
def mock_deps():
    """Create mock dependencies for testing."""
    deps = MagicMock(spec=AgentDeps)
    deps.file_tracker = FileOperationTracker()
    return deps


@pytest.fixture
def mock_context(mock_deps):
    """Create mock run context for testing."""
    ctx = MagicMock(spec=RunContext)
    ctx.deps = mock_deps
    return ctx


@pytest.mark.asyncio
async def test_research_agent_can_write_to_research_files(
    mock_context, tmp_path, monkeypatch
):
    """Test that research agent can write to research.md and research/ folder."""
    # Setup
    mock_context.deps.agent_mode = AgentType.RESEARCH
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    # Research agent should be able to write to research.md
    result = await write_file(mock_context, "research.md", "Test content")
    assert "Successfully wrote" in result
    assert (tmp_path / "research.md").exists()

    # Research agent should be able to write to research/ folder
    result = await write_file(mock_context, "research/topic1.md", "Topic 1 research")
    assert "Successfully wrote" in result
    assert (tmp_path / "research" / "topic1.md").exists()

    # Research agent should be able to write any file type to research/ folder
    result = await write_file(mock_context, "research/data.json", '{"key": "value"}')
    assert "Successfully wrote" in result
    assert (tmp_path / "research" / "data.json").exists()

    # Research agent should NOT be able to write to other files
    result = await write_file(mock_context, "plan.md", "Test content")
    assert "Error" in result
    assert "Research agent can only write to" in result


@pytest.mark.asyncio
async def test_plan_agent_can_only_write_to_plan_md(
    mock_context, tmp_path, monkeypatch
):
    """Test that plan agent can only write to plan.md."""
    # Setup
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    # Plan agent should be able to write to plan.md
    result = await write_file(mock_context, "plan.md", "Test content")
    assert "Successfully wrote" in result
    assert (tmp_path / "plan.md").exists()

    # Plan agent should NOT be able to write to other files
    result = await write_file(mock_context, "research.md", "Test content")
    assert "Error" in result
    assert "Plan agent can only write to 'plan.md'" in result


@pytest.mark.asyncio
async def test_tasks_agent_can_only_write_to_tasks_md(
    mock_context, tmp_path, monkeypatch
):
    """Test that tasks agent can only write to tasks.md."""
    # Setup
    mock_context.deps.agent_mode = AgentType.TASKS
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    # Tasks agent should be able to write to tasks.md
    result = await write_file(mock_context, "tasks.md", "Test content")
    assert "Successfully wrote" in result
    assert (tmp_path / "tasks.md").exists()

    # Tasks agent should NOT be able to write to other files
    result = await write_file(mock_context, "specification.md", "Test content")
    assert "Error" in result
    assert "Tasks agent can only write to 'tasks.md'" in result


@pytest.mark.asyncio
async def test_specify_agent_can_write_to_specification_files(
    mock_context, tmp_path, monkeypatch
):
    """Test that specify agent can write to specification.md and contracts/ folder."""
    # Setup
    mock_context.deps.agent_mode = AgentType.SPECIFY
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    # Specify agent should be able to write to specification.md
    result = await write_file(mock_context, "specification.md", "Test content")
    assert "Successfully wrote" in result
    assert (tmp_path / "specification.md").exists()

    # Specify agent should be able to write to contracts/ folder
    result = await write_file(mock_context, "contracts/types.ts", "type User = {}")
    assert "Successfully wrote" in result
    assert (tmp_path / "contracts" / "types.ts").exists()

    # Specify agent should be able to write any file type to contracts/ folder
    result = await write_file(
        mock_context, "contracts/schema.json", '{"type": "object"}'
    )
    assert "Successfully wrote" in result
    assert (tmp_path / "contracts" / "schema.json").exists()

    # Specify agent should NOT be able to write to other files
    result = await write_file(mock_context, "tasks.md", "Test content")
    assert "Error" in result
    assert "Specify agent can only write to" in result


@pytest.mark.asyncio
async def test_export_agent_can_write_anywhere_except_protected(
    mock_context, tmp_path, monkeypatch
):
    """Test that export agent can write to any file except protected agent files."""
    # Setup
    mock_context.deps.agent_mode = AgentType.EXPORT
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    # Export agent should be able to write Agents.md at root
    result = await write_file(mock_context, "Agents.md", "Test content")
    assert "Successfully wrote" in result
    assert (tmp_path / "Agents.md").exists()

    # Export agent should be able to write to exports/ directory
    result = await write_file(mock_context, "exports/file1.md", "Test content")
    assert "Successfully wrote" in result
    assert (tmp_path / "exports" / "file1.md").exists()

    # Export agent should be able to write to subdirectories
    result = await write_file(mock_context, "docs/guide.md", "Test content")
    assert "Successfully wrote" in result
    assert (tmp_path / "docs" / "guide.md").exists()

    # Export agent should be able to write any filename
    result = await write_file(mock_context, "custom_export.json", "Test content")
    assert "Successfully wrote" in result
    assert (tmp_path / "custom_export.json").exists()

    # Export agent should NOT be able to write to protected files
    for protected_file in ["research.md", "specification.md", "plan.md", "tasks.md"]:
        result = await write_file(mock_context, protected_file, "Test content")
        assert "Error" in result
        assert "cannot write to protected file" in result
        assert protected_file in result


@pytest.mark.asyncio
async def test_no_agent_mode_allows_all_writes(mock_context, tmp_path, monkeypatch):
    """Test that when no agent_mode is set, writes are allowed anywhere in .shotgun."""
    # Setup
    mock_context.deps.agent_mode = None
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    # Should be able to write to any file in .shotgun
    result = await write_file(mock_context, "any_file.md", "Test content")
    assert "Successfully wrote" in result
    assert (tmp_path / "any_file.md").exists()

    # Should be able to create subdirectories
    result = await write_file(mock_context, "subdir/file.md", "Test content")
    assert "Successfully wrote" in result
    assert (tmp_path / "subdir" / "file.md").exists()


@pytest.mark.asyncio
async def test_read_file_not_restricted_by_agent_mode(
    mock_context, tmp_path, monkeypatch
):
    """Test that read_file is not restricted by agent_mode."""
    # Setup
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    # Create test files
    (tmp_path / "research.md").write_text("Research content")
    (tmp_path / "plan.md").write_text("Plan content")
    (tmp_path / "tasks.md").write_text("Tasks content")

    # Research agent should be able to read all files
    mock_context.deps.agent_mode = AgentType.RESEARCH
    content = await read_file(mock_context, "research.md", "test read")
    assert content == "Research content"

    content = await read_file(mock_context, "plan.md", "test read")
    assert content == "Plan content"

    content = await read_file(mock_context, "tasks.md", "test read")
    assert content == "Tasks content"


@pytest.mark.asyncio
async def test_write_file_normalizes_shotgun_prefix(
    mock_context, tmp_path, monkeypatch
):
    """Test that paths with .shotgun/ prefix are normalized correctly."""
    # Setup
    mock_context.deps.agent_mode = AgentType.RESEARCH
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    # Research agent should be able to write with .shotgun/ prefix
    result = await write_file(
        mock_context, ".shotgun/research/topic.md", "Topic content"
    )
    assert "Successfully wrote" in result
    assert (tmp_path / "research" / "topic.md").exists()

    # Should also work for root files with .shotgun/ prefix
    result = await write_file(mock_context, ".shotgun/research.md", "Research content")
    assert "Successfully wrote" in result
    assert (tmp_path / "research.md").exists()


@pytest.mark.asyncio
async def test_write_file_rejects_invalid_paths_with_shotgun_prefix(
    mock_context, tmp_path, monkeypatch
):
    """Test that invalid paths are still rejected even with .shotgun/ prefix."""
    # Setup
    mock_context.deps.agent_mode = AgentType.RESEARCH
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    # Research agent should NOT be able to write to plan.md even with .shotgun/ prefix
    result = await write_file(mock_context, ".shotgun/plan.md", "Test content")
    assert "Error" in result
    assert "Research agent can only write to" in result


@pytest.mark.asyncio
async def test_read_file_normalizes_shotgun_prefix(mock_context, tmp_path, monkeypatch):
    """Test that read_file normalizes .shotgun/ prefix correctly."""
    # Setup
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    # Create test file
    (tmp_path / "research.md").write_text("Research content")

    # Should be able to read with .shotgun/ prefix
    mock_context.deps.agent_mode = AgentType.RESEARCH
    content = await read_file(mock_context, ".shotgun/research.md", "test read")
    assert content == "Research content"


def test_normalize_shotgun_filename_strips_unix_prefix():
    """Test that _normalize_shotgun_filename strips Unix-style .shotgun/ prefix."""
    assert _normalize_shotgun_filename(".shotgun/research.md") == "research.md"
    assert (
        _normalize_shotgun_filename(".shotgun/research/topic.md") == "research/topic.md"
    )
    assert _normalize_shotgun_filename("research.md") == "research.md"


def test_normalize_shotgun_filename_strips_windows_prefix():
    """Test that _normalize_shotgun_filename strips Windows-style .shotgun\\ prefix."""
    assert _normalize_shotgun_filename(".shotgun\\research.md") == "research.md"
    assert (
        _normalize_shotgun_filename(".shotgun\\research\\topic.md")
        == "research\\topic.md"
    )


def test_normalize_shotgun_filename_preserves_paths_without_prefix():
    """Test that paths without .shotgun prefix are unchanged."""
    assert _normalize_shotgun_filename("research.md") == "research.md"
    assert _normalize_shotgun_filename("research/topic.md") == "research/topic.md"
    assert _normalize_shotgun_filename("contracts/api.ts") == "contracts/api.ts"


@pytest.mark.asyncio
async def test_write_file_normalizes_windows_style_prefix(
    mock_context, tmp_path, monkeypatch
):
    """Test that Windows-style .shotgun\\ prefix is normalized correctly."""
    # Setup
    mock_context.deps.agent_mode = AgentType.RESEARCH
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    # Research agent should be able to write with Windows-style .shotgun\\ prefix
    result = await write_file(mock_context, ".shotgun\\research.md", "Research content")
    assert "Successfully wrote" in result
    assert (tmp_path / "research.md").exists()
