"""Unit tests for config migrations across versions.

This file contains example configs from each version to ensure migrations work correctly.
"""

import json
import tempfile
from pathlib import Path

import pytest

from shotgun.agents.config.manager import (
    CURRENT_CONFIG_VERSION,
    ConfigManager,
    _apply_migrations,
    _create_backup,
    _migrate_v2_to_v3,
    _migrate_v3_to_v4,
    _migrate_v4_to_v5,
)
from shotgun.agents.config.models import ProviderType, ShotgunConfig

# Example configs for each version based on git history
V2_CONFIG = {
    "openai": {"api_key": "sk-test123"},
    "anthropic": {"api_key": None},
    "google": {"api_key": None},
    "shotgun": {"api_key": None},
    "selected_model": "gpt-5",
    "user_id": "test-user-id-12345",
    "config_version": 2,
}

V3_CONFIG = {
    "openai": {"api_key": "sk-test123"},
    "anthropic": {"api_key": None},
    "google": {"api_key": None},
    "shotgun": {"api_key": None},
    "selected_model": "gpt-5",
    "shotgun_instance_id": "test-user-id-12345",
    "config_version": 3,
}

V4_CONFIG = {
    "openai": {"api_key": "sk-test123"},
    "anthropic": {"api_key": None},
    "google": {"api_key": None},
    "shotgun": {"api_key": None},
    "selected_model": "gpt-5",
    "shotgun_instance_id": "test-user-id-12345",
    "config_version": 4,
    "shown_welcome_screen": False,
    "marketing": {"messages": {}},
}

V5_CONFIG = {
    "openai": {"api_key": "sk-test123", "supports_streaming": None},
    "anthropic": {"api_key": None},
    "google": {"api_key": None},
    "shotgun": {"api_key": None, "supabase_jwt": None},
    "selected_model": "gpt-5",
    "shotgun_instance_id": "test-user-id-12345",
    "config_version": 5,
    "shown_welcome_screen": False,
    "shown_onboarding_popup": None,
    "marketing": {"messages": {}},
}


def test_migrate_v2_to_v3():
    """Test migration from version 2 to version 3."""
    config = V2_CONFIG.copy()

    result = _migrate_v2_to_v3(config)

    assert result["config_version"] == 3
    assert "user_id" not in result
    assert result["shotgun_instance_id"] == "test-user-id-12345"
    assert result["openai"] == {"api_key": "sk-test123"}


def test_migrate_v3_to_v4():
    """Test migration from version 3 to version 4."""
    config = V3_CONFIG.copy()

    result = _migrate_v3_to_v4(config)

    assert result["config_version"] == 4
    assert "marketing" in result
    assert result["marketing"] == {"messages": {}}
    assert result["shotgun_instance_id"] == "test-user-id-12345"


def test_migrate_v3_to_v4_with_byok_key():
    """Test v3->v4 migration sets shown_welcome_screen for existing BYOK users."""
    config = V3_CONFIG.copy()

    result = _migrate_v3_to_v4(config)

    assert result["config_version"] == 4
    assert result["shown_welcome_screen"] is False  # Should be set for BYOK users


def test_migrate_v3_to_v4_without_byok_key():
    """Test v3->v4 migration doesn't set shown_welcome_screen for new users."""
    config = V3_CONFIG.copy()
    config["openai"]["api_key"] = None  # No BYOK key

    result = _migrate_v3_to_v4(config)

    assert result["config_version"] == 4
    assert "shown_welcome_screen" not in result  # Should not be set for new users


def test_migrate_v4_to_v5():
    """Test migration from version 4 to version 5."""
    config = V4_CONFIG.copy()

    result = _migrate_v4_to_v5(config)

    assert result["config_version"] == 5
    assert result["openai"]["supports_streaming"] is None
    assert result["shotgun_instance_id"] == "test-user-id-12345"
    assert result["marketing"] == {"messages": {}}


def test_migrate_v4_to_v5_without_openai():
    """Test v4->v5 migration when openai config doesn't exist."""
    config = V4_CONFIG.copy()
    del config["openai"]

    result = _migrate_v4_to_v5(config)

    assert result["config_version"] == 5
    assert "openai" not in result  # Should not create openai config if it didn't exist


