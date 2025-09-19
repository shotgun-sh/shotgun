"""Unit tests for the update_checker module."""

import json
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch

import httpx

from shotgun.utils.update_checker import (
    UpdateCache,
    check_for_updates_async,
    check_for_updates_sync,
    compare_versions,
    detect_installation_method,
    format_update_notification,
    get_latest_version,
    get_update_command,
    is_dev_version,
    load_cache,
    perform_update,
    save_cache,
    should_check_for_updates,
)


def test_is_dev_version():
    """Test development version detection."""
    assert is_dev_version("0.1.0.dev2") is True
    assert is_dev_version("0.1.0.dev0") is True
    assert is_dev_version("1.0.0dev5") is True
    assert is_dev_version("1.0.0.DEV") is True
    assert is_dev_version("0.1.0") is False
    assert is_dev_version("1.0.0") is False
    assert is_dev_version("2.3.4rc1") is False


def test_compare_versions():
    """Test version comparison logic."""
    assert compare_versions("0.1.0", "0.2.0") is True
    assert compare_versions("0.2.0", "0.1.0") is False
    assert compare_versions("1.0.0", "1.0.0") is False
    assert compare_versions("1.0.0", "2.0.0") is True
    assert compare_versions("0.1.0.dev1", "0.1.0") is True
    assert compare_versions("1.0.0rc1", "1.0.0") is True


def test_format_update_notification():
    """Test update notification formatting."""
    result = format_update_notification("0.1.0", "0.2.0")
    assert result == "Update available: 0.1.0 → 0.2.0. Run 'shotgun update' to upgrade."


def test_load_cache_file_not_exists(tmp_path, monkeypatch):
    """Test loading cache when file doesn't exist."""
    monkeypatch.setenv("SHOTGUN_HOME", str(tmp_path))

    result = load_cache()
    assert result is None


def test_load_cache_valid_file(tmp_path, monkeypatch):
    """Test loading valid cache file."""
    monkeypatch.setenv("SHOTGUN_HOME", str(tmp_path))
    cache_file = tmp_path / "check-update.json"
    cache_data = {
        "last_check": "2024-01-15T10:30:00+00:00",
        "latest_version": "0.3.0",
        "current_version": "0.2.0",
        "update_available": True,
    }
    cache_file.write_text(json.dumps(cache_data))

    result = load_cache()
    assert result is not None
    assert result.latest_version == "0.3.0"
    assert result.current_version == "0.2.0"
    assert result.update_available is True


def test_load_cache_invalid_json(tmp_path, monkeypatch):
    """Test loading cache with invalid JSON."""
    monkeypatch.setenv("SHOTGUN_HOME", str(tmp_path))
    cache_file = tmp_path / "check-update.json"
    cache_file.write_text("not valid json{")

    result = load_cache()
    assert result is None


def test_save_cache(tmp_path, monkeypatch):
    """Test saving cache to disk."""
    from datetime import datetime, timezone

    monkeypatch.setenv("SHOTGUN_HOME", str(tmp_path))
    cache_file = tmp_path / "check-update.json"

    cache_data = UpdateCache(
        last_check=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        latest_version="0.3.0",
        current_version="0.2.0",
        update_available=True,
    )

    save_cache(cache_data)

    assert cache_file.exists()
    loaded = json.loads(cache_file.read_text())
    assert loaded["latest_version"] == "0.3.0"
    assert loaded["current_version"] == "0.2.0"
    assert loaded["update_available"] is True


def test_should_check_for_updates_no_update_check_flag():
    """Test that no_update_check flag prevents checking."""
    assert should_check_for_updates(no_update_check=True) is False


def test_should_check_for_updates_dev_version(monkeypatch):
    """Test that dev versions skip update checks."""
    monkeypatch.setattr("shotgun.utils.update_checker.__version__", "0.1.0.dev1")
    assert should_check_for_updates() is False


def test_should_check_for_updates_no_cache(tmp_path, monkeypatch):
    """Test update check when no cache exists."""
    monkeypatch.setattr("shotgun.utils.update_checker.__version__", "0.1.0")
    monkeypatch.setenv("SHOTGUN_HOME", str(tmp_path))

    assert should_check_for_updates() is True


def test_should_check_for_updates_cache_expired(tmp_path, monkeypatch):
    """Test update check when cache is expired."""
    monkeypatch.setattr("shotgun.utils.update_checker.__version__", "0.1.0")
    monkeypatch.setenv("SHOTGUN_HOME", str(tmp_path))
    cache_file = tmp_path / "check-update.json"

    # Create cache with old timestamp
    old_time = datetime.now(timezone.utc) - timedelta(hours=25)
    cache_data = {
        "last_check": old_time.isoformat(),
        "latest_version": "0.2.0",
        "current_version": "0.1.0",
        "update_available": True,
    }
    cache_file.write_text(json.dumps(cache_data))

    assert should_check_for_updates() is True


