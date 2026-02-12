"""Tests for the simplified update_checker module."""

import sys
from unittest.mock import Mock, patch

from shotgun.utils.update_checker import (
    UpdateInfo,
    check_for_update,
    compare_versions,
    detect_installation_method,
    get_latest_version,
    get_update_command,
    get_upgrade_hint,
    is_dev_version,
    perform_auto_update,
    perform_auto_update_async,
    perform_update,
)


def test_is_dev_version(monkeypatch):
    """Test development version detection."""
    assert is_dev_version("0.1.0.dev1") is True
    assert is_dev_version("0.1.0") is False
    assert is_dev_version("1.0.0-dev") is True
    assert is_dev_version("1.0.0") is False

    # Test with current version
    monkeypatch.setattr("shotgun.utils.update_checker.__version__", "0.1.0.dev1")
    assert is_dev_version() is True


def test_compare_versions():
    """Test version comparison."""
    assert compare_versions("0.1.0", "0.2.0") is True
    assert compare_versions("0.2.0", "0.1.0") is False
    assert compare_versions("1.0.0", "1.0.0") is False
    assert compare_versions("0.9.9", "0.10.0") is True
    assert compare_versions("1.0.0", "1.0.1") is True

    # Test with invalid versions
    assert compare_versions("invalid", "1.0.0") is False


@patch("shotgun.utils.update_checker.httpx.Client")
def test_get_latest_version_success(mock_client):
    """Test successful fetching of latest version."""
    mock_response = Mock()
    mock_response.json.return_value = {"info": {"version": "0.2.0"}}
    mock_response.raise_for_status = Mock()

    mock_client_instance = Mock()
    mock_client_instance.get.return_value = mock_response
    mock_client.return_value.__enter__.return_value = mock_client_instance

    result = get_latest_version()
    assert result == "0.2.0"


@patch("shotgun.utils.update_checker.httpx.Client")
def test_get_latest_version_network_error(mock_client):
    """Test fetching latest version with network error."""
    import httpx

    mock_client_instance = Mock()
    mock_client_instance.get.side_effect = httpx.RequestError("Network error")
    mock_client.return_value.__enter__.return_value = mock_client_instance

    result = get_latest_version()
    assert result is None


@patch("shotgun.utils.update_checker.subprocess.run")
@patch("shotgun.utils.update_checker.Path")
def test_detect_installation_method_uvx(mock_path, mock_run):
    """Test detection of uvx (ephemeral) execution."""
    # Mock executable path to look like uvx cache
    mock_executable = Mock()
    mock_executable.__str__ = (
        lambda x: "/home/user/.cache/uv/tools/shotgun-sh/bin/python"
    )
    mock_path.return_value = mock_executable

    result = detect_installation_method()
    assert result == "uvx"


@patch("shotgun.utils.update_checker.subprocess.run")
@patch("shotgun.utils.update_checker.Path")
def test_detect_installation_method_uv_tool(mock_path, mock_run):
    """Test detection of uv tool installation."""
    # Mock executable path to not match uvx cache
    mock_executable = Mock()
    mock_executable.__str__ = lambda x: "/home/user/.local/bin/python"
    mock_path.return_value = mock_executable

    # Mock uv tool list success
    def run_side_effect(cmd, **kwargs):
        if cmd[0] == "uv" and cmd[1] == "tool":
            return Mock(stdout="shotgun-sh 0.1.0", returncode=0)
        raise FileNotFoundError()

    mock_run.side_effect = run_side_effect

    result = detect_installation_method()
    assert result == "uv-tool"


@patch("shotgun.utils.update_checker.subprocess.run")
@patch("shotgun.utils.update_checker.Path")
def test_detect_installation_method_pipx(mock_path, mock_run):
    """Test detection of pipx installation."""
    # Mock executable path to not match uvx cache
    mock_executable = Mock()
    mock_executable.__str__ = lambda x: "/usr/bin/python"
    mock_path.return_value = mock_executable

    # Mock subprocess calls
    def run_side_effect(cmd, **kwargs):
        if cmd[0] == "uv":
            raise FileNotFoundError()
        if cmd[0] == "pipx":
            return Mock(stdout="shotgun-sh 0.1.0", returncode=0)
        raise FileNotFoundError()

    mock_run.side_effect = run_side_effect

    result = detect_installation_method()
    assert result == "pipx"


@patch("shotgun.utils.update_checker.subprocess.run")
def test_detect_installation_method_venv(mock_run, monkeypatch):
    """Test detection of virtual environment installation."""
    mock_run.side_effect = FileNotFoundError()

    # Mock virtual environment
    monkeypatch.setattr(sys, "base_prefix", "/usr")
    monkeypatch.setattr(sys, "prefix", "/home/user/venv")

    result = detect_installation_method()
    assert result == "venv"