def test_apply_migrations_from_v2_to_current():
    """Test applying all migrations from v2 to current version."""
    config = V2_CONFIG.copy()

    result = _apply_migrations(config)

    assert result["config_version"] == CURRENT_CONFIG_VERSION
    assert "user_id" not in result
    assert result["shotgun_instance_id"] == "test-user-id-12345"
    assert "marketing" in result
    assert result["marketing"] == {"messages": {}}
    assert result["openai"]["supports_streaming"] is None


def test_apply_migrations_from_v3_to_current():
    """Test applying migrations from v3 to current version."""
    config = V3_CONFIG.copy()

    result = _apply_migrations(config)

    assert result["config_version"] == CURRENT_CONFIG_VERSION
    assert result["shotgun_instance_id"] == "test-user-id-12345"
    assert "marketing" in result
    assert result["openai"]["supports_streaming"] is None


def test_apply_migrations_from_v4_to_current():
    """Test applying migrations from v4 to current version."""
    config = V4_CONFIG.copy()

    result = _apply_migrations(config)

    assert result["config_version"] == CURRENT_CONFIG_VERSION
    assert result["shotgun_instance_id"] == "test-user-id-12345"
    assert result["marketing"] == {"messages": {}}
    assert result["openai"]["supports_streaming"] is None


def test_apply_migrations_already_current():
    """Test applying migrations when already at current version."""
    config = V5_CONFIG.copy()

    result = _apply_migrations(config)

    assert result["config_version"] == CURRENT_CONFIG_VERSION
    assert result == V5_CONFIG  # Should be unchanged


def test_apply_migrations_sequential():
    """Test that migrations are applied sequentially v2->v3->v4->v5."""
    config = V2_CONFIG.copy()

    result = _apply_migrations(config)

    # Should have all changes from each migration
    assert "user_id" not in result  # v2->v3 change
    assert result["shotgun_instance_id"] == "test-user-id-12345"  # v2->v3 change
    assert "marketing" in result  # v3->v4 change
    assert result["shown_welcome_screen"] is False  # v3->v4 change (BYOK user)
    assert result["openai"]["supports_streaming"] is None  # v4->v5 change
    assert result["config_version"] == CURRENT_CONFIG_VERSION


@pytest.mark.asyncio
async def test_config_manager_loads_v2_config():
    """Test ConfigManager can load and migrate a v2 config file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"

        # Write a v2 config file
        with open(config_path, "w") as f:
            json.dump(V2_CONFIG, f)

        manager = ConfigManager(config_path=config_path)
        config = await manager.load()

        # Should be migrated to current version
        assert config.config_version == CURRENT_CONFIG_VERSION
        assert config.shotgun_instance_id == "test-user-id-12345"
        assert hasattr(config, "marketing")
        assert config.openai.supports_streaming is None


@pytest.mark.asyncio
async def test_config_manager_loads_v3_config():
    """Test ConfigManager can load and migrate a v3 config file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"

        # Write a v3 config file
        with open(config_path, "w") as f:
            json.dump(V3_CONFIG, f)

        manager = ConfigManager(config_path=config_path)
        config = await manager.load()

        # Should be migrated to current version
        assert config.config_version == CURRENT_CONFIG_VERSION
        assert config.shotgun_instance_id == "test-user-id-12345"
        assert hasattr(config, "marketing")
        assert config.openai.supports_streaming is None


@pytest.mark.asyncio
async def test_config_manager_loads_v4_config():
    """Test ConfigManager can load and migrate a v4 config file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"

        # Write a v4 config file
        with open(config_path, "w") as f:
            json.dump(V4_CONFIG, f)

        manager = ConfigManager(config_path=config_path)
        config = await manager.load()

        # Should be migrated to current version
        assert config.config_version == CURRENT_CONFIG_VERSION
        assert config.shotgun_instance_id == "test-user-id-12345"
        assert config.marketing.messages == {}
        assert config.openai.supports_streaming is None


@pytest.mark.asyncio
async def test_config_manager_preserves_user_data_during_migration():
    """Test that user data is preserved during migration."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"

        # Create a v2 config with multiple API keys
        v2_with_keys = V2_CONFIG.copy()
        v2_with_keys["openai"]["api_key"] = "sk-openai-key"
        v2_with_keys["anthropic"]["api_key"] = "sk-ant-key"
        v2_with_keys["google"]["api_key"] = "google-key"
        v2_with_keys["selected_model"] = "claude-sonnet-4-5"

        with open(config_path, "w") as f:
            json.dump(v2_with_keys, f)

        manager = ConfigManager(config_path=config_path)
        config = await manager.load()

        # All user data should be preserved
        assert config.config_version == CURRENT_CONFIG_VERSION
        assert config.openai.api_key.get_secret_value() == "sk-openai-key"
        assert config.anthropic.api_key.get_secret_value() == "sk-ant-key"
        assert config.google.api_key.get_secret_value() == "google-key"
        # Note: selected_model might be reset if invalid, but that's separate logic


