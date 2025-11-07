"""Tests for logging configuration and log rotation."""

import time
from pathlib import Path

from shotgun.logging_config import cleanup_old_log_files


def test_cleanup_old_log_files_keeps_correct_number(tmp_path: Path) -> None:
    """Test that cleanup keeps exactly max_files log files."""
    # Create 15 log files with different timestamps
    log_files = []
    for i in range(15):
        log_file = tmp_path / f"shotgun-2024010{i:02d}T120000Z.log"
        log_file.touch()
        # Set different modification times (oldest to newest)
        time.sleep(0.01)  # Ensure different mtimes
        log_files.append(log_file)

    # Keep only 10 files
    cleanup_old_log_files(tmp_path, max_files=10)

    # Verify only 10 files remain
    remaining_files = sorted(tmp_path.glob("shotgun-*.log"))
    assert len(remaining_files) == 10

    # Verify the newest 10 files were kept (last 10 created)
    for log_file in log_files[-10:]:
        assert log_file.exists()

    # Verify the oldest 5 files were deleted
    for log_file in log_files[:5]:
        assert not log_file.exists()


def test_cleanup_old_log_files_with_fewer_than_max(tmp_path: Path) -> None:
    """Test that cleanup doesn't delete files when count is below max."""
    # Create 5 log files
    log_files = []
    for i in range(5):
        log_file = tmp_path / f"shotgun-2024010{i}T120000Z.log"
        log_file.touch()
        time.sleep(0.01)
        log_files.append(log_file)

    # Try to keep 10 files (more than we have)
    cleanup_old_log_files(tmp_path, max_files=10)

    # Verify all 5 files still exist
    remaining_files = list(tmp_path.glob("shotgun-*.log"))
    assert len(remaining_files) == 5
    for log_file in log_files:
        assert log_file.exists()


def test_cleanup_old_log_files_with_no_files(tmp_path: Path) -> None:
    """Test that cleanup handles empty directory gracefully."""
    # Don't create any files
    cleanup_old_log_files(tmp_path, max_files=10)

    # Verify no errors occurred and directory is still empty
    remaining_files = list(tmp_path.glob("shotgun-*.log"))
    assert len(remaining_files) == 0


def test_cleanup_old_log_files_ignores_non_shotgun_files(tmp_path: Path) -> None:
    """Test that cleanup only affects shotgun-*.log files."""
    # Create shotgun log files
    for i in range(15):
        log_file = tmp_path / f"shotgun-2024010{i:02d}T120000Z.log"
        log_file.touch()
        time.sleep(0.01)

    # Create non-shotgun files
    other_file1 = tmp_path / "other.log"
    other_file1.touch()
    other_file2 = tmp_path / "debug.log"
    other_file2.touch()
    other_file3 = tmp_path / "shotgun.txt"  # Wrong extension
    other_file3.touch()

    # Keep only 10 shotgun files
    cleanup_old_log_files(tmp_path, max_files=10)

    # Verify only 10 shotgun log files remain
    shotgun_files = list(tmp_path.glob("shotgun-*.log"))
    assert len(shotgun_files) == 10

    # Verify other files were not affected
    assert other_file1.exists()
    assert other_file2.exists()
    assert other_file3.exists()


def test_cleanup_old_log_files_keeps_exactly_one(tmp_path: Path) -> None:
    """Test that cleanup can keep just 1 file."""
    # Create 5 log files
    log_files = []
    for i in range(5):
        log_file = tmp_path / f"shotgun-2024010{i}T120000Z.log"
        log_file.touch()
        time.sleep(0.01)
        log_files.append(log_file)

    # Keep only 1 file
    cleanup_old_log_files(tmp_path, max_files=1)

    # Verify only 1 file remains (the newest)
    remaining_files = list(tmp_path.glob("shotgun-*.log"))
    assert len(remaining_files) == 1
    assert log_files[-1].exists()  # Newest file

    # Verify older files were deleted
    for log_file in log_files[:-1]:
        assert not log_file.exists()


def test_cleanup_old_log_files_handles_permission_errors(tmp_path: Path) -> None:
    """Test that cleanup continues even if some files can't be deleted."""
    # Create 5 log files
    log_files = []
    for i in range(5):
        log_file = tmp_path / f"shotgun-2024010{i}T120000Z.log"
        log_file.touch()
        time.sleep(0.01)
        log_files.append(log_file)

    # Make the oldest file read-only (simulate permission error on some systems)
    # Note: This might not work on all systems, but shouldn't cause test failure
    import stat

    old_mode = log_files[0].stat().st_mode
    try:
        log_files[0].chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)  # Read-only
    except Exception:  # noqa: S110
        # If we can't change permissions, skip this part of the test
        pass

    # Try to keep only 2 files
    cleanup_old_log_files(tmp_path, max_files=2)

    # Verify at least some cleanup occurred (may be 2 or 3 files depending on permissions)
    remaining_files = list(tmp_path.glob("shotgun-*.log"))
    assert len(remaining_files) <= 3  # Should be close to 2, might include read-only file

    # Restore permissions for cleanup
    try:
        log_files[0].chmod(old_mode)
    except Exception:  # noqa: S110
        pass


def test_cleanup_old_log_files_with_identical_mtimes(tmp_path: Path) -> None:
    """Test cleanup behavior when files have identical modification times."""
    # Create 5 log files
    for i in range(5):
        log_file = tmp_path / f"shotgun-2024010{i}T120000Z.log"
        log_file.touch()

    # Don't sleep between files, so they might have same mtime

    # Keep only 2 files
    cleanup_old_log_files(tmp_path, max_files=2)

    # Verify exactly 2 files remain
    remaining_files = list(tmp_path.glob("shotgun-*.log"))
    assert len(remaining_files) == 2


def test_cleanup_removes_legacy_log_file(tmp_path: Path) -> None:
    """Test that cleanup removes the legacy shotgun.log file."""
    # Create legacy log file
    legacy_log = tmp_path / "shotgun.log"
    legacy_log.touch()

    # Create some timestamped log files
    for i in range(3):
        log_file = tmp_path / f"shotgun-2024010{i}T120000Z.log"
        log_file.touch()
        time.sleep(0.01)

    # Verify legacy file exists before cleanup
    assert legacy_log.exists()

    # Run cleanup
    cleanup_old_log_files(tmp_path, max_files=10)

    # Verify legacy file was removed
    assert not legacy_log.exists()

    # Verify timestamped files still exist (under the limit)
    remaining_files = list(tmp_path.glob("shotgun-*.log"))
    assert len(remaining_files) == 3
