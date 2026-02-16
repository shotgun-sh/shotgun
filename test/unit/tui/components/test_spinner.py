"""Tests for the Spinner component."""

from unittest.mock import MagicMock

from textual.timer import Timer

from shotgun.tui.components.spinner import Spinner


def test_on_unmount_stops_timer():
    """on_unmount should stop and clear the timer."""
    spinner = Spinner()
    mock_timer = MagicMock(spec=Timer)
    spinner._timer = mock_timer

    spinner.on_unmount()

    mock_timer.stop.assert_called_once()
    assert spinner._timer is None


def test_on_unmount_with_no_timer():
    """on_unmount should be safe when no timer exists."""
    spinner = Spinner()
    spinner._timer = None

    spinner.on_unmount()

    assert spinner._timer is None


def test_mount_unmount_cycle_no_leak():
    """Repeated mount/unmount cycles should not leak timers."""
    spinner = Spinner()

    timers = []
    for _ in range(5):
        mock_timer = MagicMock(spec=Timer)
        spinner._timer = mock_timer
        timers.append(mock_timer)

        spinner.on_unmount()

        assert spinner._timer is None
        mock_timer.stop.assert_called_once()

    # All timers were stopped
    assert all(t.stop.called for t in timers)
