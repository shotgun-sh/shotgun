"""Fixtures for shared_specs tests."""

from pathlib import Path

import pytest


@pytest.fixture
def temp_shotgun_dir(tmp_path: Path) -> Path:
    """Create a temporary .shotgun/ directory with test files."""
    shotgun_dir = tmp_path / ".shotgun"
    shotgun_dir.mkdir()

    # Create some test files
    (shotgun_dir / "research.md").write_text("# Research\n\nSome research content.")
    (shotgun_dir / "specification.md").write_text("# Specification\n\nSpec content.")

    # Create a subdirectory with files
    contracts_dir = shotgun_dir / "contracts"
    contracts_dir.mkdir()
    (contracts_dir / "api.yaml").write_text("openapi: 3.0.0\ninfo:\n  title: Test API")
    (contracts_dir / "models.py").write_text("class TestModel:\n    pass")

    return tmp_path


@pytest.fixture
def temp_shotgun_dir_with_ignored_files(temp_shotgun_dir: Path) -> Path:
    """Create a temporary .shotgun/ directory with files that should be ignored."""
    shotgun_dir = temp_shotgun_dir / ".shotgun"

    # Create files that should be ignored
    (shotgun_dir / ".DS_Store").write_bytes(b"\x00\x00\x00\x01Bud1")
    (shotgun_dir / "file.pyc").write_bytes(b"compiled python")
    (shotgun_dir / "file.swp").write_text("vim swap file")
    (shotgun_dir / "backup.bak").write_text("backup file")
    (shotgun_dir / "temp~").write_text("temp file")

    # Create __pycache__ directory with files
    pycache_dir = shotgun_dir / "__pycache__"
    pycache_dir.mkdir()
    (pycache_dir / "module.cpython-311.pyc").write_bytes(b"cached")

    # Create .vscode directory with files
    vscode_dir = shotgun_dir / ".vscode"
    vscode_dir.mkdir()
    (vscode_dir / "settings.json").write_text('{"key": "value"}')

    return temp_shotgun_dir


@pytest.fixture
def temp_file_for_hash(tmp_path: Path) -> Path:
    """Create a temporary file with known content for hash testing."""
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("Hello, World!")
    return test_file


@pytest.fixture
def large_temp_file(tmp_path: Path) -> Path:
    """Create a larger temporary file (>10MB) for testing chunk size."""
    test_file = tmp_path / "large_file.bin"
    # Create a 15MB file
    with open(test_file, "wb") as f:
        f.write(b"x" * (15 * 1024 * 1024))
    return test_file
