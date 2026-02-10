"""Tests for autopilot models."""

from shotgun.agents.autopilot.models import (
    AutopilotMode,
    AutopilotState,
    ClaudeOutput,
    ClaudeOutputType,
    Stage,
    StageStatus,
    Task,
)


def test_autopilot_mode_enum():
    """Test AutopilotMode enum values."""
    assert AutopilotMode.PAUSE_BETWEEN == "pause_between"
    assert AutopilotMode.AUTO_CONTINUE == "auto_continue"


def test_stage_status_enum():
    """Test StageStatus enum values."""
    assert StageStatus.PENDING == "pending"
    assert StageStatus.IN_PROGRESS == "in_progress"
    assert StageStatus.COMPLETED == "completed"
    assert StageStatus.FAILED == "failed"
    assert StageStatus.SKIPPED == "skipped"


def test_claude_output_type_enum():
    """Test ClaudeOutputType enum values."""
    assert ClaudeOutputType.STDOUT == "stdout"
    assert ClaudeOutputType.STDERR == "stderr"
    assert ClaudeOutputType.EXIT == "exit"
    assert ClaudeOutputType.ERROR == "error"


def test_task_creation():
    """Test Task model creation."""
    task = Task(text="Implement feature", completed=False, line_number=10)

    assert task.text == "Implement feature"
    assert task.completed is False
    assert task.line_number == 10


def test_task_completed():
    """Test Task completed state."""
    task = Task(text="Complete task", completed=True, line_number=5)

    assert task.completed is True


def test_stage_creation():
    """Test Stage model creation with tasks."""
    tasks = [
        Task(text="Task 1", completed=False, line_number=10),
        Task(text="Task 2", completed=True, line_number=11),
        Task(text="Task 3", completed=False, line_number=12),
    ]
    stage = Stage(number="1", name="Authentication Setup", tasks=tasks)

    assert stage.number == "1"
    assert stage.name == "Authentication Setup"
    assert len(stage.tasks) == 3
    assert stage.status == StageStatus.PENDING


def test_stage_pending_tasks():
    """Test Stage.pending_tasks property."""
    tasks = [
        Task(text="Task 1", completed=False, line_number=10),
        Task(text="Task 2", completed=True, line_number=11),
        Task(text="Task 3", completed=False, line_number=12),
    ]
    stage = Stage(number="1", name="Test Stage", tasks=tasks)

    pending = stage.pending_tasks
    assert len(pending) == 2
    assert pending[0].text == "Task 1"
    assert pending[1].text == "Task 3"


def test_stage_completed_tasks():
    """Test Stage.completed_tasks property."""
    tasks = [
        Task(text="Task 1", completed=False, line_number=10),
        Task(text="Task 2", completed=True, line_number=11),
        Task(text="Task 3", completed=True, line_number=12),
    ]
    stage = Stage(number="1", name="Test Stage", tasks=tasks)

    completed = stage.completed_tasks
    assert len(completed) == 2
    assert completed[0].text == "Task 2"
    assert completed[1].text == "Task 3"


def test_stage_is_complete():
    """Test Stage.is_complete property."""
    # Not complete
    tasks = [
        Task(text="Task 1", completed=True, line_number=10),
        Task(text="Task 2", completed=False, line_number=11),
    ]
    stage = Stage(number="1", name="Test Stage", tasks=tasks)
    assert stage.is_complete is False

    # Complete
    tasks_complete = [
        Task(text="Task 1", completed=True, line_number=10),
        Task(text="Task 2", completed=True, line_number=11),
    ]
    stage_complete = Stage(number="1", name="Test Stage", tasks=tasks_complete)
    assert stage_complete.is_complete is True


def test_stage_task_count():
    """Test Stage.task_count property."""
    tasks = [
        Task(text="Task 1", completed=False, line_number=10),
        Task(text="Task 2", completed=True, line_number=11),
        Task(text="Task 3", completed=False, line_number=12),
    ]
    stage = Stage(number="1", name="Test Stage", tasks=tasks)

    assert stage.task_count == 3
    assert stage.completed_count == 1


def test_stage_task_count_override():
    """Test Stage.task_count and completed_count with override fields."""
    # Test with empty tasks but override counts (lightweight parser use case)
    stage = Stage(
        number="1",
        name="Test Stage",
        tasks=[],  # No tasks loaded
        task_count_override=10,
        completed_count_override=7,
    )

    assert stage.task_count == 10  # Uses override
    assert stage.completed_count == 7  # Uses override

    # Test that normal computation still works when override not set
    tasks = [
        Task(text="Task 1", completed=False, line_number=10),
        Task(text="Task 2", completed=True, line_number=11),
        Task(text="Task 3", completed=True, line_number=12),
    ]
    stage_normal = Stage(number="2", name="Normal Stage", tasks=tasks)

    assert stage_normal.task_count == 3  # Computed from tasks
    assert stage_normal.completed_count == 2  # Computed from tasks


