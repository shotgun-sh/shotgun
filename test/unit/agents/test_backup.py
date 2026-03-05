"""Tests for pre-agent backup functionality."""

from pathlib import Path

from shotgun.agents.backup import backup_artifacts, cleanup_old_backups


def test_backup_creates_timestamped_directory(tmp_path: Path):
    shotgun_dir = tmp_path / ".shotgun"
    shotgun_dir.mkdir()
    (shotgun_dir / "specification.md").write_text("# Spec content")
    (shotgun_dir / "tasks.md").write_text("# Tasks")

    # Point backups to tmp_path
    backup_base = tmp_path / "backups" / "pre-agent"

    import shotgun.agents.backup as backup_mod

    original = backup_mod._get_backup_base_dir
    backup_mod._get_backup_base_dir = lambda: backup_base
    try:
        result = backup_artifacts(shotgun_dir)
    finally:
        backup_mod._get_backup_base_dir = original

    assert result is not None
    assert result.parent == backup_base

    # Verify files were copied
    copied_files = list(result.rglob("*"))
    copied_names = {f.name for f in copied_files if f.is_file()}
    assert copied_names == {"specification.md", "tasks.md"}

    # Verify content preserved
    assert (result / "specification.md").read_text() == "# Spec content"
    assert (result / "tasks.md").read_text() == "# Tasks"


def test_backup_preserves_subdirectory_structure(tmp_path: Path):
    shotgun_dir = tmp_path / ".shotgun"
    shotgun_dir.mkdir()
    (shotgun_dir / "contracts").mkdir()
    (shotgun_dir / "contracts" / "api.md").write_text("API contract")
    (shotgun_dir / "research").mkdir()
    (shotgun_dir / "research" / "notes.md").write_text("Research notes")
    (shotgun_dir / "specification.md").write_text("Top-level spec")

    backup_base = tmp_path / "backups" / "pre-agent"

    import shotgun.agents.backup as backup_mod

    original = backup_mod._get_backup_base_dir
    backup_mod._get_backup_base_dir = lambda: backup_base
    try:
        result = backup_artifacts(shotgun_dir)
    finally:
        backup_mod._get_backup_base_dir = original

    assert result is not None
    assert (result / "contracts" / "api.md").read_text() == "API contract"
    assert (result / "research" / "notes.md").read_text() == "Research notes"
    assert (result / "specification.md").read_text() == "Top-level spec"


def test_backup_skips_when_dir_does_not_exist(tmp_path: Path):
    nonexistent = tmp_path / ".shotgun"
    result = backup_artifacts(nonexistent)
    assert result is None


def test_backup_skips_when_dir_is_empty(tmp_path: Path):
    shotgun_dir = tmp_path / ".shotgun"
    shotgun_dir.mkdir()

    result = backup_artifacts(shotgun_dir)
    assert result is None


def test_backup_skips_when_only_subdirs_no_files(tmp_path: Path):
    shotgun_dir = tmp_path / ".shotgun"
    shotgun_dir.mkdir()
    (shotgun_dir / "empty_subdir").mkdir()

    result = backup_artifacts(shotgun_dir)
    assert result is None


def test_cleanup_deletes_oldest_backups(tmp_path: Path):
    backup_base = tmp_path / "backups" / "pre-agent"
    backup_base.mkdir(parents=True)

    # Create 5 backup dirs with sequential timestamps
    dirs = []
    for i in range(5):
        d = backup_base / f"20250101_00000{i}"
        d.mkdir()
        (d / "spec.md").write_text(f"backup {i}")
        dirs.append(d)

    import shotgun.agents.backup as backup_mod

    original = backup_mod._get_backup_base_dir
    backup_mod._get_backup_base_dir = lambda: backup_base
    try:
        cleanup_old_backups(max_backups=3)
    finally:
        backup_mod._get_backup_base_dir = original

    remaining = sorted(d.name for d in backup_base.iterdir() if d.is_dir())
    assert remaining == ["20250101_000002", "20250101_000003", "20250101_000004"]


def test_cleanup_noop_when_under_limit(tmp_path: Path):
    backup_base = tmp_path / "backups" / "pre-agent"
    backup_base.mkdir(parents=True)

    for i in range(3):
        d = backup_base / f"20250101_00000{i}"
        d.mkdir()
        (d / "spec.md").write_text(f"backup {i}")

    import shotgun.agents.backup as backup_mod

    original = backup_mod._get_backup_base_dir
    backup_mod._get_backup_base_dir = lambda: backup_base
    try:
        cleanup_old_backups(max_backups=5)
    finally:
        backup_mod._get_backup_base_dir = original

    remaining = list(backup_base.iterdir())
    assert len(remaining) == 3


def test_cleanup_noop_when_no_backup_dir(tmp_path: Path):
    backup_base = tmp_path / "nonexistent"

    import shotgun.agents.backup as backup_mod

    original = backup_mod._get_backup_base_dir
    backup_mod._get_backup_base_dir = lambda: backup_base
    try:
        cleanup_old_backups()  # Should not raise
    finally:
        backup_mod._get_backup_base_dir = original