def test_should_check_for_updates_cache_fresh(tmp_path, monkeypatch):
    """Test update check when cache is fresh."""
    monkeypatch.setattr("shotgun.utils.update_checker.__version__", "0.1.0")
    monkeypatch.setenv("SHOTGUN_HOME", str(tmp_path))
    cache_file = tmp_path / "check-update.json"

    # Create cache with recent timestamp
    recent_time = datetime.now(timezone.utc) - timedelta(hours=1)
    cache_data = {
        "last_check": recent_time.isoformat(),
        "latest_version": "0.2.0",
        "current_version": "0.1.0",
        "update_available": True,
    }
    cache_file.write_text(json.dumps(cache_data))

    assert should_check_for_updates() is False


@patch("shotgun.utils.update_checker.httpx.Client")
def test_get_latest_version_success(mock_client_class):
    """Test successful fetching of latest version from PyPI."""
    mock_response = Mock()
    mock_response.json.return_value = {"info": {"version": "1.2.3"}}

    mock_client = Mock()
    mock_client.get.return_value = mock_response
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=None)

    mock_client_class.return_value = mock_client

    result = get_latest_version()
    assert result == "1.2.3"


@patch("shotgun.utils.update_checker.httpx.Client")
def test_get_latest_version_network_error(mock_client_class):
    """Test handling of network errors when fetching version."""
    mock_client = Mock()
    mock_client.get.side_effect = httpx.RequestError("Network error")
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=None)

    mock_client_class.return_value = mock_client

    result = get_latest_version()
    assert result is None


@patch("shotgun.utils.update_checker.httpx.Client")
def test_get_latest_version_invalid_json(mock_client_class):
    """Test handling of invalid JSON response."""
    mock_response = Mock()
    mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)

    mock_client = Mock()
    mock_client.get.return_value = mock_response
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=None)

    mock_client_class.return_value = mock_client

    result = get_latest_version()
    assert result is None


@patch("shotgun.utils.update_checker.subprocess.run")
def test_detect_installation_method_pipx(mock_run):
    """Test detection of pipx installation."""
    mock_run.return_value = Mock(stdout="shotgun-sh 0.1.0\n", returncode=0)
    result = detect_installation_method()
    assert result == "pipx"


@patch("shotgun.utils.update_checker.subprocess.run")
def test_detect_installation_method_venv(mock_run, monkeypatch):
    """Test detection of virtual environment installation."""
    mock_run.side_effect = FileNotFoundError()
    monkeypatch.setattr(sys, "base_prefix", "/usr")
    monkeypatch.setattr(sys, "prefix", "/home/user/venv")

    result = detect_installation_method()
    assert result == "venv"


@patch("shotgun.utils.update_checker.subprocess.run")
@patch("site.getusersitepackages")
def test_detect_installation_method_pip_user(
    mock_getusersitepackages, mock_run, tmp_path, monkeypatch
):
    """Test detection of pip --user installation."""
    # Mock subprocess to not find pipx
    mock_run.side_effect = FileNotFoundError()

    # Mock sys attributes to indicate NOT in a virtual environment
    monkeypatch.setattr(sys, "base_prefix", "/usr")
    monkeypatch.setattr(sys, "prefix", "/usr")

    # Create fake user site-packages with shotgun installed
    user_site = tmp_path / "site-packages"
    user_site.mkdir()
    (user_site / "shotgun_sh-0.1.0.dist-info").mkdir()

    mock_getusersitepackages.return_value = str(user_site)

    # Import and call the function
    from shotgun.utils.update_checker import detect_installation_method

    result = detect_installation_method()
    assert result == "pip"


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

    unknown_cmd = get_update_command("unknown")
    assert unknown_cmd == [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "shotgun-sh",
    ]


@patch("shotgun.utils.update_checker.get_latest_version")
def test_perform_update_dev_version_no_force(mock_get_latest, monkeypatch):
    """Test that dev versions cannot be updated without force flag."""
    monkeypatch.setattr("shotgun.utils.update_checker.__version__", "0.1.0.dev1")
    success, message = perform_update(force=False)
    assert success is False
    assert "development version" in message


@patch("shotgun.utils.update_checker.get_latest_version")
def test_perform_update_no_new_version(mock_get_latest, monkeypatch):
    """Test update when already at latest version."""
    monkeypatch.setattr("shotgun.utils.update_checker.__version__", "1.0.0")
    mock_get_latest.return_value = "1.0.0"

    success, message = perform_update()
    assert success is False
    assert "Already at latest version" in message