def test_get_update_command():
    """Test getting update commands for different installation methods."""
    uvx_cmd = get_update_command("uvx")
    assert uvx_cmd is None  # No update command for ephemeral

    uv_tool_cmd = get_update_command("uv-tool")
    assert uv_tool_cmd == ["uv", "tool", "upgrade", "shotgun-sh"]

    pipx_cmd = get_update_command("pipx")
    assert pipx_cmd == ["pipx", "upgrade", "shotgun-sh"]

    pip_cmd = get_update_command("pip")
    assert pip_cmd == [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "shotgun-sh",
    ]

    venv_cmd = get_update_command("venv")
    assert venv_cmd == [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "shotgun-sh",
    ]


def test_perform_update_dev_version_no_force(monkeypatch):
    """Test update rejection for dev version without force."""
    monkeypatch.setattr("shotgun.utils.update_checker.__version__", "0.1.0.dev1")

    success, message = perform_update()
    assert success is False
    assert "Cannot update development version" in message


@patch("shotgun.utils.update_checker.subprocess.run")
@patch("shotgun.utils.update_checker.detect_installation_method")
@patch("shotgun.utils.update_checker.get_latest_version")
def test_perform_update_success(mock_get_latest, mock_detect, mock_run, monkeypatch):
    """Test successful update."""
    monkeypatch.setattr("shotgun.utils.update_checker.__version__", "0.1.0")
    mock_get_latest.return_value = "0.2.0"
    mock_detect.return_value = "pipx"

    # Mock successful update
    mock_run.return_value = Mock(
        returncode=0, stdout="Successfully upgraded", stderr=""
    )

    success, message = perform_update()
    assert success is True
    assert "Successfully updated from 0.1.0 to 0.2.0" in message


@patch("shotgun.utils.update_checker.subprocess.run")
@patch("shotgun.utils.update_checker.detect_installation_method")
def test_perform_auto_update_uv_tool(mock_detect, mock_run):
    """Test auto-update for uv tool installation."""
    mock_detect.return_value = "uv-tool"
    mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

    perform_auto_update(no_update_check=False)

    # Should have called uv tool upgrade
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args == ["uv", "tool", "upgrade", "shotgun-sh"]


@patch("shotgun.utils.update_checker.subprocess.run")
@patch("shotgun.utils.update_checker.detect_installation_method")
def test_perform_auto_update_pipx(mock_detect, mock_run):
    """Test auto-update for pipx installation."""
    mock_detect.return_value = "pipx"
    mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

    perform_auto_update(no_update_check=False)

    # Should have called pipx upgrade
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args == ["pipx", "upgrade", "shotgun-sh", "--quiet"]


@patch("shotgun.utils.update_checker.detect_installation_method")
def test_perform_auto_update_uvx_skips(mock_detect):
    """Test auto-update skips for uvx (ephemeral) installations."""
    mock_detect.return_value = "uvx"

    # Should not attempt update
    with patch("shotgun.utils.update_checker.subprocess.run") as mock_run:
        perform_auto_update(no_update_check=False)
        mock_run.assert_not_called()


@patch("shotgun.utils.update_checker.detect_installation_method")
def test_perform_auto_update_not_pipx(mock_detect):
    """Test auto-update skips for non-pipx installations."""
    mock_detect.return_value = "pip"

    # Should not attempt update
    with patch("shotgun.utils.update_checker.subprocess.run") as mock_run:
        perform_auto_update(no_update_check=False)
        mock_run.assert_not_called()


@patch("shotgun.utils.update_checker.detect_installation_method")
@patch("shotgun.utils.update_checker.get_latest_version")
def test_perform_update_uvx_shows_message(mock_get_latest, mock_detect, monkeypatch):
    """Test that uvx installations get a helpful message instead of update."""
    monkeypatch.setattr("shotgun.utils.update_checker.__version__", "0.1.0")
    mock_get_latest.return_value = "0.2.0"
    mock_detect.return_value = "uvx"

    success, message = perform_update()
    assert success is False
    assert "ephemeral mode" in message
    assert "uvx shotgun-sh" in message
    assert "uv tool install shotgun-sh" in message


def test_perform_auto_update_async():
    """Test async update starts a thread."""
    with patch("shotgun.utils.update_checker.perform_auto_update") as mock_update:
        thread = perform_auto_update_async(no_update_check=False)
        thread.join(timeout=1)
        mock_update.assert_called_once_with(False)


def test_get_upgrade_hint():
    """Test upgrade hints for different installation methods."""
    # uvx only shows uvx command
    assert "uvx shotgun-sh@latest" in get_upgrade_hint("uvx")

    # All other methods show their specific command AND uvx suggestion
    uv_tool_hint = get_upgrade_hint("uv-tool")
    assert "uv tool upgrade shotgun-sh" in uv_tool_hint
    assert "uvx shotgun-sh@latest" in uv_tool_hint

    pipx_hint = get_upgrade_hint("pipx")
    assert "pipx upgrade shotgun-sh" in pipx_hint
    assert "uvx shotgun-sh@latest" in pipx_hint

    pip_hint = get_upgrade_hint("pip")
    assert "pip install --upgrade shotgun-sh" in pip_hint
    assert "uvx shotgun-sh@latest" in pip_hint

    venv_hint = get_upgrade_hint("venv")
    assert "pip install --upgrade shotgun-sh" in venv_hint
    assert "uvx shotgun-sh@latest" in venv_hint

    unknown_hint = get_upgrade_hint("unknown")
    assert "pip install --upgrade shotgun-sh" in unknown_hint
    assert "uvx shotgun-sh@latest" in unknown_hint