def test_migration_idempotency():
    """Test that running the same migration twice doesn't break anything."""
    config = V2_CONFIG.copy()

    # Run migration twice
    result1 = _migrate_v2_to_v3(config.copy())
    result2 = _migrate_v2_to_v3(result1.copy())

    # Should be stable
    assert result1 == result2
    assert result2["config_version"] == 3
    assert result2["shotgun_instance_id"] == "test-user-id-12345"


def test_apply_migrations_handles_missing_version():
    """Test that configs without version field default to v2."""
    config = V2_CONFIG.copy()
    del config["config_version"]  # Remove version field

    result = _apply_migrations(config)

    # Should default to v2 and migrate to current
    assert result["config_version"] == CURRENT_CONFIG_VERSION
    assert "user_id" not in result
    assert result["shotgun_instance_id"] == "test-user-id-12345"


# Tests with populated configs (non-empty values)


def test_migrate_v2_to_v3_with_all_providers_configured():
    """Test v2->v3 migration preserves all provider API keys."""
    config = V2_CONFIG.copy()
    config["openai"]["api_key"] = "sk-proj-abc123xyz"
    config["anthropic"]["api_key"] = "sk-ant-api03-xyz789"
    config["google"]["api_key"] = "AIzaSyABC123XYZ789"
    config["selected_model"] = "gpt-5"

    result = _migrate_v2_to_v3(config)

    assert result["config_version"] == 3
    assert result["shotgun_instance_id"] == "test-user-id-12345"
    assert result["openai"]["api_key"] == "sk-proj-abc123xyz"
    assert result["anthropic"]["api_key"] == "sk-ant-api03-xyz789"
    assert result["google"]["api_key"] == "AIzaSyABC123XYZ789"
    assert result["selected_model"] == "gpt-5"


def test_migrate_v2_to_v3_with_shotgun_account():
    """Test v2->v3 migration preserves Shotgun Account key."""
    config = V2_CONFIG.copy()
    config["shotgun"]["api_key"] = "sg_test_key_12345"

    result = _migrate_v2_to_v3(config)

    assert result["config_version"] == 3
    assert result["shotgun"]["api_key"] == "sg_test_key_12345"
    assert result["shotgun_instance_id"] == "test-user-id-12345"


def test_migrate_v3_to_v4_preserves_multiple_providers():
    """Test v3->v4 migration with multiple providers configured."""
    config = V3_CONFIG.copy()
    config["openai"]["api_key"] = "sk-proj-openai"
    config["anthropic"]["api_key"] = "sk-ant-anthropic"
    config["google"]["api_key"] = "AIza-google"
    config["shotgun"]["api_key"] = "sg_account_key"
    config["selected_model"] = "claude-sonnet-4-5"

    result = _migrate_v3_to_v4(config)

    assert result["config_version"] == 4
    assert result["marketing"] == {"messages": {}}
    assert result["shown_welcome_screen"] is False  # Has BYOK key
    # Verify all providers preserved
    assert result["openai"]["api_key"] == "sk-proj-openai"
    assert result["anthropic"]["api_key"] == "sk-ant-anthropic"
    assert result["google"]["api_key"] == "AIza-google"
    assert result["shotgun"]["api_key"] == "sg_account_key"
    assert result["selected_model"] == "claude-sonnet-4-5"


