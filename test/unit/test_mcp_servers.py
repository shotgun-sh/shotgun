"""Tests for MCP server configuration and loading."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from shotgun.agents.config.manager import (
    ConfigManager,
    _migrate_v12_to_v13,
)
from shotgun.agents.config.models import (
    MCPServerEntry,
    MCPTransport,
)
from shotgun.agents.tools.mcp_servers import _create_mcp_server, get_user_mcp_servers


def test_mcp_transport_enum():
    assert MCPTransport.STDIO == "stdio"
    assert MCPTransport.HTTP == "http"


def test_mcp_server_entry_stdio():
    entry = MCPServerEntry(
        name="test-server",
        transport=MCPTransport.STDIO,
        command="echo",
        args=["hello", "world"],
        env={"FOO": "bar"},
    )
    assert entry.name == "test-server"
    assert entry.transport == MCPTransport.STDIO
    assert entry.command == "echo"
    assert entry.args == ["hello", "world"]
    assert entry.env == {"FOO": "bar"}
    assert entry.url is None
    assert entry.headers == {}


def test_mcp_server_entry_http():
    entry = MCPServerEntry(
        name="docs-server",
        transport=MCPTransport.HTTP,
        url="https://example.com/mcp",
        headers={"Authorization": "Bearer token123"},
    )
    assert entry.name == "docs-server"
    assert entry.transport == MCPTransport.HTTP
    assert entry.url == "https://example.com/mcp"
    assert entry.headers == {"Authorization": "Bearer token123"}
    assert entry.command is None
    assert entry.args == []


def test_mcp_server_entry_defaults():
    entry = MCPServerEntry(
        name="minimal",
        transport=MCPTransport.STDIO,
        command="my-server",
    )
    assert entry.args == []
    assert entry.env == {}
    assert entry.url is None
    assert entry.headers == {}


def test_create_mcp_server_stdio():
    entry = MCPServerEntry(
        name="test",
        transport=MCPTransport.STDIO,
        command="echo",
        args=["hello"],
    )
    server = _create_mcp_server(entry)
    assert server.tool_prefix == "test"


def test_create_mcp_server_http():
    entry = MCPServerEntry(
        name="web",
        transport=MCPTransport.HTTP,
        url="https://example.com/mcp",
    )
    server = _create_mcp_server(entry)
    assert server.tool_prefix == "web"


def test_create_mcp_server_stdio_no_command():
    entry = MCPServerEntry(
        name="broken",
        transport=MCPTransport.STDIO,
    )
    with pytest.raises(ValueError, match="no command"):
        _create_mcp_server(entry)


def test_create_mcp_server_http_no_url():
    entry = MCPServerEntry(
        name="broken",
        transport=MCPTransport.HTTP,
    )
    with pytest.raises(ValueError, match="no url"):
        _create_mcp_server(entry)


def test_migrate_v12_to_v13():
    data = {"config_version": 12}
    result = _migrate_v12_to_v13(data)
    assert result["config_version"] == 13
    assert result["mcp_servers"] == []


def test_migrate_v12_to_v13_preserves_existing():
    data = {
        "config_version": 12,
        "mcp_servers": [{"name": "existing", "transport": "stdio", "command": "test"}],
    }
    result = _migrate_v12_to_v13(data)
    assert result["config_version"] == 13
    assert len(result["mcp_servers"]) == 1


@pytest.mark.asyncio
async def test_get_user_mcp_servers_empty(tmp_path: Path):
    """Test loading MCP servers when none configured."""
    config_path = tmp_path / "config.json"
    config_data = {
        "config_version": 13,
        "shotgun_instance_id": "test-id",
        "mcp_servers": [],
    }
    config_path.write_text(json.dumps(config_data))

    with patch("shotgun.agents.tools.mcp_servers.get_config_manager") as mock_get_cm:
        cm = ConfigManager(config_path=config_path)
        mock_get_cm.return_value = cm
        servers = await get_user_mcp_servers()

    assert servers == []


@pytest.mark.asyncio
async def test_get_user_mcp_servers_with_entries():
    """Test loading MCP servers with configured entries."""
    entries = [
        MCPServerEntry(
            name="test-stdio",
            transport=MCPTransport.STDIO,
            command="echo",
            args=["hello"],
        ),
        MCPServerEntry(
            name="test-http",
            transport=MCPTransport.HTTP,
            url="https://example.com/mcp",
        ),
    ]

    mock_cm = AsyncMock()
    mock_cm.get_mcp_servers = AsyncMock(return_value=entries)

    with patch(
        "shotgun.agents.tools.mcp_servers.get_config_manager", return_value=mock_cm
    ):
        servers = await get_user_mcp_servers()

    assert len(servers) == 2
    assert servers[0].tool_prefix == "test-stdio"
    assert servers[1].tool_prefix == "test-http"


@pytest.mark.asyncio
async def test_get_user_mcp_servers_skips_invalid():
    """Test that invalid MCP server entries are skipped with warning."""
    entries = [
        MCPServerEntry(
            name="broken",
            transport=MCPTransport.STDIO,
            # missing command
        ),
        MCPServerEntry(
            name="good",
            transport=MCPTransport.STDIO,
            command="echo",
        ),
    ]

    mock_cm = AsyncMock()
    mock_cm.get_mcp_servers = AsyncMock(return_value=entries)

    with patch(
        "shotgun.agents.tools.mcp_servers.get_config_manager", return_value=mock_cm
    ):
        servers = await get_user_mcp_servers()

    assert len(servers) == 1
    assert servers[0].tool_prefix == "good"


@pytest.mark.asyncio
async def test_config_manager_add_mcp_server(tmp_path: Path):
    """Test adding an MCP server via ConfigManager."""
    config_path = tmp_path / "config.json"
    config_data = {
        "config_version": 13,
        "shotgun_instance_id": "test-id",
        "mcp_servers": [],
    }
    config_path.write_text(json.dumps(config_data))

    cm = ConfigManager(config_path=config_path)

    entry = MCPServerEntry(
        name="my-server",
        transport=MCPTransport.STDIO,
        command="my-cmd",
    )
    await cm.add_mcp_server(entry)

    # Reload and verify
    cm._config = None
    config = await cm.load()
    assert len(config.mcp_servers) == 1
    assert config.mcp_servers[0].name == "my-server"


@pytest.mark.asyncio
async def test_config_manager_add_duplicate_mcp_server(tmp_path: Path):
    """Test that adding a duplicate MCP server raises ValueError."""
    config_path = tmp_path / "config.json"
    config_data = {
        "config_version": 13,
        "shotgun_instance_id": "test-id",
        "mcp_servers": [{"name": "existing", "transport": "stdio", "command": "echo"}],
    }
    config_path.write_text(json.dumps(config_data))

    cm = ConfigManager(config_path=config_path)

    entry = MCPServerEntry(
        name="existing",
        transport=MCPTransport.STDIO,
        command="other-cmd",
    )
    with pytest.raises(ValueError, match="already exists"):
        await cm.add_mcp_server(entry)


@pytest.mark.asyncio
async def test_config_manager_remove_mcp_server(tmp_path: Path):
    """Test removing an MCP server via ConfigManager."""
    config_path = tmp_path / "config.json"
    config_data = {
        "config_version": 13,
        "shotgun_instance_id": "test-id",
        "mcp_servers": [
            {"name": "to-remove", "transport": "stdio", "command": "echo"},
            {"name": "keep", "transport": "http", "url": "https://example.com"},
        ],
    }
    config_path.write_text(json.dumps(config_data))

    cm = ConfigManager(config_path=config_path)
    removed = await cm.remove_mcp_server("to-remove")
    assert removed is True

    # Reload and verify
    cm._config = None
    config = await cm.load()
    assert len(config.mcp_servers) == 1
    assert config.mcp_servers[0].name == "keep"


@pytest.mark.asyncio
async def test_config_manager_remove_nonexistent_mcp_server(tmp_path: Path):
    """Test removing a non-existent MCP server returns False."""
    config_path = tmp_path / "config.json"
    config_data = {
        "config_version": 13,
        "shotgun_instance_id": "test-id",
        "mcp_servers": [],
    }
    config_path.write_text(json.dumps(config_data))

    cm = ConfigManager(config_path=config_path)
    removed = await cm.remove_mcp_server("nonexistent")
    assert removed is False