def test_check_for_update_returns_none_for_dev_version(monkeypatch):
    """Test check_for_update returns None for dev versions."""
    monkeypatch.setattr("shotgun.utils.update_checker.__version__", "0.1.0.dev1")

    result = check_for_update()
    assert result is None


@patch("shotgun.utils.update_checker.get_latest_version")
def test_check_for_update_returns_none_on_network_failure(mock_get_latest, monkeypatch):
    """Test check_for_update returns None on network failure."""
    monkeypatch.setattr("shotgun.utils.update_checker.__version__", "0.1.0")
    mock_get_latest.return_value = None

    result = check_for_update()
    assert result is None


@patch("shotgun.utils.update_checker.detect_installation_method")
@patch("shotgun.utils.update_checker.get_latest_version")
def test_check_for_update_returns_update_info_when_available(
    mock_get_latest, mock_detect, monkeypatch
):
    """Test check_for_update returns UpdateInfo when update available."""
    monkeypatch.setattr("shotgun.utils.update_checker.__version__", "0.1.0")
    mock_get_latest.return_value = "0.2.0"
    mock_detect.return_value = "pipx"

    result = check_for_update()

    assert result is not None
    assert isinstance(result, UpdateInfo)
    assert result.current_version == "0.1.0"
    assert result.latest_version == "0.2.0"
    assert result.update_available is True
    assert result.installation_method == "pipx"
    assert result.upgrade_command == ["pipx", "upgrade", "shotgun-sh"]
    assert "pipx upgrade" in result.upgrade_hint


@patch("shotgun.utils.update_checker.detect_installation_method")
@patch("shotgun.utils.update_checker.get_latest_version")
def test_check_for_update_returns_update_info_no_update_needed(
    mock_get_latest, mock_detect, monkeypatch
):
    """Test check_for_update returns UpdateInfo with update_available=False when current."""
    monkeypatch.setattr("shotgun.utils.update_checker.__version__", "0.2.0")
    mock_get_latest.return_value = "0.2.0"
    mock_detect.return_value = "pipx"

    result = check_for_update()

    assert result is not None
    assert isinstance(result, UpdateInfo)
    assert result.current_version == "0.2.0"
    assert result.latest_version == "0.2.0"
    assert result.update_available is False


@patch("shotgun.utils.update_checker.detect_installation_method")
@patch("shotgun.utils.update_checker.get_latest_version")
def test_check_for_update_uvx_has_no_upgrade_command(
    mock_get_latest, mock_detect, monkeypatch
):
    """Test check_for_update for uvx has None upgrade_command."""
    monkeypatch.setattr("shotgun.utils.update_checker.__version__", "0.1.0")
    mock_get_latest.return_value = "0.2.0"
    mock_detect.return_value = "uvx"

    result = check_for_update()

    assert result is not None
    assert result.upgrade_command is None
    assert "uvx shotgun-sh@latest" in result.upgrade_hint


@patch("shotgun.utils.update_checker.detect_installation_method")
@patch("shotgun.utils.update_checker.get_latest_version")
def test_check_for_update_respects_version_override(
    mock_get_latest, mock_detect, monkeypatch
):
    """Test check_for_update uses SHOTGUN_VERSION_OVERRIDE setting."""
    # Set the actual version to latest (no update needed)
    monkeypatch.setattr("shotgun.utils.update_checker.__version__", "0.2.0")
    mock_get_latest.return_value = "0.2.0"
    mock_detect.return_value = "pipx"

    # Override version to an older version to simulate update available
    monkeypatch.setattr(
        "shotgun.utils.update_checker.settings.dev.version_override", "0.1.0"
    )

    result = check_for_update()

    assert result is not None
    assert result.current_version == "0.1.0"  # Uses override
    assert result.latest_version == "0.2.0"
    assert result.update_available is True


@patch("shotgun.utils.update_checker.detect_installation_method")
@patch("shotgun.utils.update_checker.get_latest_version")
def test_check_for_update_respects_install_method_override(
    mock_get_latest, mock_detect, monkeypatch
):
    """Test check_for_update uses SHOTGUN_INSTALL_METHOD_OVERRIDE setting."""
    monkeypatch.setattr("shotgun.utils.update_checker.__version__", "0.1.0")
    mock_get_latest.return_value = "0.2.0"
    mock_detect.return_value = "pip"  # Would normally detect pip

    # Override installation method to test different hints
    monkeypatch.setattr(
        "shotgun.utils.update_checker.settings.dev.install_method_override", "uvx"
    )

    result = check_for_update()

    assert result is not None
    assert result.installation_method == "uvx"  # Uses override
    assert result.upgrade_command is None  # uvx has no upgrade command
    assert "uvx shotgun-sh@latest" in result.upgrade_hint
    # Verify detect_installation_method was not called (we used override)
    mock_detect.assert_not_called()
