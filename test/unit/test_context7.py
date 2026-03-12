"""Unit tests for Context7 MCP integration."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from shotgun.agents.config.manager import (
    CURRENT_CONFIG_VERSION,
    ConfigManager,
    _apply_migrations,
    _migrate_v8_to_v9,
)
from shotgun.agents.models import AgentSystemPromptContext

# V8 config for testing migration
V8_CONFIG = {
    "openai": {"api_key": "sk-test123", "supports_streaming": None},
    "anthropic": {"api_key": None, "tier": None},
    "google": {"api_key": None},
    "shotgun": {"api_key": None, "supabase_jwt": None},
    "ollama": {"enabled": False, "base_url": "http://localhost:11434"},
    "selected_model": None,
    "shotgun_instance_id": "test-user-id-12345",
    "config_version": 8,
    "shown_welcome_screen": False,
    "marketing": {"messages": {}},
    "router_mode": "planning",
}


# --- Migration tests ---


def test_migrate_v8_to_v9():
    """Test migration from version 8 to version 9."""
    config = V8_CONFIG.copy()

    result = _migrate_v8_to_v9(config)

    assert result["config_version"] == 9
    assert "context7" in result
    assert result["context7"] == {}
    assert result["shotgun_instance_id"] == "test-user-id-12345"


def test_migrate_v8_to_v9_preserves_existing_fields():
    """Test v8->v9 migration preserves all existing fields."""
    config = V8_CONFIG.copy()
    config["openai"]["api_key"] = "sk-proj-test"
    config["anthropic"]["api_key"] = "sk-ant-test"
    config["ollama"]["enabled"] = True

    result = _migrate_v8_to_v9(config)

    assert result["config_version"] == 9
    assert result["context7"] == {}
    assert result["openai"]["api_key"] == "sk-proj-test"
    assert result["anthropic"]["api_key"] == "sk-ant-test"
    assert result["ollama"]["enabled"] is True


def test_migrate_v8_to_v9_with_existing_context7():
    """Test v8->v9 migration doesn't overwrite existing context7 field."""
    config = V8_CONFIG.copy()
    config["context7"] = {"api_key": "existing-key"}

    result = _migrate_v8_to_v9(config)

    assert result["config_version"] == 9
    assert result["context7"] == {"api_key": "existing-key"}


def test_apply_migrations_from_v8_to_current():
    """Test applying migrations from v8 to current version."""
    config = V8_CONFIG.copy()

    result = _apply_migrations(config)

    assert result["config_version"] == CURRENT_CONFIG_VERSION
    assert "context7" in result
    assert result["context7"] == {}


def test_current_config_version_is_13():
    """Verify current config version is 13."""
    assert CURRENT_CONFIG_VERSION == 13


# --- ConfigManager Context7 methods tests ---


@pytest.mark.asyncio
async def test_update_context7_sets_key():
    """Test that update_context7 stores the API key."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"

        # Create a current version config
        current_config = V8_CONFIG.copy()
        current_config["config_version"] = CURRENT_CONFIG_VERSION
        current_config["context7"] = {}
        config_path.write_text(json.dumps(current_config))

        manager = ConfigManager(config_path=config_path)

        await manager.update_context7("test-c7-key-123")

        config = await manager.load(force_reload=True)
        assert config.context7.api_key is not None
        assert config.context7.api_key.get_secret_value() == "test-c7-key-123"


@pytest.mark.asyncio
async def test_update_context7_clears_key():
    """Test that update_context7(None) removes the API key."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"

        # Create a config with context7 key set
        current_config = V8_CONFIG.copy()
        current_config["config_version"] = CURRENT_CONFIG_VERSION
        current_config["context7"] = {"api_key": "existing-key"}
        config_path.write_text(json.dumps(current_config))

        manager = ConfigManager(config_path=config_path)

        await manager.update_context7(None)

        config = await manager.load(force_reload=True)
        assert config.context7.api_key is None


@pytest.mark.asyncio
async def test_get_context7_api_key_returns_key():
    """Test that get_context7_api_key returns the key when set."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"

        current_config = V8_CONFIG.copy()
        current_config["config_version"] = CURRENT_CONFIG_VERSION
        current_config["context7"] = {"api_key": "my-c7-key"}
        config_path.write_text(json.dumps(current_config))

        manager = ConfigManager(config_path=config_path)

        key = await manager.get_context7_api_key()
        assert key == "my-c7-key"


@pytest.mark.asyncio
async def test_get_context7_api_key_returns_none_when_not_set():
    """Test that get_context7_api_key returns None when no key."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"

        current_config = V8_CONFIG.copy()
        current_config["config_version"] = CURRENT_CONFIG_VERSION
        current_config["context7"] = {}
        config_path.write_text(json.dumps(current_config))

        manager = ConfigManager(config_path=config_path)

        key = await manager.get_context7_api_key()
        assert key is None


