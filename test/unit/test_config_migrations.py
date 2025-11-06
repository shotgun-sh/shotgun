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
    _migrate_v2_to_v3,
    _migrate_v3_to_v4,
    _migrate_v4_to_v5,
)


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
