"""Tests for MCP CLI commands."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from shotgun.agents.config.manager import ConfigManager
from shotgun.cli.mcp import app

runner = CliRunner()


@pytest.fixture()
def config_path(tmp_path: Path) -> Path:
    """Create a temporary config file."""
    config_path = tmp_path / "config.json"
    config_data = {
        "config_version": 13,
        "shotgun_instance_id": "test-id",
        "mcp_servers": [],
    }
    config_path.write_text(json.dumps(config_data))
    return config_path


@pytest.fixture()
def mock_config_manager(config_path: Path):
    """Patch get_config_manager to use temp config."""
    cm = ConfigManager(config_path=config_path)
    with patch("shotgun.cli.mcp.get_config_manager", return_value=cm):
        yield cm


def test_mcp_list_empty(mock_config_manager: ConfigManager):
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "No MCP servers configured" in result.output


def test_mcp_add_stdio(mock_config_manager: ConfigManager):
    result = runner.invoke(
        app, ["add", "test-server", "--command", "echo", "--args", "hello"]
    )
    assert result.exit_code == 0
    assert "Added MCP server 'test-server'" in result.output
    assert "experimental" in result.output.lower()


def test_mcp_add_http(mock_config_manager: ConfigManager):
    result = runner.invoke(
        app, ["add", "web-server", "--url", "https://example.com/mcp"]
    )
    assert result.exit_code == 0
    assert "Added MCP server 'web-server'" in result.output


def test_mcp_add_with_env(mock_config_manager: ConfigManager):
    result = runner.invoke(
        app,
        [
            "add",
            "env-server",
            "--command",
            "my-cmd",
            "--env",
            "KEY=value",
            "--env",
            "OTHER=val2",
        ],
    )
    assert result.exit_code == 0
    assert "Added MCP server 'env-server'" in result.output


def test_mcp_add_with_headers(mock_config_manager: ConfigManager):
    result = runner.invoke(
        app,
        [
            "add",
            "auth-server",
            "--url",
            "https://example.com/mcp",
            "--header",
            "Authorization=Bearer token",
        ],
    )
    assert result.exit_code == 0
    assert "Added MCP server 'auth-server'" in result.output


def test_mcp_add_both_command_and_url(mock_config_manager: ConfigManager):
    result = runner.invoke(
        app,
        ["add", "bad", "--command", "echo", "--url", "https://example.com"],
    )
    assert result.exit_code == 1
    assert "Cannot specify both" in result.output


def test_mcp_add_neither_command_nor_url(mock_config_manager: ConfigManager):
    result = runner.invoke(app, ["add", "bad"])
    assert result.exit_code == 1
    assert "Must specify either" in result.output


def test_mcp_add_duplicate(mock_config_manager: ConfigManager):
    # Add first
    runner.invoke(app, ["add", "dup", "--command", "echo"])
    # Try to add duplicate
    result = runner.invoke(app, ["add", "dup", "--command", "other"])
    assert result.exit_code == 1
    assert "already exists" in result.output


def test_mcp_add_invalid_env_format(mock_config_manager: ConfigManager):
    result = runner.invoke(
        app, ["add", "bad-env", "--command", "echo", "--env", "NOEQUALS"]
    )
    assert result.exit_code == 1
    assert "Invalid env format" in result.output


def test_mcp_add_invalid_header_format(mock_config_manager: ConfigManager):
    result = runner.invoke(
        app,
        ["add", "bad-header", "--url", "https://example.com", "--header", "NOEQUALS"],
    )
    assert result.exit_code == 1
    assert "Invalid header format" in result.output


def test_mcp_list_with_servers(mock_config_manager: ConfigManager):
    runner.invoke(app, ["add", "stdio-srv", "--command", "echo", "--args", "hi"])
    runner.invoke(app, ["add", "http-srv", "--url", "https://example.com/mcp"])

    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "stdio-srv" in result.output
    assert "http-srv" in result.output
    assert "stdio" in result.output
    assert "http" in result.output


def test_mcp_remove(mock_config_manager: ConfigManager):
    runner.invoke(app, ["add", "to-remove", "--command", "echo"])

    result = runner.invoke(app, ["remove", "to-remove"])
    assert result.exit_code == 0
    assert "Removed MCP server 'to-remove'" in result.output

    # Verify it's gone
    result = runner.invoke(app, ["list"])
    assert "to-remove" not in result.output


def test_mcp_remove_nonexistent(mock_config_manager: ConfigManager):
    result = runner.invoke(app, ["remove", "ghost"])
    assert result.exit_code == 1
    assert "not found" in result.output
