"""Tests for ShotgunAuthScreen copy URL button."""

from unittest.mock import Mock, patch

from shotgun.tui.screens.shotgun_auth import ShotgunAuthScreen


def test_copy_url_button_starts_disabled() -> None:
    """Test that the copy URL button is initially disabled (auth_url is None)."""
    screen = ShotgunAuthScreen()
    assert screen.auth_url is None


def test_on_copy_url_pressed_copies_url() -> None:
    """Test that pressing copy button copies the auth URL to clipboard."""
    screen = ShotgunAuthScreen()
    screen.auth_url = "https://example.com/auth/token123"

    mock_app = Mock()

    with patch.object(type(screen), "app", new=mock_app):
        with patch.object(screen, "notify") as mock_notify:
            screen._on_copy_url_pressed()

    mock_app.copy_to_clipboard.assert_called_once_with(
        "https://example.com/auth/token123"
    )
    mock_notify.assert_called_once_with("URL copied to clipboard")


def test_on_copy_url_pressed_no_url() -> None:
    """Test that pressing copy button does nothing when no URL is set."""
    screen = ShotgunAuthScreen()
    screen.auth_url = None

    mock_app = Mock()

    with patch.object(type(screen), "app", new=mock_app):
        screen._on_copy_url_pressed()

    mock_app.copy_to_clipboard.assert_not_called()
