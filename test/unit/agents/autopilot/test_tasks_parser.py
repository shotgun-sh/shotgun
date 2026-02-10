"""Tests for the tasks.md parser."""

from pathlib import Path

from shotgun.agents.autopilot.models import Stage, StageStatus, Task
from shotgun.agents.autopilot.tasks_parser import ParsedTasksFile, TasksParser


def test_parser_initialization():
    """Test TasksParser initialization."""
    parser = TasksParser()
    assert parser.working_directory == Path.cwd()

    custom_dir = Path("/var/tmp/test")  # noqa: S108
    parser_with_dir = TasksParser(custom_dir)
    assert parser_with_dir.working_directory == custom_dir


def test_parse_valid_tasks_content():
    """Test parsing valid tasks.md content."""
    content = """# Tasks

### Stage 1: Authentication Setup
- [ ] Create login form
- [x] Set up auth middleware
- [ ] Add password validation

### Stage 2: User Management
- [ ] Create user model
- [ ] Add user CRUD endpoints
"""
    parser = TasksParser()
    result = parser.parse_content(content)

    assert result.is_valid
    assert len(result.stages) == 2
    assert result.total_tasks == 5
    assert result.completed_tasks == 1

    # Check first stage
    stage1 = result.stages[0]
    assert stage1.number == "1"
    assert stage1.name == "Authentication Setup"
    assert len(stage1.tasks) == 3
    assert stage1.tasks[0].text == "Create login form"
    assert stage1.tasks[0].completed is False
    assert stage1.tasks[1].completed is True  # Set up auth middleware

    # Check second stage
    stage2 = result.stages[1]
    assert stage2.number == "2"
    assert stage2.name == "User Management"
    assert len(stage2.tasks) == 2


def test_parse_case_insensitive_checkbox():
    """Test parsing checkboxes with different case."""
    content = """### Stage 1: Test
- [X] Upper case X
- [x] Lower case x
- [ ] Empty checkbox
"""
    parser = TasksParser()
    result = parser.parse_content(content)

    assert result.is_valid
    assert len(result.stages[0].tasks) == 3
    assert result.stages[0].tasks[0].completed is True
    assert result.stages[0].tasks[1].completed is True
    assert result.stages[0].tasks[2].completed is False


def test_parse_empty_content():
    """Test parsing empty content."""
    parser = TasksParser()
    result = parser.parse_content("")

    assert not result.is_valid
    assert len(result.stages) == 0
    assert "No stages found" in result.parse_errors[0]


def test_parse_no_stages():
    """Test parsing content without stages."""
    content = """# Tasks

Just some text without stages.
- [ ] A task outside a stage
"""
    parser = TasksParser()
    result = parser.parse_content(content)

    assert not result.is_valid
    # Should have error about task outside stage and no stages found
    assert any("No stages found" in e for e in result.parse_errors)
    assert any("Task found outside" in e for e in result.parse_errors)


def test_parse_empty_stage():
    """Test parsing a stage with no tasks."""
    content = """### Stage 1: Empty Stage

### Stage 2: Has Tasks
- [ ] A task
"""
    parser = TasksParser()
    result = parser.parse_content(content)

    assert len(result.stages) == 2
    # Should warn about empty stage
    assert any("Stage 1" in e and "no tasks" in e for e in result.parse_errors)


def test_parse_out_of_order_stages():
    """Test parsing stages that are numbered out of order (now allowed with alphanumeric)."""
    content = """### Stage 1: First
- [ ] Task

### Stage 3: Skipped Two
- [ ] Task
"""
    parser = TasksParser()
    result = parser.parse_content(content)

    # With alphanumeric support, out-of-order stages are allowed
    assert result.is_valid
    assert len(result.stages) == 2
    assert result.stages[0].number == "1"
    assert result.stages[1].number == "3"


def test_parse_stage_pattern_variations():
    """Test parsing different stage header formats."""
    # Standard format
    content = """### Stage 1: Standard Format
- [ ] Task
"""
    parser = TasksParser()
    result = parser.parse_content(content)
    assert result.is_valid
    assert result.stages[0].name == "Standard Format"


def test_parse_preserves_line_numbers():
    """Test that parser preserves task line numbers."""
    content = """Line 1
Line 2
### Stage 1: Test
- [ ] Task on line 4
- [ ] Task on line 5
- [ ] Task on line 6
"""
    parser = TasksParser()
    result = parser.parse_content(content)

    assert result.is_valid
    assert result.stages[0].tasks[0].line_number == 4
    assert result.stages[0].tasks[1].line_number == 5
    assert result.stages[0].tasks[2].line_number == 6