def test_stage_format_task_list():
    """Test Stage.format_task_list method."""
    tasks = [
        Task(text="Incomplete task", completed=False, line_number=10),
        Task(text="Complete task", completed=True, line_number=11),
    ]
    stage = Stage(number="1", name="Test Stage", tasks=tasks)

    formatted = stage.format_task_list()
    assert "- [ ] Incomplete task" in formatted
    assert "- [x] Complete task" in formatted


def test_autopilot_state_creation():
    """Test AutopilotState model creation."""
    state = AutopilotState(
        mode=AutopilotMode.PAUSE_BETWEEN,
        base_branch="main",
    )

    assert state.mode == AutopilotMode.PAUSE_BETWEEN
    assert state.current_stage_index == 0
    assert state.stages == []
    assert state.base_branch == "main"
    assert state.current_branch is None
    assert state.pr_urls == []
    assert state.awaiting_approval is False


def test_autopilot_state_current_stage():
    """Test AutopilotState.current_stage property."""
    stages = [
        Stage(number="1", name="Stage 1", tasks=[]),
        Stage(number="2", name="Stage 2", tasks=[]),
    ]
    state = AutopilotState(stages=stages, current_stage_index=0)

    assert state.current_stage is not None
    assert state.current_stage.number == "1"
    assert state.current_stage.name == "Stage 1"


def test_autopilot_state_next_stage():
    """Test AutopilotState.next_stage property."""
    stages = [
        Stage(number="1", name="Stage 1", tasks=[]),
        Stage(number="2", name="Stage 2", tasks=[]),
    ]
    state = AutopilotState(stages=stages, current_stage_index=0)

    assert state.next_stage is not None
    assert state.next_stage.number == "2"

    # At last stage
    state.current_stage_index = 1
    assert state.next_stage is None


def test_autopilot_state_is_complete():
    """Test AutopilotState.is_complete property."""
    stages = [
        Stage(number="1", name="Stage 1", status=StageStatus.COMPLETED, tasks=[]),
        Stage(number="2", name="Stage 2", status=StageStatus.PENDING, tasks=[]),
    ]
    state = AutopilotState(stages=stages)

    assert state.is_complete is False

    # All complete
    stages[1].status = StageStatus.COMPLETED
    assert state.is_complete is True


def test_autopilot_state_advance_to_next_stage():
    """Test AutopilotState.advance_to_next_stage method."""
    stages = [
        Stage(number="1", name="Stage 1", tasks=[]),
        Stage(number="2", name="Stage 2", tasks=[]),
    ]
    state = AutopilotState(stages=stages, current_stage_index=0)

    # Can advance
    result = state.advance_to_next_stage()
    assert result is True
    assert state.current_stage_index == 1

    # Cannot advance (at end)
    result = state.advance_to_next_stage()
    assert result is False
    assert state.current_stage_index == 1


def test_autopilot_state_pending_stages():
    """Test AutopilotState.pending_stages property."""
    stages = [
        Stage(number="1", name="Stage 1", status=StageStatus.COMPLETED, tasks=[]),
        Stage(number="2", name="Stage 2", status=StageStatus.PENDING, tasks=[]),
        Stage(number="3", name="Stage 3", status=StageStatus.IN_PROGRESS, tasks=[]),
    ]
    state = AutopilotState(stages=stages)

    pending = state.pending_stages
    assert len(pending) == 2  # PENDING and IN_PROGRESS
    assert pending[0].number == "2"
    assert pending[1].number == "3"


def test_autopilot_state_format_stages_summary():
    """Test AutopilotState.format_stages_summary method."""
    stages = [
        Stage(
            number="1",
            name="Stage 1",
            status=StageStatus.COMPLETED,
            tasks=[Task(text="Task", completed=True, line_number=1)],
        ),
        Stage(
            number="2",
            name="Stage 2",
            status=StageStatus.IN_PROGRESS,
            tasks=[Task(text="Task", completed=False, line_number=2)],
        ),
    ]
    state = AutopilotState(stages=stages, current_stage_index=1)

    summary = state.format_stages_summary()
    assert "Stage 1" in summary
    assert "Stage 2" in summary
    assert "1/1" in summary  # Completed tasks in stage 1
    assert "0/1" in summary  # Completed tasks in stage 2


def test_stage_depends_on_default():
    """Test Stage.depends_on defaults to empty list."""
    stage = Stage(number="1", name="First Stage", tasks=[])
    assert stage.depends_on == []


def test_stage_depends_on_set():
    """Test Stage.depends_on with explicit dependencies."""
    stage = Stage(
        number="3",
        name="Integration",
        depends_on=["1", "2"],
        tasks=[],
    )
    assert stage.depends_on == ["1", "2"]


def test_claude_output_creation():
    """Test ClaudeOutput model creation."""
    output = ClaudeOutput(
        type=ClaudeOutputType.STDOUT,
        content="Hello, world!",
    )

    assert output.type == ClaudeOutputType.STDOUT
    assert output.content == "Hello, world!"
    assert output.exit_code is None


def test_claude_output_with_exit_code():
    """Test ClaudeOutput with exit code."""
    output = ClaudeOutput(
        type=ClaudeOutputType.EXIT,
        content="Process exited",
        exit_code=0,
    )

    assert output.type == ClaudeOutputType.EXIT
    assert output.exit_code == 0