def test_migrate_v3_to_v4_with_only_shotgun_account():
    """Test v3->v4 migration for Shotgun Account only user (no BYOK)."""
    config = V3_CONFIG.copy()
    config["openai"]["api_key"] = None
    config["anthropic"]["api_key"] = None
    config["google"]["api_key"] = None
    config["shotgun"]["api_key"] = "sg_only_account_key"
    config["selected_model"] = "gpt-5"

    result = _migrate_v3_to_v4(config)

    assert result["config_version"] == 4
    assert "shown_welcome_screen" not in result  # No BYOK keys
    assert result["shotgun"]["api_key"] == "sg_only_account_key"
    assert result["selected_model"] == "gpt-5"


def test_migrate_v4_to_v5_preserves_all_fields():
    """Test v4->v5 migration preserves all existing fields."""
    config = V4_CONFIG.copy()
    config["openai"]["api_key"] = "sk-proj-test"
    config["anthropic"]["api_key"] = "sk-ant-test"
    config["google"]["api_key"] = "AIza-test"
    config["shotgun"]["api_key"] = "sg_test"
    config["selected_model"] = "claude-opus-4-1"
    config["shown_welcome_screen"] = True
    config["marketing"]["messages"] = {
        "github_star_v1": {
            "shown_at": "2025-11-01T12:00:00Z"
        }
    }

    result = _migrate_v4_to_v5(config)

    assert result["config_version"] == 5
    assert result["openai"]["supports_streaming"] is None
    # Verify everything else preserved
    assert result["openai"]["api_key"] == "sk-proj-test"
    assert result["anthropic"]["api_key"] == "sk-ant-test"
    assert result["google"]["api_key"] == "AIza-test"
    assert result["shotgun"]["api_key"] == "sg_test"
    assert result["selected_model"] == "claude-opus-4-1"
    assert result["shown_welcome_screen"] is True
    assert result["marketing"]["messages"]["github_star_v1"]["shown_at"] == "2025-11-01T12:00:00Z"


def test_migrate_v4_to_v5_with_multiple_marketing_messages():
    """Test v4->v5 migration preserves multiple marketing message records."""
    config = V4_CONFIG.copy()
    config["marketing"]["messages"] = {
        "github_star_v1": {"shown_at": "2025-11-01T10:00:00Z"},
        "feedback_prompt_v1": {"shown_at": "2025-11-02T15:30:00Z"},
        "survey_v2": {"shown_at": "2025-11-03T09:45:00Z"},
    }

    result = _migrate_v4_to_v5(config)

    assert result["config_version"] == 5
    assert len(result["marketing"]["messages"]) == 3
    assert result["marketing"]["messages"]["github_star_v1"]["shown_at"] == "2025-11-01T10:00:00Z"
    assert result["marketing"]["messages"]["feedback_prompt_v1"]["shown_at"] == "2025-11-02T15:30:00Z"
    assert result["marketing"]["messages"]["survey_v2"]["shown_at"] == "2025-11-03T09:45:00Z"


@pytest.mark.asyncio
async def test_config_manager_loads_v3_with_supabase_jwt():
    """Test ConfigManager preserves Supabase JWT during v3->current migration."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"

        # Create v3 config with Supabase JWT
        v3_with_jwt = V3_CONFIG.copy()
        v3_with_jwt["shotgun"]["api_key"] = "sg_api_key_test"
        v3_with_jwt["shotgun"]["supabase_jwt"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"
        v3_with_jwt["openai"]["api_key"] = "sk-proj-test"

        with open(config_path, "w") as f:
            json.dump(v3_with_jwt, f)

        manager = ConfigManager(config_path=config_path)
        config = await manager.load()

        assert config.config_version == CURRENT_CONFIG_VERSION
        assert config.shotgun.api_key.get_secret_value() == "sg_api_key_test"
        assert config.shotgun.supabase_jwt.get_secret_value() == "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"
        assert config.openai.api_key.get_secret_value() == "sk-proj-test"


@pytest.mark.asyncio
async def test_config_manager_loads_v4_with_marketing_data():
    """Test ConfigManager preserves marketing message data during v4->v5 migration."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"

        # Create v4 config with marketing messages
        v4_with_marketing = V4_CONFIG.copy()
        v4_with_marketing["openai"]["api_key"] = "sk-proj-xyz"
        v4_with_marketing["marketing"]["messages"] = {
            "github_star_v1": {"shown_at": "2025-11-01T12:00:00Z"}
        }
        v4_with_marketing["shown_welcome_screen"] = True

        with open(config_path, "w") as f:
            json.dump(v4_with_marketing, f)

        manager = ConfigManager(config_path=config_path)
        config = await manager.load()

        assert config.config_version == CURRENT_CONFIG_VERSION
        assert config.openai.api_key.get_secret_value() == "sk-proj-xyz"
        assert config.shown_welcome_screen is True
        assert "github_star_v1" in config.marketing.messages
        assert config.marketing.messages["github_star_v1"].shown_at.isoformat() == "2025-11-01T12:00:00+00:00"


