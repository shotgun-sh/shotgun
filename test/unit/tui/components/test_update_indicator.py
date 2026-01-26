"""Tests for UpdateIndicator component."""

from shotgun.tui.components.update_indicator import UpdateIndicator
from shotgun.utils.update_checker import UpdateInfo


def create_test_update_info(
    current_version: str = "0.1.0",
    latest_version: str = "0.2.0",
    update_available: bool = True,
    installation_method: str = "pipx",
) -> UpdateInfo:
    """Create a test UpdateInfo object."""
    upgrade_commands = {
        "uvx": None,
        "uv-tool": ["uv", "tool", "upgrade", "shotgun-sh"],
        "pipx": ["pipx", "upgrade", "shotgun-sh"],
        "pip": ["pip", "install", "--upgrade", "shotgun-sh"],
    }
    upgrade_hints = {
        "uvx": "Run `uvx shotgun-sh@latest` to use the latest version",
        "uv-tool": "Run `uv tool upgrade shotgun-sh` to update",
        "pipx": "Run `pipx upgrade shotgun-sh` to update",
        "pip": "Run `pip install --upgrade shotgun-sh` to update",
    }
    return UpdateInfo(
        current_version=current_version,
        latest_version=latest_version,
        update_available=update_available,
        installation_method=installation_method,
        upgrade_command=upgrade_commands.get(installation_method),
        upgrade_hint=upgrade_hints.get(installation_method, upgrade_hints["pip"]),
    )


def test_update_indicator_initialization():
    """Test UpdateIndicator can be initialized."""
    indicator = UpdateIndicator(id="test-indicator")
    assert indicator.update_info is None
    assert indicator.display is False


def test_update_indicator_set_update_info():
    """Test setting update info shows the indicator."""
    indicator = UpdateIndicator()

    info = create_test_update_info(
        current_version="0.1.0",
        latest_version="0.2.0",
        update_available=True,
    )

    indicator.set_update_info(info)

    assert indicator.update_info == info
    assert indicator.display is True


def test_update_indicator_hidden_when_no_update():
    """Test indicator is hidden when no update available."""
    indicator = UpdateIndicator()

    info = create_test_update_info(
        current_version="0.2.0",
        latest_version="0.2.0",
        update_available=False,
    )

    indicator.set_update_info(info)

    assert indicator.update_info == info
    assert indicator.display is False


def test_update_indicator_hidden_when_none():
    """Test indicator is hidden when info is None."""
    indicator = UpdateIndicator()

    # First set some update info
    info = create_test_update_info(update_available=True)
    indicator.set_update_info(info)
    assert indicator.display is True

    # Then set None
    indicator.set_update_info(None)
    assert indicator.update_info is None
    assert indicator.display is False


def test_update_indicator_different_installation_methods():
    """Test indicator works with different installation methods."""
    indicator = UpdateIndicator()

    for method in ["uvx", "uv-tool", "pipx", "pip"]:
        info = create_test_update_info(
            installation_method=method,
            update_available=True,
        )
        indicator.set_update_info(info)

        assert indicator.update_info == info
        assert indicator.update_info.installation_method == method
        assert indicator.display is True


def test_update_indicator_watch_update_info():
    """Test reactive watch triggers refresh."""
    indicator = UpdateIndicator()

    info = create_test_update_info(update_available=True)

    # Setting the reactive attribute should trigger watch
    indicator.update_info = info

    # The watch should have been called and updated display
    assert indicator.display is True
