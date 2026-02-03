"""Tests for agents.models module."""

from pathlib import Path

import pytest

from shotgun.agents.models import (
    AgentSystemPromptContext,
    FileOperationTracker,
    FileOperationType,
)


@pytest.mark.smoke
def test_file_operation_tracker_get_display_path_empty():
    """Test get_display_path with no operations."""
    tracker = FileOperationTracker()
    assert tracker.get_display_path() is None


def test_file_operation_tracker_get_display_path_single_file():
    """Test get_display_path with single file."""
    tracker = FileOperationTracker()
    test_file = Path("/home/user/project/file.py")
    tracker.add_operation(test_file, FileOperationType.UPDATED)

    result = tracker.get_display_path()
    # Compare against the resolved path since add_operation uses Path.resolve()
    assert result == str(test_file.resolve())


def test_file_operation_tracker_get_display_path_multiple_files_same_dir():
    """Test get_display_path with multiple files in same directory."""
    tracker = FileOperationTracker()
    file1 = Path("/home/user/project/file1.py")
    file2 = Path("/home/user/project/file2.py")
    tracker.add_operation(file1, FileOperationType.UPDATED)
    tracker.add_operation(file2, FileOperationType.CREATED)

    result = tracker.get_display_path()
    # Should return the common directory
    assert result == str(Path("/home/user/project").resolve())


def test_file_operation_tracker_get_display_path_multiple_files_different_dirs():
    """Test get_display_path with multiple files in different directories."""
    tracker = FileOperationTracker()
    file1 = Path("/home/user/project/src/file1.py")
    file2 = Path("/home/user/project/tests/file2.py")
    file3 = Path("/home/user/project/docs/readme.md")
    tracker.add_operation(file1, FileOperationType.UPDATED)
    tracker.add_operation(file2, FileOperationType.CREATED)
    tracker.add_operation(file3, FileOperationType.DELETED)

    result = tracker.get_display_path()
    # Should return the common parent directory
    assert result == str(Path("/home/user/project").resolve())


def test_file_operation_tracker_get_display_path_duplicate_files():
    """Test get_display_path with duplicate file paths."""
    tracker = FileOperationTracker()
    test_file = Path("/home/user/project/file.py")
    # Add the same file multiple times
    tracker.add_operation(test_file, FileOperationType.UPDATED)
    tracker.add_operation(test_file, FileOperationType.UPDATED)
    tracker.add_operation(test_file, FileOperationType.UPDATED)

    result = tracker.get_display_path()
    # Should still return the single file path since they're all the same
    assert result == str(test_file.resolve())


def test_file_operation_tracker_get_display_path_nested_paths():
    """Test get_display_path with deeply nested paths."""
    tracker = FileOperationTracker()
    file1 = Path("/home/user/project/src/components/ui/button.tsx")
    file2 = Path("/home/user/project/src/components/ui/input.tsx")
    tracker.add_operation(file1, FileOperationType.CREATED)
    tracker.add_operation(file2, FileOperationType.UPDATED)

    result = tracker.get_display_path()
    # Should return the common parent directory
    assert result == str(Path("/home/user/project/src/components/ui").resolve())


def test_file_operation_tracker_add_operation():
    """Test adding operations to tracker."""
    tracker = FileOperationTracker()

    # Add with Path object
    file1 = Path("/home/user/file1.py")
    tracker.add_operation(file1, FileOperationType.CREATED)
    assert len(tracker.operations) == 1
    assert tracker.operations[0].file_path == str(file1.resolve())
    assert tracker.operations[0].operation == FileOperationType.CREATED

    # Add with string
    file2 = "/home/user/file2.py"
    tracker.add_operation(file2, FileOperationType.UPDATED)
    assert len(tracker.operations) == 2
    assert tracker.operations[1].file_path == str(Path(file2).resolve())
    assert tracker.operations[1].operation == FileOperationType.UPDATED


def test_file_operation_tracker_clear():
    """Test clearing operations from tracker."""
    tracker = FileOperationTracker()
    tracker.add_operation(Path("/home/user/file1.py"), FileOperationType.CREATED)
    tracker.add_operation(Path("/home/user/file2.py"), FileOperationType.UPDATED)

    assert len(tracker.operations) == 2
    tracker.clear()
    assert len(tracker.operations) == 0
    assert tracker.get_display_path() is None


def test_file_operation_tracker_get_summary():
    """Test get_summary method."""
    tracker = FileOperationTracker()
    file1 = Path("/home/user/file1.py")
    file2 = Path("/home/user/file2.py")
    file3 = Path("/home/user/file3.py")
    tracker.add_operation(file1, FileOperationType.CREATED)
    tracker.add_operation(file2, FileOperationType.UPDATED)
    tracker.add_operation(file3, FileOperationType.DELETED)
    tracker.add_operation(file2, FileOperationType.UPDATED)  # Duplicate

    summary = tracker.get_summary()

    assert summary[FileOperationType.CREATED] == [str(file1.resolve())]
    assert summary[FileOperationType.UPDATED] == [str(file2.resolve())]
    assert summary[FileOperationType.DELETED] == [str(file3.resolve())]


def test_file_operation_tracker_format_summary():
    """Test format_summary method."""
    tracker = FileOperationTracker()
    file1 = Path("/home/user/file1.py")
    file2 = Path("/home/user/file2.py")
    tracker.add_operation(file1, FileOperationType.CREATED)
    tracker.add_operation(file2, FileOperationType.UPDATED)

    summary = tracker.format_summary()

    assert "Files modified during this run:" in summary
    assert "Created:" in summary
    assert str(file1.resolve()) in summary
    assert "Updated:" in summary
    assert str(file2.resolve()) in summary


def test_file_operation_tracker_format_summary_empty():
    """Test format_summary with no operations."""
    tracker = FileOperationTracker()
    summary = tracker.format_summary()
    assert summary == "No files were modified during this run."


# Tests for AgentSystemPromptContext multimodal capabilities


def test_agent_system_prompt_context_default_capabilities():
    """Test that AgentSystemPromptContext defaults to supporting multimodal."""
    context = AgentSystemPromptContext(
        interactive_mode=True,
        mode="router",
    )
    assert context.supports_pdf is True
    assert context.supports_images is True


def test_agent_system_prompt_context_custom_capabilities():
    """Test that AgentSystemPromptContext can have custom capabilities."""
    context = AgentSystemPromptContext(
        interactive_mode=True,
        mode="router",
        supports_pdf=False,
        supports_images=True,
    )
    assert context.supports_pdf is False
    assert context.supports_images is True


def test_agent_system_prompt_context_no_multimodal():
    """Test AgentSystemPromptContext with no multimodal support."""
    context = AgentSystemPromptContext(
        interactive_mode=True,
        mode="router",
        supports_pdf=False,
        supports_images=False,
    )
    assert context.supports_pdf is False
    assert context.supports_images is False


def test_agent_system_prompt_context_model_dump_includes_capabilities():
    """Test that model_dump includes the capability fields."""
    context = AgentSystemPromptContext(
        interactive_mode=True,
        mode="router",
        supports_pdf=False,
        supports_images=True,
    )
    dumped = context.model_dump()
    assert "supports_pdf" in dumped
    assert "supports_images" in dumped
    assert dumped["supports_pdf"] is False
    assert dumped["supports_images"] is True