def test_apply_migrations_v2_to_current_with_full_config():
    """Test complete migration path v2->v5 with fully populated config."""
    config = V2_CONFIG.copy()
    config["openai"]["api_key"] = "sk-proj-full-test"
    config["anthropic"]["api_key"] = "sk-ant-full-test"
    config["google"]["api_key"] = "AIza-full-test"
    config["shotgun"]["api_key"] = "sg_full_test"
    config["selected_model"] = "gemini-2.5-pro"

    result = _apply_migrations(config)

    # Should have all v5 fields
    assert result["config_version"] == CURRENT_CONFIG_VERSION
    assert result["shotgun_instance_id"] == "test-user-id-12345"  # v2->v3
    assert "user_id" not in result  # v2->v3
    assert result["marketing"] == {"messages": {}}  # v3->v4
    assert result["shown_welcome_screen"] is False  # v3->v4 (has BYOK)
    assert result["openai"]["supports_streaming"] is None  # v4->v5

    # All user data preserved
    assert result["openai"]["api_key"] == "sk-proj-full-test"
    assert result["anthropic"]["api_key"] == "sk-ant-full-test"
    assert result["google"]["api_key"] == "AIza-full-test"
    assert result["shotgun"]["api_key"] == "sg_full_test"
    assert result["selected_model"] == "gemini-2.5-pro"


def test_apply_migrations_v3_to_current_with_partial_config():
    """Test v3->v5 migration with only some providers configured."""
    config = V3_CONFIG.copy()
    config["openai"]["api_key"] = None
    config["anthropic"]["api_key"] = "sk-ant-only"
    config["google"]["api_key"] = None
    config["shotgun"]["api_key"] = None
    config["selected_model"] = "claude-haiku-4-5"

    result = _apply_migrations(config)

    assert result["config_version"] == CURRENT_CONFIG_VERSION
    assert result["shotgun_instance_id"] == "test-user-id-12345"
    assert result["anthropic"]["api_key"] == "sk-ant-only"
    assert result["selected_model"] == "claude-haiku-4-5"
    assert result["shown_welcome_screen"] is False  # Has BYOK key
    assert result["marketing"]["messages"] == {}


def test_migration_preserves_instance_id_consistency():
    """Test that shotgun_instance_id remains consistent across all migrations."""
    original_instance_id = "consistent-id-abc-123-xyz"

    # Start with v2
    v2_config = V2_CONFIG.copy()
    v2_config["user_id"] = original_instance_id

    # Migrate to current
    result = _apply_migrations(v2_config)

    # Instance ID should be preserved through the rename
    assert result["shotgun_instance_id"] == original_instance_id
    assert "user_id" not in result


def test_create_backup_success():
    """Test that backup creation works correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"

        # Create a test config file
        test_config = {"test": "data", "config_version": 4}
        config_path.write_text(json.dumps(test_config))

        # Create backup
        backup_path = _create_backup(config_path)

        # Verify backup was created in backup subdirectory
        assert backup_path.exists()
        assert backup_path.parent == config_path.parent / "backup"
        assert backup_path.name.startswith("config.backup.")
        assert backup_path.name.endswith(".json")

        # Verify backup content matches original
        backup_data = json.loads(backup_path.read_text())
        assert backup_data == test_config


def test_create_backup_nonexistent_file():
    """Test that backup creation fails gracefully for nonexistent files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "nonexistent.json"

        # Should raise IOError when trying to backup nonexistent file
        with pytest.raises(IOError, match="Failed to create config backup"):
            _create_backup(config_path)


