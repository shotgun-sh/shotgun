"""Tests for ProcessingStateManager."""

from unittest.mock import Mock

import pytest

from shotgun.tui.state.processing_state import ProcessingStateManager


@pytest.fixture
def mock_screen():
    """Create a mock screen."""
    return Mock()


@pytest.fixture
def mock_spinner():
    """Create a mock spinner widget."""
    spinner = Mock()
    spinner.text = "Processing..."
    return spinner


@pytest.fixture
def mock_worker():
    """Create a mock worker."""
    worker = Mock()
    worker.cancel = Mock()
    return worker


@pytest.fixture
def manager(mock_screen):
    """Create a ProcessingStateManager instance."""
    return ProcessingStateManager(mock_screen)


def test_initial_state(manager):
    """Test that manager starts in idle state."""
    assert manager.is_working is False
    assert manager._current_worker is None
    assert manager._spinner_widget is None


def test_bind_spinner(manager, mock_spinner):
    """Test binding a spinner widget."""
    manager.bind_spinner(mock_spinner)
    assert manager._spinner_widget is mock_spinner


def test_start_processing_with_default_text(manager, mock_spinner):
    """Test starting processing with default spinner text."""
    manager.bind_spinner(mock_spinner)
    manager.start_processing()

    assert manager.is_working is True
    assert mock_spinner.text == "Processing..."


def test_start_processing_with_custom_text(manager, mock_spinner):
    """Test starting processing with custom spinner text."""
    manager.bind_spinner(mock_spinner)
    manager.start_processing("Custom operation...")

    assert manager.is_working is True
    assert mock_spinner.text == "Custom operation..."


def test_start_processing_without_spinner(manager):
    """Test starting processing without bound spinner (should not error)."""
    manager.start_processing("Some work...")
    assert manager.is_working is True


def test_start_processing_while_already_working(manager, mock_spinner):
    """Test that starting processing while already working is a no-op."""
    manager.bind_spinner(mock_spinner)
    manager.start_processing("First operation")
    assert manager.is_working is True

    # Try to start again with different text
    manager.start_processing("Second operation")

    # Should still be working with first operation's text
    assert manager.is_working is True
    assert mock_spinner.text == "First operation"


def test_stop_processing(manager, mock_spinner):
    """Test stopping processing."""
    manager.bind_spinner(mock_spinner)
    manager.start_processing("Working...")

    manager.stop_processing()

    assert manager.is_working is False
    assert manager._current_worker is None
    assert mock_spinner.text == "Processing..."  # Reset to default


def test_stop_processing_when_not_working(manager):
    """Test that stopping when not working is a no-op."""
    manager.stop_processing()  # Should not error
    assert manager.is_working is False


def test_bind_worker(manager, mock_worker):
    """Test binding a worker for cancellation."""
    manager.bind_worker(mock_worker)
    assert manager._current_worker is mock_worker


def test_cancel_current_operation_success(manager, mock_spinner, mock_worker):
    """Test successfully cancelling a current operation."""
    manager.bind_spinner(mock_spinner)
    manager.start_processing("Working...")
    manager.bind_worker(mock_worker)

    result = manager.cancel_current_operation()

    assert result is True
    mock_worker.cancel.assert_called_once()


def test_cancel_when_not_working(manager):
    """Test cancellation when no operation is running."""
    result = manager.cancel_current_operation()
    assert result is False


def test_cancel_when_no_worker_bound(manager, mock_spinner):
    """Test cancellation when working but no worker is bound."""
    manager.bind_spinner(mock_spinner)
    manager.start_processing("Working...")
    # Don't bind a worker

    result = manager.cancel_current_operation()
    assert result is False


def test_cancel_operation_with_exception(manager, mock_spinner, mock_worker):
    """Test handling exception during cancellation."""
    manager.bind_spinner(mock_spinner)
    manager.start_processing("Working...")
    manager.bind_worker(mock_worker)

    # Make cancel() raise an exception
    mock_worker.cancel.side_effect = RuntimeError("Cancel failed")

    result = manager.cancel_current_operation()
    assert result is False


def test_update_spinner_text_while_working(manager, mock_spinner):
    """Test updating spinner text during processing."""
    manager.bind_spinner(mock_spinner)
    manager.start_processing("Initial text")

    manager.update_spinner_text("Updated text")

    assert mock_spinner.text == "Updated text"


def test_update_spinner_text_when_not_working(manager, mock_spinner):
    """Test that updating spinner text when not working is a no-op."""
    manager.bind_spinner(mock_spinner)
    initial_text = mock_spinner.text

    manager.update_spinner_text("Should not update")

    assert mock_spinner.text == initial_text


def test_update_spinner_text_without_bound_spinner(manager):
    """Test updating spinner text without bound spinner (should not error)."""
    manager.start_processing("Working...")
    manager.update_spinner_text("New text")  # Should not raise


def test_full_operation_lifecycle(manager, mock_spinner, mock_worker):
    """Test a complete operation lifecycle."""
    # Setup
    manager.bind_spinner(mock_spinner)

    # Start operation
    manager.start_processing("Starting work...")
    assert manager.is_working is True
    assert mock_spinner.text == "Starting work..."

    # Bind worker
    manager.bind_worker(mock_worker)
    assert manager._current_worker is mock_worker

    # Update spinner during work
    manager.update_spinner_text("Still working...")
    assert mock_spinner.text == "Still working..."

    # Complete operation
    manager.stop_processing()
    assert manager.is_working is False
    assert manager._current_worker is None
    assert mock_spinner.text == "Processing..."  # Reset to default


def test_full_cancellation_lifecycle(manager, mock_spinner, mock_worker):
    """Test a complete cancellation lifecycle."""
    # Setup
    manager.bind_spinner(mock_spinner)

    # Start operation
    manager.start_processing("Long operation...")
    manager.bind_worker(mock_worker)

    # User cancels
    result = manager.cancel_current_operation()
    assert result is True
    mock_worker.cancel.assert_called_once()

    # Clean up
    manager.stop_processing()
    assert manager.is_working is False
