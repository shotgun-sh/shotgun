"""Shared test configuration and fixtures for all tests.

This provides common utilities and cleanup fixtures that are needed
across both unit and integration tests, particularly for Kuzu database
resource management.
"""

# IMPORTANT: Set environment variables BEFORE any imports to ensure
# they're available when settings are loaded during module import
import os

os.environ["SHOTGUN_LOGGING_TO_FILE"] = "false"

# Now safe to import modules that depend on settings
import asyncio
import gc
import shutil
import tempfile
import uuid
from collections.abc import Generator
from pathlib import Path

import anyio
import pytest
import pytest_asyncio

from shotgun.codebase.core.manager import CodebaseGraphManager


@pytest.fixture(scope="session", autouse=True)
def cleanup_before_tests():
    """Clean up any leftover state before running tests.

    This session-scoped fixture runs once before all tests to ensure
    a clean starting state by removing leftover database files and
    clearing any class-level state from previous test runs.
    """
    # Clean up any leftover database files from previous runs
    import tempfile

    temp_dir = Path(tempfile.gettempdir())
    for test_dir in temp_dir.glob("shotgun_test*"):
        try:
            if test_dir.is_dir():
                shutil.rmtree(test_dir, ignore_errors=True)
        except Exception:  # noqa: S110
            pass

    # Clear any leftover class state
    CodebaseGraphManager._connections.clear()
    CodebaseGraphManager._databases.clear()
    CodebaseGraphManager._watchers.clear()
    CodebaseGraphManager._handlers.clear()
    CodebaseGraphManager._operations.clear()
    CodebaseGraphManager._lock = anyio.Lock()


@pytest_asyncio.fixture(autouse=True)
async def cleanup_kuzu_state():
    """Automatically clean up Kuzu state after each test.

    This fixture ensures that all Kuzu database connections, files,
    and class-level state are properly cleaned up after each test
    to prevent resource conflicts when running tests together.

    This is critical for preventing "Buffer manager exception: Mmap"
    errors that occur when database resources aren't properly released.
    """
    yield  # Run the test

    # After test completes, clean up all class-level state
    try:
        # 1. Stop all watchers first
        for _graph_id, watcher in list(CodebaseGraphManager._watchers.items()):
            try:
                if hasattr(watcher, "stop"):
                    watcher.stop()
                if hasattr(watcher, "join"):
                    watcher.join(timeout=1.0)
            except Exception:  # noqa: S110
                pass  # Ignore errors during cleanup

        # 2. Cancel all pending operations
        for _operation_id, task in list(CodebaseGraphManager._operations.items()):
            try:
                if not task.done():
                    task.cancel()
                    try:
                        await asyncio.wait_for(task, timeout=1.0)
                    except (asyncio.TimeoutError, asyncio.CancelledError):
                        pass
            except Exception:  # noqa: S110
                pass  # Ignore errors during cleanup

        # 3. Close all connections gracefully
        for _graph_id, conn in list(CodebaseGraphManager._connections.items()):
            try:
                conn.close()
            except Exception:  # noqa: S110
                pass  # Ignore errors during cleanup

        # 4. Close all databases gracefully
        for _graph_id, db in list(CodebaseGraphManager._databases.items()):
            try:
                db.close()
            except Exception:  # noqa: S110
                pass  # Ignore errors during cleanup

        # 5. Force cleanup any remaining database files
        # Look for any .kuzu files in temp directories
        import tempfile

        temp_dir = Path(tempfile.gettempdir())
        for kuzu_file in temp_dir.glob("**/test*.kuzu"):
            try:
                kuzu_file.unlink()
            except Exception:  # noqa: S110
                pass
        for wal_file in temp_dir.glob("**/test*.kuzu.wal"):
            try:
                wal_file.unlink()
            except Exception:  # noqa: S110
                pass
        # Also look for shotgun_test directories
        for test_dir in temp_dir.glob("shotgun_test*"):
            try:
                if test_dir.is_dir():
                    shutil.rmtree(test_dir, ignore_errors=True)
            except Exception:  # noqa: S110
                pass

        # 6. Clear all class-level dictionaries
        CodebaseGraphManager._connections.clear()
        CodebaseGraphManager._databases.clear()
        CodebaseGraphManager._watchers.clear()
        CodebaseGraphManager._handlers.clear()
        CodebaseGraphManager._operations.clear()

        # 7. Reset the class-level lock
        CodebaseGraphManager._lock = anyio.Lock()

        # 8. Force garbage collection to ensure cleanup
        gc.collect()

    except Exception:
        # If cleanup fails, still try to clear the dictionaries
        # to prevent test contamination
        CodebaseGraphManager._connections.clear()
        CodebaseGraphManager._databases.clear()
        CodebaseGraphManager._watchers.clear()
        CodebaseGraphManager._handlers.clear()
        CodebaseGraphManager._operations.clear()
        CodebaseGraphManager._lock = anyio.Lock()


@pytest.fixture
def unique_graph_id() -> str:
    """Generate a unique graph ID for each test to prevent conflicts.

    Returns:
        A unique string suitable for use as a graph ID in tests
    """
    return f"test-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def temp_storage_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test storage that gets cleaned up.

    Uses tempfile.TemporaryDirectory for guaranteed cleanup.

    Yields:
        Path to a temporary directory that will be automatically cleaned up
    """
    with tempfile.TemporaryDirectory(prefix="shotgun_test_") as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def isolated_shotgun_home(temp_storage_dir, monkeypatch):
    """Provide an isolated shotgun home directory for testing.

    Sets SHOTGUN_HOME environment variable to a temporary directory
    that gets cleaned up after the test.

    Args:
        temp_storage_dir: Temporary directory fixture
        monkeypatch: pytest monkeypatch fixture for environment variables

    Returns:
        Path to the isolated shotgun home directory
    """
    test_home = temp_storage_dir / "test_shotgun_home"
    test_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SHOTGUN_HOME", str(test_home))
    return test_home
