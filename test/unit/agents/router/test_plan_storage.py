"""Tests for router agent plan storage."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from shotgun.agents.router.models import ExecutionPlan, ExecutionStep
from shotgun.agents.router.plan_storage import (
    PLAN_FILE_NAME,
    delete_plan,
    load_plan,
    save_plan,
)


@pytest.fixture
def temp_shotgun_dir(tmp_path):
    """Create a temporary .shotgun directory."""
    shotgun_dir = tmp_path / ".shotgun"
    shotgun_dir.mkdir()
    return shotgun_dir


@pytest.fixture
def mock_shotgun_path(temp_shotgun_dir):
    """Mock get_shotgun_base_path to return temp directory."""
    with patch(
        "shotgun.agents.router.plan_storage.get_shotgun_base_path",
        return_value=temp_shotgun_dir,
    ):
        yield temp_shotgun_dir


@pytest.fixture
def sample_plan():
    """Create a sample execution plan."""
    return ExecutionPlan(
        goal="Test the plan storage",
        steps=[
            ExecutionStep(
                id="step-1",
                title="First Step",
                objective="Do the first thing",
                success_criteria=["Criterion 1"],
                affects_files=["test.md"],
            ),
            ExecutionStep(
                id="step-2",
                title="Second Step",
                objective="Do the second thing",
                done=True,
            ),
        ],
        current_step_index=1,
    )


@pytest.mark.asyncio
async def test_save_and_load_plan_roundtrip(mock_shotgun_path, sample_plan):
    """Test saving and loading a plan preserves all data."""
    await save_plan(sample_plan)

    loaded = await load_plan()

    assert loaded is not None
    assert loaded.goal == sample_plan.goal
    assert len(loaded.steps) == len(sample_plan.steps)
    assert loaded.current_step_index == sample_plan.current_step_index

    # Check first step
    assert loaded.steps[0].id == "step-1"
    assert loaded.steps[0].title == "First Step"
    assert loaded.steps[0].objective == "Do the first thing"
    assert loaded.steps[0].success_criteria == ["Criterion 1"]
    assert loaded.steps[0].affects_files == ["test.md"]
    assert loaded.steps[0].done is False

    # Check second step
    assert loaded.steps[1].id == "step-2"
    assert loaded.steps[1].done is True


@pytest.mark.asyncio
async def test_load_plan_not_found(mock_shotgun_path):
    """Test loading when plan file doesn't exist."""
    result = await load_plan()
    assert result is None


@pytest.mark.asyncio
async def test_load_plan_invalid_json(mock_shotgun_path):
    """Test loading when plan file contains invalid JSON."""
    plan_file = mock_shotgun_path / PLAN_FILE_NAME
    plan_file.write_text("not valid json {{{")

    result = await load_plan()
    assert result is None


@pytest.mark.asyncio
async def test_load_plan_invalid_schema(mock_shotgun_path):
    """Test loading when plan file has wrong schema."""
    plan_file = mock_shotgun_path / PLAN_FILE_NAME
    plan_file.write_text('{"wrong": "schema"}')

    result = await load_plan()
    assert result is None


@pytest.mark.asyncio
async def test_save_plan_creates_directory(tmp_path):
    """Test that save_plan creates .shotgun directory if missing."""
    shotgun_dir = tmp_path / ".shotgun"
    # Don't create the directory

    with patch(
        "shotgun.agents.router.plan_storage.get_shotgun_base_path",
        return_value=shotgun_dir,
    ):
        plan = ExecutionPlan(
            goal="Test",
            steps=[ExecutionStep(id="1", title="Step", objective="Test")],
        )
        await save_plan(plan)

        # Directory should now exist
        assert shotgun_dir.exists()
        assert (shotgun_dir / PLAN_FILE_NAME).exists()


@pytest.mark.asyncio
async def test_save_plan_overwrites_existing(mock_shotgun_path, sample_plan):
    """Test that saving a plan overwrites existing plan."""
    # Save first plan
    await save_plan(sample_plan)

    # Save a different plan
    new_plan = ExecutionPlan(
        goal="New goal",
        steps=[ExecutionStep(id="new", title="New Step", objective="New")],
    )
    await save_plan(new_plan)

    # Load and verify it's the new plan
    loaded = await load_plan()
    assert loaded is not None
    assert loaded.goal == "New goal"
    assert len(loaded.steps) == 1
    assert loaded.steps[0].id == "new"


@pytest.mark.asyncio
async def test_delete_plan_existing(mock_shotgun_path, sample_plan):
    """Test deleting an existing plan."""
    await save_plan(sample_plan)

    # Verify file exists
    plan_file = mock_shotgun_path / PLAN_FILE_NAME
    assert plan_file.exists()

    # Delete
    result = await delete_plan()
    assert result is True
    assert not plan_file.exists()


@pytest.mark.asyncio
async def test_delete_plan_not_found(mock_shotgun_path):
    """Test deleting when no plan exists."""
    result = await delete_plan()
    assert result is False


@pytest.mark.asyncio
async def test_plan_file_is_valid_json(mock_shotgun_path, sample_plan):
    """Test that saved plan file is valid JSON."""
    await save_plan(sample_plan)

    plan_file = mock_shotgun_path / PLAN_FILE_NAME
    content = plan_file.read_text()

    # Should be valid JSON
    data = json.loads(content)
    assert "goal" in data
    assert "steps" in data


@pytest.mark.asyncio
async def test_plan_file_name_constant():
    """Test the plan file name constant."""
    assert PLAN_FILE_NAME == "execution_plan.json"
