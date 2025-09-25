"""Test file scoping restrictions for agents."""

from unittest.mock import MagicMock

import pytest
from pydantic_ai import RunContext

from shotgun.agents.models import AgentDeps, AgentType, FileOperationTracker
from shotgun.agents.tools.file_management import read_file, write_file


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
async def test_research_agent_can_only_write_to_research_md(mock_context, tmp_path, monkeypatch):
    """Test that research agent can only write to research.md."""
    # Setup
    mock_context.deps.agent_mode = AgentType.RESEARCH
    monkeypatch.setattr("shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path)

    # Research agent should be able to write to research.md
    result = await write_file(mock_context, "research.md", "Test content")
    assert "Successfully wrote" in result
    assert (tmp_path / "research.md").exists()

    # Research agent should NOT be able to write to other files
    result = await write_file(mock_context, "plan.md", "Test content")
    assert "Error" in result
    assert "Research agent can only write to 'research.md'" in result


@pytest.mark.asyncio
async def test_plan_agent_can_only_write_to_plan_md(mock_context, tmp_path, monkeypatch):
    """Test that plan agent can only write to plan.md."""
    # Setup
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr("shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path)

    # Plan agent should be able to write to plan.md
    result = await write_file(mock_context, "plan.md", "Test content")
    assert "Successfully wrote" in result
    assert (tmp_path / "plan.md").exists()

    # Plan agent should NOT be able to write to other files
    result = await write_file(mock_context, "research.md", "Test content")
    assert "Error" in result
    assert "Plan agent can only write to 'plan.md'" in result


@pytest.mark.asyncio
async def test_tasks_agent_can_only_write_to_tasks_md(mock_context, tmp_path, monkeypatch):
    """Test that tasks agent can only write to tasks.md."""
    # Setup
    mock_context.deps.agent_mode = AgentType.TASKS
    monkeypatch.setattr("shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path)

    # Tasks agent should be able to write to tasks.md
    result = await write_file(mock_context, "tasks.md", "Test content")
    assert "Successfully wrote" in result
    assert (tmp_path / "tasks.md").exists()

    # Tasks agent should NOT be able to write to other files
    result = await write_file(mock_context, "specification.md", "Test content")
    assert "Error" in result
    assert "Tasks agent can only write to 'tasks.md'" in result


@pytest.mark.asyncio
async def test_specify_agent_can_only_write_to_specification_md(mock_context, tmp_path, monkeypatch):
    """Test that specify agent can only write to specification.md."""
    # Setup
    mock_context.deps.agent_mode = AgentType.SPECIFY
    monkeypatch.setattr("shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path)

    # Specify agent should be able to write to specification.md
    result = await write_file(mock_context, "specification.md", "Test content")
    assert "Successfully wrote" in result
    assert (tmp_path / "specification.md").exists()

    # Specify agent should NOT be able to write to other files
    result = await write_file(mock_context, "tasks.md", "Test content")
    assert "Error" in result
    assert "Specify agent can only write to 'specification.md'" in result


@pytest.mark.asyncio
async def test_export_agent_can_write_to_exports_directory(mock_context, tmp_path, monkeypatch):
    """Test that export agent can write to any file in exports/ directory."""
    # Setup
    mock_context.deps.agent_mode = AgentType.EXPORT
    monkeypatch.setattr("shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path)

    # Export agent should be able to write to exports/
    result = await write_file(mock_context, "exports/file1.md", "Test content")
    assert "Successfully wrote" in result
    assert (tmp_path / "exports" / "file1.md").exists()

    # Export agent should be able to write to subdirectories in exports/
    result = await write_file(mock_context, "exports/subdir/file2.md", "Test content")
    assert "Successfully wrote" in result
    assert (tmp_path / "exports" / "subdir" / "file2.md").exists()

    # Export agent should auto-prefix filenames with exports/
    result = await write_file(mock_context, "file3.md", "Test content")
    assert "Successfully wrote" in result
    assert (tmp_path / "exports" / "file3.md").exists()

    # Export agent should NOT be able to write outside exports/
    result = await write_file(mock_context, "../research.md", "Test content")
    assert "Error" in result


@pytest.mark.asyncio
async def test_no_agent_mode_allows_all_writes(mock_context, tmp_path, monkeypatch):
    """Test that when no agent_mode is set, writes are allowed anywhere in .shotgun."""
    # Setup
    mock_context.deps.agent_mode = None
    monkeypatch.setattr("shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path)

    # Should be able to write to any file in .shotgun
    result = await write_file(mock_context, "any_file.md", "Test content")
    assert "Successfully wrote" in result
    assert (tmp_path / "any_file.md").exists()

    # Should be able to create subdirectories
    result = await write_file(mock_context, "subdir/file.md", "Test content")
    assert "Successfully wrote" in result
    assert (tmp_path / "subdir" / "file.md").exists()


@pytest.mark.asyncio
async def test_read_file_not_restricted_by_agent_mode(mock_context, tmp_path, monkeypatch):
    """Test that read_file is not restricted by agent_mode."""
    # Setup
    monkeypatch.setattr("shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path)

    # Create test files
    (tmp_path / "research.md").write_text("Research content")
    (tmp_path / "plan.md").write_text("Plan content")
    (tmp_path / "tasks.md").write_text("Tasks content")

    # Research agent should be able to read all files
    mock_context.deps.agent_mode = AgentType.RESEARCH
    content = await read_file(mock_context, "research.md")
    assert content == "Research content"

    content = await read_file(mock_context, "plan.md")
    assert content == "Plan content"

    content = await read_file(mock_context, "tasks.md")
    assert content == "Tasks content"