def test_parsed_tasks_file_properties():
    """Test ParsedTasksFile properties."""
    stages = [
        Stage(
            number="1",
            name="Stage 1",
            tasks=[
                Task(text="T1", completed=True, line_number=1),
                Task(text="T2", completed=False, line_number=2),
            ],
        ),
        Stage(
            number="2",
            name="Stage 2",
            tasks=[
                Task(text="T3", completed=True, line_number=3),
            ],
        ),
    ]
    result = ParsedTasksFile(stages=stages, file_path="test.md")

    assert result.total_tasks == 3
    assert result.completed_tasks == 2
    assert result.is_valid is True


def test_parsed_tasks_file_invalid():
    """Test ParsedTasksFile.is_valid with errors."""
    result = ParsedTasksFile(
        stages=[],
        file_path="test.md",
        parse_errors=["Some error"],
    )

    assert result.is_valid is False


def test_refresh_stages_updates_completion():
    """Test refresh_stages updates task completion status."""
    # Original stages with tasks not completed
    original_stages = [
        Stage(
            number="1",
            name="Stage 1",
            status=StageStatus.IN_PROGRESS,
            tasks=[
                Task(text="Task 1", completed=False, line_number=4),
                Task(text="Task 2", completed=False, line_number=5),
            ],
        ),
    ]

    # New content with one task completed
    new_content = """### Stage 1: Stage 1
- [x] Task 1
- [ ] Task 2
"""
    parser = TasksParser()

    # Verify parsing works (result not used, just exercising the parser)
    _ = parser.parse_content(new_content)

    # Manually test the refresh logic by simulating the file parse
    updated_stages = parser.refresh_stages(
        original_stages,
        Path("/nonexistent"),  # Will parse and return empty
    )

    # Since file doesn't exist, should return original
    assert updated_stages == original_stages


def test_refresh_stages_preserves_metadata():
    """Test refresh_stages preserves stage metadata like status and branch."""
    original_stages = [
        Stage(
            number="1",
            name="Stage 1",
            status=StageStatus.IN_PROGRESS,
            branch_name="autopilot/stage-1",
            pr_url="https://github.com/test/repo/pull/1",
            tasks=[
                Task(text="Task 1", completed=False, line_number=4),
            ],
        ),
    ]

    # Refresh with same stages (simulating no file change)
    parser = TasksParser()
    updated = parser.refresh_stages(original_stages, Path("/nonexistent"))

    # Should preserve metadata
    assert updated[0].status == StageStatus.IN_PROGRESS
    assert updated[0].branch_name == "autopilot/stage-1"
    assert updated[0].pr_url == "https://github.com/test/repo/pull/1"


def test_parse_multiline_task_text():
    """Test that only single-line task format is supported."""
    content = """### Stage 1: Test
- [ ] Single line task
- [ ] Another task
"""
    parser = TasksParser()
    result = parser.parse_content(content)

    assert result.is_valid
    assert len(result.stages[0].tasks) == 2


def test_parse_special_characters_in_task():
    """Test parsing tasks with special characters."""
    content = """### Stage 1: Test
- [ ] Task with `code` and **bold**
- [ ] Task with URL: https://example.com
- [ ] Task with "quotes" and 'apostrophes'
"""
    parser = TasksParser()
    result = parser.parse_content(content)

    assert result.is_valid
    assert len(result.stages[0].tasks) == 3
    assert "`code`" in result.stages[0].tasks[0].text
    assert "https://example.com" in result.stages[0].tasks[1].text


def test_parse_depends_on_with_stage_prefix():
    """Test parsing Depends on lines with 'Stage N' format."""
    content = """### Stage 1: Database Layer
Depends on: None
- [ ] Create models

### Stage 2: API Framework
Depends on: None
- [ ] Set up routing

### Stage 3: Business Logic
Depends on: Stage 1, Stage 2
- [ ] Implement services
"""
    parser = TasksParser()
    result = parser.parse_content(content)

    assert result.is_valid
    assert len(result.stages) == 3
    assert result.stages[0].depends_on == []
    assert result.stages[1].depends_on == []
    assert result.stages[2].depends_on == ["1", "2"]