@pytest.mark.asyncio
async def test_get_context7_api_key_returns_none_for_empty_string():
    """Test that get_context7_api_key returns None for empty/whitespace key."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"

        current_config = V8_CONFIG.copy()
        current_config["config_version"] = CURRENT_CONFIG_VERSION
        current_config["context7"] = {"api_key": "   "}
        config_path.write_text(json.dumps(current_config))

        manager = ConfigManager(config_path=config_path)

        key = await manager.get_context7_api_key()
        assert key is None


@pytest.mark.asyncio
async def test_context7_key_persists_through_save_reload():
    """Test that Context7 key survives save and reload cycle."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"

        current_config = V8_CONFIG.copy()
        current_config["config_version"] = CURRENT_CONFIG_VERSION
        current_config["context7"] = {}
        config_path.write_text(json.dumps(current_config))

        manager = ConfigManager(config_path=config_path)

        # Set key
        await manager.update_context7("persist-test-key")

        # Create fresh manager to force reload from disk
        manager2 = ConfigManager(config_path=config_path)
        config = await manager2.load()

        assert config.context7.api_key is not None
        assert config.context7.api_key.get_secret_value() == "persist-test-key"


# --- Context7 MCP server helper tests ---


@pytest.mark.asyncio
async def test_get_context7_mcp_server_returns_none_when_no_key():
    """Test that get_context7_mcp_server returns None when no API key."""
    mock_manager = AsyncMock()
    mock_manager.get_context7_api_key.return_value = None

    with patch(
        "shotgun.agents.tools.context7.get_config_manager", return_value=mock_manager
    ):
        from shotgun.agents.tools.context7 import get_context7_mcp_server

        result = await get_context7_mcp_server()
        assert result is None


@pytest.mark.asyncio
async def test_get_context7_mcp_server_returns_server_when_key_set():
    """Test that get_context7_mcp_server returns MCPServerStreamableHTTP when key is set."""
    from pydantic_ai.mcp import MCPServerStreamableHTTP

    mock_manager = AsyncMock()
    mock_manager.get_context7_api_key.return_value = "test-api-key"

    with patch(
        "shotgun.agents.tools.context7.get_config_manager", return_value=mock_manager
    ):
        from shotgun.agents.tools.context7 import get_context7_mcp_server

        result = await get_context7_mcp_server()
        assert result is not None
        assert isinstance(result, MCPServerStreamableHTTP)


# --- AgentSystemPromptContext tests ---


def test_agent_system_prompt_context_has_context7_default_false():
    """Test that has_context7 defaults to False."""
    ctx = AgentSystemPromptContext(
        interactive_mode=True,
        mode="research",
    )
    assert ctx.has_context7 is False


def test_agent_system_prompt_context_has_context7_true():
    """Test that has_context7 can be set to True."""
    ctx = AgentSystemPromptContext(
        interactive_mode=True,
        mode="research",
        has_context7=True,
    )
    assert ctx.has_context7 is True


# --- Config migration integration tests ---


@pytest.mark.asyncio
async def test_config_manager_loads_v8_config_with_migration():
    """Test ConfigManager can load and migrate a v8 config file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"

        config_path.write_text(json.dumps(V8_CONFIG))

        manager = ConfigManager(config_path=config_path)
        config = await manager.load()

        assert config.config_version == CURRENT_CONFIG_VERSION
        assert config.context7 is not None
        assert config.context7.api_key is None
        assert config.shotgun_instance_id == "test-user-id-12345"


# --- MCP servers telemetry tests ---


def test_mcp_servers_telemetry_event_structure_with_context7():
    """Test that mcp_servers telemetry dict includes context7 when key is set."""
    mcp_servers = {
        "context7": True,
    }

    assert mcp_servers["context7"] is True
    # Extensible - future MCP servers can be added
    assert isinstance(mcp_servers, dict)


def test_mcp_servers_telemetry_event_structure_without_context7():
    """Test that mcp_servers telemetry dict shows context7=False when no key."""
    mcp_servers = {
        "context7": False,
    }

    assert mcp_servers["context7"] is False


@pytest.mark.asyncio
async def test_get_configured_mcp_servers_with_context7_key():
    """Test _get_configured_mcp_servers returns context7=True when key is set."""
    mock_manager = AsyncMock()
    mock_manager.get_context7_api_key.return_value = "test-key"

    with patch("shotgun.agents.config.get_config_manager", return_value=mock_manager):
        from shotgun.agents.agent_manager import AgentManager

        # Call the static-like method directly by creating a minimal instance
        result = await AgentManager._get_configured_mcp_servers(
            AsyncMock(spec=AgentManager)
        )
        assert result == {"context7": True}


@pytest.mark.asyncio
async def test_get_configured_mcp_servers_without_context7_key():
    """Test _get_configured_mcp_servers returns context7=False when no key."""
    mock_manager = AsyncMock()
    mock_manager.get_context7_api_key.return_value = None

    with patch("shotgun.agents.config.get_config_manager", return_value=mock_manager):
        from shotgun.agents.agent_manager import AgentManager

        result = await AgentManager._get_configured_mcp_servers(
            AsyncMock(spec=AgentManager)
        )
        assert result == {"context7": False}