@pytest.mark.asyncio
async def test_load_with_corrupted_json():
    """Test that loading corrupted JSON auto-recovers with fresh config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"

        # Write invalid JSON
        config_path.write_text("{invalid json this is not valid")

        manager = ConfigManager(config_path=config_path)

        # Should auto-recover by creating fresh config
        config = await manager.load()

        # Verify fresh config was created with migration failure flag
        assert isinstance(config, ShotgunConfig)
        assert config.migration_failed is True
        assert config.migration_backup_path is not None

        # Verify backup was created
        backup_dir = Path(tmpdir) / "backup"
        assert backup_dir.exists()
        backup_files = list(backup_dir.glob("config.backup.*.json"))
        assert len(backup_files) == 1


@pytest.mark.asyncio
async def test_load_with_migration_failure():
    """Test that migration failures auto-recover with fresh config and backup."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"

        # Create a config with invalid field type that will cause validation to fail
        bad_config = {
            "config_version": 2,
            "user_id": "test-id",
            "openai": "this should be a dict, not a string",  # Invalid type
            "anthropic": {"api_key": None},
            "google": {"api_key": None},
            "shotgun": {"api_key": None},
        }
        config_path.write_text(json.dumps(bad_config))

        manager = ConfigManager(config_path=config_path)

        # Should auto-recover by creating fresh config
        config = await manager.load()

        # Verify fresh config was created with migration failure flag
        assert isinstance(config, ShotgunConfig)
        assert config.migration_failed is True
        assert config.migration_backup_path is not None

        # Verify backup was created
        backup_dir = Path(tmpdir) / "backup"
        assert backup_dir.exists()
        backup_files = list(backup_dir.glob("config.backup.*.json"))
        assert len(backup_files) == 1


@pytest.mark.asyncio
async def test_load_creates_backup_only_when_migration_needed():
    """Test that backup is only created when migration is actually needed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"

        # Create a current version config (no migration needed)
        current_config = V5_CONFIG.copy()
        config_path.write_text(json.dumps(current_config))

        manager = ConfigManager(config_path=config_path)

        # Load config
        config = await manager.load()

        # Verify no backup directory was created (no migration needed)
        backup_dir = Path(tmpdir) / "backup"
        assert not backup_dir.exists()
        assert config.config_version == CURRENT_CONFIG_VERSION


@pytest.mark.asyncio
async def test_load_creates_backup_when_migration_needed():
    """Test that backup is created when config needs migration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"

        # Create an old version config (migration needed)
        old_config = V2_CONFIG.copy()
        config_path.write_text(json.dumps(old_config))

        manager = ConfigManager(config_path=config_path)

        # Load config (should succeed and create backup)
        config = await manager.load()

        # Verify backup was created in backup subdirectory
        backup_dir = Path(tmpdir) / "backup"
        assert backup_dir.exists()
        backup_files = list(backup_dir.glob("config.backup.*.json"))
        assert len(backup_files) == 1

        # Verify backup contains original v2 config
        backup_data = json.loads(backup_files[0].read_text())
        assert backup_data["config_version"] == 2
        assert "user_id" in backup_data

        # Verify loaded config is migrated
        assert config.config_version == CURRENT_CONFIG_VERSION
        assert config.shotgun_instance_id == old_config["user_id"]


@pytest.mark.asyncio
async def test_migration_failed_flag_cleared_after_provider_config():
    """Test that migration_failed flag is cleared when user configures a provider."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"

        # Write config that will fail validation
        bad_config = {
            "config_version": 2,
            "user_id": "test-id",
            "openai": "invalid string instead of dict",
            "anthropic": {"api_key": None},
            "google": {"api_key": None},
            "shotgun": {"api_key": None},
        }
        config_path.write_text(json.dumps(bad_config))

        manager = ConfigManager(config_path=config_path)

        # Load should auto-recover
        config = await manager.load()
        assert config.migration_failed is True
        assert config.migration_backup_path is not None

        # Configure a provider
        await manager.update_provider(ProviderType.OPENAI, api_key="test-key")

        # Reload and verify flag is cleared
        config = await manager.load(force_reload=True)
        assert config.migration_failed is False
        assert config.migration_backup_path is None