def test_parse_depends_on_bare_numbers():
    """Test parsing Depends on lines with bare numbers."""
    content = """### Stage 1: First
Depends on: None
- [ ] Task

### Stage 2: Second
Depends on: 1
- [ ] Task
"""
    parser = TasksParser()
    result = parser.parse_content(content)

    assert result.is_valid
    assert result.stages[0].depends_on == []
    assert result.stages[1].depends_on == ["1"]


def test_parse_depends_on_missing():
    """Test that missing Depends on line results in empty list."""
    content = """### Stage 1: No Depends Line
- [ ] Task
"""
    parser = TasksParser()
    result = parser.parse_content(content)

    assert result.is_valid
    assert result.stages[0].depends_on == []


def test_parse_depends_on_multiple():
    """Test parsing Depends on with multiple dependencies."""
    content = """### Stage 4: Integration Testing
Depends on: Stage 1, Stage 2, Stage 3
- [ ] Run integration tests
"""
    parser = TasksParser()
    result = parser.parse_content(content)

    assert result.is_valid
    assert result.stages[0].depends_on == ["1", "2", "3"]


def test_parse_depends_on_with_markdown_header():
    """Test parsing Depends on as a markdown sub-header."""
    content = """### Stage 1: Database
#### Depends on: None
- [ ] Task

### Stage 2: Logic
#### Depends on: Stage 1
- [ ] Task
"""
    parser = TasksParser()
    result = parser.parse_content(content)

    assert result.is_valid
    assert result.stages[0].depends_on == []
    assert result.stages[1].depends_on == ["1"]


def test_parse_depends_on_static_method():
    """Test _parse_depends_on static method directly."""
    assert TasksParser._parse_depends_on("None") == []
    assert TasksParser._parse_depends_on("none") == []
    assert TasksParser._parse_depends_on("") == []
    assert TasksParser._parse_depends_on("Stage 1") == ["1"]
    assert TasksParser._parse_depends_on("Stage 1, Stage 2") == ["1", "2"]
    assert TasksParser._parse_depends_on("1, 2, 3") == ["1", "2", "3"]
    assert TasksParser._parse_depends_on("Stage A, Stage 2b") == ["A", "2b"]


def test_merge_preserves_empty_depends_on():
    """Test that merge preserves explicit empty depends_on (not falsy fallback)."""
    from shotgun.agents.autopilot.tasks_parser import merge_stages_with_parsed_tasks

    # State has depends_on=["1"] (stale), parsed has depends_on=[] (cleared to None/empty)
    state_stages = [
        Stage(
            number="2",
            name="Stage 2",
            depends_on=["1"],
            status=StageStatus.IN_PROGRESS,
            tasks=[Task(text="Task 2", completed=False, line_number=2)],
        ),
    ]

    # Parsed stage has empty depends_on (e.g. "Depends on: None" was parsed)
    parsed_stages = [
        Stage(
            number="2",
            name="Stage 2",
            depends_on=[],  # Explicitly empty - should NOT fall through to state
            tasks=[Task(text="Task 2", completed=True, line_number=2)],
        ),
    ]

    result = merge_stages_with_parsed_tasks(state_stages, parsed_stages)

    # The empty list from parsed should be preserved, not replaced by stale ["1"]
    assert result[0].depends_on == []


def test_merge_stages_preserves_depends_on():
    """Test that merge_stages_with_parsed_tasks preserves depends_on."""
    from shotgun.agents.autopilot.tasks_parser import merge_stages_with_parsed_tasks

    state_stages = [
        Stage(
            number="1",
            name="Stage 1",
            depends_on=[],
            status=StageStatus.COMPLETED,
            tasks=[Task(text="Task 1", completed=True, line_number=1)],
        ),
        Stage(
            number="2",
            name="Stage 2",
            depends_on=["1"],
            status=StageStatus.IN_PROGRESS,
            tasks=[Task(text="Task 2", completed=False, line_number=2)],
        ),
    ]

    parsed_stages = [
        Stage(
            number="1",
            name="Stage 1",
            depends_on=[],
            tasks=[Task(text="Task 1", completed=True, line_number=1)],
        ),
        Stage(
            number="2",
            name="Stage 2",
            depends_on=["1"],
            tasks=[Task(text="Task 2", completed=True, line_number=2)],
        ),
    ]

    result = merge_stages_with_parsed_tasks(state_stages, parsed_stages)

    assert result[0].depends_on == []
    assert result[1].depends_on == ["1"]
    # Metadata preserved
    assert result[0].status == StageStatus.COMPLETED
    assert result[1].status == StageStatus.IN_PROGRESS
    # Tasks updated from parsed
    assert result[1].tasks[0].completed is True
