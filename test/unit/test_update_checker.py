"""Tests for the simplified update_checker module."""

import sys
from unittest.mock import Mock, patch

from shotgun.utils.update_checker import (
    compare_versions,
    detect_installation_method,
    get_latest_version,
    get_update_command,
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
def test_detect_installation_method_pipx(mock_run):
    """Test detection of pipx installation."""
    mock_run.return_value = Mock(stdout="shotgun-sh 0.1.0", returncode=0)

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
def test_perform_auto_update_not_pipx(mock_detect):
    """Test auto-update skips for non-pipx installations."""
    mock_detect.return_value = "pip"

    # Should not attempt update
    with patch("shotgun.utils.update_checker.subprocess.run") as mock_run:
        perform_auto_update(no_update_check=False)
        mock_run.assert_not_called()


def test_perform_auto_update_async():
    """Test async update starts a thread."""
    with patch("shotgun.utils.update_checker.perform_auto_update") as mock_update:
        thread = perform_auto_update_async(no_update_check=False)
        thread.join(timeout=1)
        mock_update.assert_called_once_with(False)
