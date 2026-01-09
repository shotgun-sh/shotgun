"""Unit tests for gitignore module."""

import tempfile
from pathlib import Path

from shotgun.codebase.core.gitignore import GitignoreManager, load_gitignore_for_repo


def test_gitignore_manager_no_gitignore_file():
    """Test GitignoreManager when no .gitignore file exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = GitignoreManager(Path(tmpdir))

        # Nothing should be ignored
        assert not manager.is_ignored("test.py")
        assert not manager.is_ignored("src/main.py")
        assert manager.stats.gitignore_files_loaded == 0
        assert manager.stats.patterns_loaded == 0


def test_gitignore_manager_basic_patterns():
    """Test GitignoreManager with basic ignore patterns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create a .gitignore file
        gitignore = tmpdir_path / ".gitignore"
        gitignore.write_text(
            """
# Python
__pycache__/
*.pyc
.venv/
venv/

# Node
node_modules/

# Build artifacts
dist/
build/
"""
        )

        manager = GitignoreManager(tmpdir_path)

        # Check patterns were loaded
        assert manager.stats.gitignore_files_loaded == 1
        assert manager.stats.patterns_loaded > 0

        # Check files that should be ignored
        assert manager.is_ignored("__pycache__/something.py")
        assert manager.is_ignored("test.pyc")
        assert manager.is_ignored(".venv/lib/python3.11/site-packages/pkg")
        assert manager.is_ignored("venv/bin/python")
        assert manager.is_ignored("node_modules/package/index.js")
        assert manager.is_ignored("dist/bundle.js")
        assert manager.is_ignored("build/output.txt")

        # Check files that should NOT be ignored
        assert not manager.is_ignored("src/main.py")
        assert not manager.is_ignored("test/test_main.py")
        assert not manager.is_ignored("README.md")


def test_gitignore_manager_directory_patterns():
    """Test GitignoreManager with directory-specific patterns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        gitignore = tmpdir_path / ".gitignore"
        gitignore.write_text(
            """
# Directories
logs/
tmp/

# Specific files in specific locations
/config/local.json
"""
        )

        manager = GitignoreManager(tmpdir_path)

        # Directory patterns should match
        assert manager.is_directory_ignored("logs")
        assert manager.is_directory_ignored("tmp")

        # But not random files
        assert not manager.is_ignored("src/logs.py")


def test_gitignore_manager_negation_patterns():
    """Test GitignoreManager with negation patterns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        gitignore = tmpdir_path / ".gitignore"
        gitignore.write_text(
            """
# Ignore all logs
*.log

# But keep important.log
!important.log
"""
        )

        manager = GitignoreManager(tmpdir_path)

        # Regular logs should be ignored
        assert manager.is_ignored("debug.log")
        assert manager.is_ignored("error.log")

        # important.log should NOT be ignored due to negation
        assert not manager.is_ignored("important.log")


def test_gitignore_manager_wildcard_patterns():
    """Test GitignoreManager with wildcard patterns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        gitignore = tmpdir_path / ".gitignore"
        gitignore.write_text(
            """
# Single level wildcard
*.egg-info/

# Double wildcard (recursive)
**/secret.txt
"""
        )

        manager = GitignoreManager(tmpdir_path)

        # Single wildcard
        assert manager.is_ignored("mypackage.egg-info/PKG-INFO")

        # Double wildcard (recursive)
        assert manager.is_ignored("secret.txt")
        assert manager.is_ignored("deep/nested/path/secret.txt")


def test_gitignore_manager_comments_and_empty_lines():
    """Test that comments and empty lines are ignored."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        gitignore = tmpdir_path / ".gitignore"
        gitignore.write_text(
            """
# This is a comment

# Another comment
*.log

  # Indented comment

"""
        )

        manager = GitignoreManager(tmpdir_path)

        # Only *.log should be a valid pattern
        assert manager.is_ignored("test.log")
        # Comments should not be treated as patterns
        assert not manager.is_ignored("# This is a comment")


def test_gitignore_manager_respect_gitignore_false():
    """Test GitignoreManager with respect_gitignore=False."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        gitignore = tmpdir_path / ".gitignore"
        gitignore.write_text("*.log\n__pycache__/")

        manager = GitignoreManager(tmpdir_path, respect_gitignore=False)

        # Nothing should be ignored when respect_gitignore is False
        assert not manager.is_ignored("test.log")
        assert not manager.is_ignored("__pycache__/module.pyc")
        assert manager.stats.gitignore_files_loaded == 0


def test_gitignore_manager_filter_paths():
    """Test GitignoreManager.filter_paths method."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        gitignore = tmpdir_path / ".gitignore"
        gitignore.write_text("*.log\n__pycache__/")

        manager = GitignoreManager(tmpdir_path)

        paths = [
            Path("src/main.py"),
            Path("debug.log"),
            Path("test/test_main.py"),
            Path("error.log"),
            Path("__pycache__/module.pyc"),
        ]

        filtered = manager.filter_paths(paths)

        assert Path("src/main.py") in filtered
        assert Path("test/test_main.py") in filtered
        assert Path("debug.log") not in filtered
        assert Path("error.log") not in filtered
        assert Path("__pycache__/module.pyc") not in filtered


def test_gitignore_manager_stats_summary():
    """Test GitignoreManager.get_stats_summary method."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        gitignore = tmpdir_path / ".gitignore"
        gitignore.write_text("*.log\n__pycache__/")

        manager = GitignoreManager(tmpdir_path)

        # Check some paths to update stats
        manager.is_ignored("test.log")
        manager.is_ignored("main.py")
        manager.is_ignored("error.log")

        summary = manager.get_stats_summary()

        assert "1 files loaded" in summary
        assert "2 patterns" in summary
        assert "3 paths checked" in summary
        assert "2 ignored" in summary


def test_load_gitignore_for_repo_convenience_function():
    """Test the load_gitignore_for_repo convenience function."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        gitignore = tmpdir_path / ".gitignore"
        gitignore.write_text("*.pyc")

        manager = load_gitignore_for_repo(tmpdir_path)

        assert isinstance(manager, GitignoreManager)
        assert manager.is_ignored("test.pyc")
        assert not manager.is_ignored("test.py")


def test_gitignore_manager_absolute_path():
    """Test GitignoreManager with absolute paths."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        gitignore = tmpdir_path / ".gitignore"
        gitignore.write_text("*.log")

        manager = GitignoreManager(tmpdir_path)

        # Absolute path should work
        abs_path = tmpdir_path / "test.log"
        assert manager.is_ignored(abs_path)

        abs_path_ok = tmpdir_path / "test.py"
        assert not manager.is_ignored(abs_path_ok)


def test_gitignore_manager_path_outside_repo():
    """Test GitignoreManager with paths outside the repo."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        gitignore = tmpdir_path / ".gitignore"
        gitignore.write_text("*.log")

        manager = GitignoreManager(tmpdir_path)

        # Path outside repo should not be ignored
        outside_path = Path("/some/other/path/test.log")
        assert not manager.is_ignored(outside_path)