@patch("shotgun.utils.update_checker.subprocess.run")
@patch("shotgun.utils.update_checker.detect_installation_method")
@patch("shotgun.utils.update_checker.get_latest_version")
def test_perform_update_success(
    mock_get_latest, mock_detect, mock_run, monkeypatch, tmp_path
):
    """Test successful update."""
    monkeypatch.setattr("shotgun.utils.update_checker.__version__", "0.1.0")
    monkeypatch.setenv("SHOTGUN_HOME", str(tmp_path))
    cache_file = tmp_path / "check-update.json"
    mock_get_latest.return_value = "0.2.0"
    mock_detect.return_value = "pip"
    mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")

    success, message = perform_update()
    assert success is True
    assert "Successfully updated from 0.1.0 to 0.2.0" in message
    # Check that cache was cleared
    assert not cache_file.exists()


@patch("shotgun.utils.update_checker.subprocess.run")
@patch("shotgun.utils.update_checker.detect_installation_method")
@patch("shotgun.utils.update_checker.get_latest_version")
def test_perform_update_command_failure(
    mock_get_latest, mock_detect, mock_run, monkeypatch
):
    """Test update when command fails."""
    monkeypatch.setattr("shotgun.utils.update_checker.__version__", "0.1.0")
    mock_get_latest.return_value = "0.2.0"
    mock_detect.return_value = "pip"
    mock_run.return_value = Mock(returncode=1, stdout="", stderr="Error installing")

    success, message = perform_update()
    assert success is False
    assert "Update failed" in message


def test_check_for_updates_sync_skip_check(monkeypatch, tmp_path):
    """Test sync update check when checks are disabled."""
    monkeypatch.setattr("shotgun.utils.update_checker.__version__", "0.1.0.dev1")
    monkeypatch.setenv("SHOTGUN_HOME", str(tmp_path))
    result = check_for_updates_sync()
    assert result is None


@patch("shotgun.utils.update_checker.get_latest_version")
def test_check_for_updates_sync_with_update(mock_get_latest, monkeypatch, tmp_path):
    """Test sync update check when update is available."""
    monkeypatch.setattr("shotgun.utils.update_checker.__version__", "0.1.0")
    monkeypatch.setenv("SHOTGUN_HOME", str(tmp_path))
    mock_get_latest.return_value = "0.2.0"

    result = check_for_updates_sync()
    assert result == "Update available: 0.1.0 → 0.2.0. Run 'shotgun update' to upgrade."

    # Check cache was updated - load it with Pydantic model
    cache = load_cache()
    assert cache is not None
    assert cache.latest_version == "0.2.0"
    assert cache.update_available is True


@patch("shotgun.utils.update_checker.get_latest_version")
def test_check_for_updates_sync_no_update(mock_get_latest, monkeypatch, tmp_path):
    """Test sync update check when no update is available."""
    monkeypatch.setattr("shotgun.utils.update_checker.__version__", "0.2.0")
    monkeypatch.setenv("SHOTGUN_HOME", str(tmp_path))
    mock_get_latest.return_value = "0.2.0"

    result = check_for_updates_sync()
    assert result is None

    # Check cache was updated - load it with Pydantic model
    cache = load_cache()
    assert cache is not None
    assert cache.latest_version == "0.2.0"
    assert cache.update_available is False


def test_check_for_updates_sync_uses_cache(monkeypatch, tmp_path):
    """Test that sync check uses cache when fresh."""
    monkeypatch.setattr("shotgun.utils.update_checker.__version__", "0.1.0")
    monkeypatch.setenv("SHOTGUN_HOME", str(tmp_path))
    cache_file = tmp_path / "check-update.json"

    # Create fresh cache
    recent_time = datetime.now(timezone.utc) - timedelta(hours=1)
    cache_data = {
        "last_check": recent_time.isoformat(),
        "latest_version": "0.2.0",
        "current_version": "0.1.0",
        "update_available": True,
    }
    cache_file.write_text(json.dumps(cache_data))

    result = check_for_updates_sync()
    assert result == "Update available: 0.1.0 → 0.2.0. Run 'shotgun update' to upgrade."


@patch("shotgun.utils.update_checker.check_for_updates_sync")
def test_check_for_updates_async(mock_sync_check):
    """Test async update checking."""
    mock_sync_check.return_value = "Update available!"
    callback = MagicMock()

    thread = check_for_updates_async(callback=callback, no_update_check=False)
    thread.join(timeout=1)

    mock_sync_check.assert_called_once_with(False)
    callback.assert_called_once_with("Update available!")


@patch("shotgun.utils.update_checker.check_for_updates_sync")
def test_check_for_updates_async_no_callback(mock_sync_check):
    """Test async update checking without callback."""
    mock_sync_check.return_value = "Update available!"

    thread = check_for_updates_async(callback=None, no_update_check=False)
    thread.join(timeout=1)

    mock_sync_check.assert_called_once_with(False)


@patch("shotgun.utils.update_checker.check_for_updates_sync")
def test_check_for_updates_async_exception_handling(mock_sync_check):
    """Test async update checking handles exceptions gracefully."""
    mock_sync_check.side_effect = Exception("Test error")
    callback = MagicMock()

    thread = check_for_updates_async(callback=callback, no_update_check=False)
    thread.join(timeout=1)

    callback.assert_not_called()
