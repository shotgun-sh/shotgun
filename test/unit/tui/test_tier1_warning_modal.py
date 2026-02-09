"""Tests for Tier 1 warning modal."""

from unittest.mock import Mock

from textual.widgets import Button

from shotgun.tui.screens.tier1_warning_modal import Tier1WarningModal


def test_modal_can_be_instantiated():
    """Test modal can be instantiated."""
    modal = Tier1WarningModal()
    assert modal is not None


def test_button_press_dismisses_modal():
    """Test that button press event dismisses the modal."""
    modal = Tier1WarningModal()
    modal.dismiss = Mock()

    # Create a button pressed event
    button = Button("I Understand", id="understand-button")
    event = Button.Pressed(button)

    # Handle the event
    modal.on_button_pressed(event)

    # Should call dismiss(True)
    modal.dismiss.assert_called_once_with(True)
