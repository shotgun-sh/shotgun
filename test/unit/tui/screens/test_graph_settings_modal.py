"""Unit tests for GraphSettingsModal screen."""

from unittest.mock import AsyncMock, Mock

import pytest

from shotgun.agents.config.models import PersistentGraphOpenBehavior
from shotgun.tui.screens.chat.graph_settings_modal import GraphSettingsModal


@pytest.fixture
def mock_config_manager():
    """Create a mock ConfigManager for testing."""
    mock = Mock()
    mock.get_persistent_graph_behavior = AsyncMock(
        return_value=PersistentGraphOpenBehavior.ASK
    )
    mock.set_persistent_graph_behavior = AsyncMock()
    return mock


def test_modal_initialization(mock_config_manager):
    """Test that modal initializes correctly with config manager."""
    modal = GraphSettingsModal(mock_config_manager)

    assert modal.config_manager == mock_config_manager
    assert modal.current_behavior is None
    assert modal.selected_behavior is None


@pytest.mark.asyncio
async def test_on_mount_loads_current_behavior(mock_config_manager):
    """Test that on_mount loads current behavior from config."""
    mock_config_manager.get_persistent_graph_behavior = AsyncMock(
        return_value=PersistentGraphOpenBehavior.ALWAYS_REUSE
    )

    modal = GraphSettingsModal(mock_config_manager)

    # Mock query_one to return a mock ListView
    mock_list_view = Mock()
    mock_list_view.index = 0
    modal.query_one = Mock(return_value=mock_list_view)

    # Mock button query for focus
    mock_button = Mock()
    modal.query_one = Mock(side_effect=lambda selector, **kwargs: mock_list_view if "options-list" in selector else mock_button)

    await modal.on_mount()

    # Verify behavior was loaded
    assert modal.current_behavior == PersistentGraphOpenBehavior.ALWAYS_REUSE
    assert modal.selected_behavior == PersistentGraphOpenBehavior.ALWAYS_REUSE

    # Verify index was set to 1 (ALWAYS_REUSE is second option)
    assert mock_list_view.index == 1


def test_handle_selection_ask(mock_config_manager):
    """Test selection handler for ASK option."""
    modal = GraphSettingsModal(mock_config_manager)

    # Simulate ListView.Selected event for first option (ASK)
    event = Mock()
    event.list_view = Mock()
    event.list_view.index = 0
    event.stop = Mock()

    modal.handle_selection(event)

    # Verify selection was updated
    assert modal.selected_behavior == PersistentGraphOpenBehavior.ASK
    event.stop.assert_called_once()


def test_handle_selection_always_reuse(mock_config_manager):
    """Test selection handler for ALWAYS_REUSE option."""
    modal = GraphSettingsModal(mock_config_manager)

    # Simulate ListView.Selected event for second option (ALWAYS_REUSE)
    event = Mock()
    event.list_view = Mock()
    event.list_view.index = 1
    event.stop = Mock()

    modal.handle_selection(event)

    # Verify selection was updated
    assert modal.selected_behavior == PersistentGraphOpenBehavior.ALWAYS_REUSE
    event.stop.assert_called_once()


def test_handle_selection_always_new(mock_config_manager):
    """Test selection handler for ALWAYS_NEW option."""
    modal = GraphSettingsModal(mock_config_manager)

    # Simulate ListView.Selected event for third option (ALWAYS_NEW)
    event = Mock()
    event.list_view = Mock()
    event.list_view.index = 2
    event.stop = Mock()

    modal.handle_selection(event)

    # Verify selection was updated
    assert modal.selected_behavior == PersistentGraphOpenBehavior.ALWAYS_NEW
    event.stop.assert_called_once()


@pytest.mark.asyncio
async def test_handle_save_with_changes(mock_config_manager):
    """Test save button when settings changed."""
    modal = GraphSettingsModal(mock_config_manager)
    modal.current_behavior = PersistentGraphOpenBehavior.ASK
    modal.selected_behavior = PersistentGraphOpenBehavior.ALWAYS_REUSE

    # Mock dismiss
    modal.dismiss = Mock()

    # Simulate button press
    event = Mock()
    event.stop = Mock()

    await modal.handle_save(event)

    # Verify event was stopped
    event.stop.assert_called_once()

    # Verify config was saved
    mock_config_manager.set_persistent_graph_behavior.assert_called_once_with(
        PersistentGraphOpenBehavior.ALWAYS_REUSE
    )

    # Verify modal was dismissed with True (changed)
    modal.dismiss.assert_called_once_with(True)


@pytest.mark.asyncio
async def test_handle_save_without_changes(mock_config_manager):
    """Test save button when settings not changed."""
    modal = GraphSettingsModal(mock_config_manager)
    modal.current_behavior = PersistentGraphOpenBehavior.ASK
    modal.selected_behavior = PersistentGraphOpenBehavior.ASK

    # Mock dismiss
    modal.dismiss = Mock()

    # Simulate button press
    event = Mock()
    event.stop = Mock()

    await modal.handle_save(event)

    # Verify event was stopped
    event.stop.assert_called_once()

    # Verify config was NOT saved (no change)
    mock_config_manager.set_persistent_graph_behavior.assert_not_called()

    # Verify modal was dismissed with False (no change)
    modal.dismiss.assert_called_once_with(False)


@pytest.mark.asyncio
async def test_handle_save_with_no_selection(mock_config_manager):
    """Test save button when no selection made."""
    modal = GraphSettingsModal(mock_config_manager)
    modal.current_behavior = PersistentGraphOpenBehavior.ASK
    modal.selected_behavior = None

    # Mock dismiss
    modal.dismiss = Mock()

    # Simulate button press
    event = Mock()
    event.stop = Mock()

    await modal.handle_save(event)

    # Verify config was NOT saved
    mock_config_manager.set_persistent_graph_behavior.assert_not_called()

    # Verify modal was dismissed with False
    modal.dismiss.assert_called_once_with(False)


def test_handle_cancel(mock_config_manager):
    """Test cancel button handler."""
    modal = GraphSettingsModal(mock_config_manager)

    # Mock dismiss
    modal.dismiss = Mock()

    # Simulate button press
    event = Mock()
    event.stop = Mock()

    modal.handle_cancel(event)

    # Verify event was stopped
    event.stop.assert_called_once()

    # Verify modal was dismissed with False (cancelled)
    modal.dismiss.assert_called_once_with(False)


def test_escape_key_cancels(mock_config_manager):
    """Test that escape key dismisses modal without saving."""
    modal = GraphSettingsModal(mock_config_manager)

    # Mock dismiss
    modal.dismiss = Mock()

    # Simulate escape key press
    event = Mock()
    event.key = "escape"
    event.stop = Mock()

    modal.on_key(event)

    # Verify event was stopped
    event.stop.assert_called_once()

    # Verify modal was dismissed with False (cancelled)
    modal.dismiss.assert_called_once_with(False)


def test_escape_key_with_other_key(mock_config_manager):
    """Test that other keys don't dismiss modal."""
    modal = GraphSettingsModal(mock_config_manager)

    # Mock dismiss
    modal.dismiss = Mock()

    # Simulate other key press
    event = Mock()
    event.key = "enter"
    event.stop = Mock()

    modal.on_key(event)

    # Verify dismiss was NOT called
    modal.dismiss.assert_not_called()


def test_persistent_graph_open_behavior_enum_values():
    """Test that PersistentGraphOpenBehavior enum has expected values."""
    assert PersistentGraphOpenBehavior.ASK == "ASK"
    assert PersistentGraphOpenBehavior.ALWAYS_REUSE == "ALWAYS_REUSE"
    assert PersistentGraphOpenBehavior.ALWAYS_NEW == "ALWAYS_NEW"

    # Test that all values are strings
    assert isinstance(PersistentGraphOpenBehavior.ASK.value, str)
    assert isinstance(PersistentGraphOpenBehavior.ALWAYS_REUSE.value, str)
    assert isinstance(PersistentGraphOpenBehavior.ALWAYS_NEW.value, str)


@pytest.mark.asyncio
async def test_multiple_save_attempts(mock_config_manager):
    """Test that multiple save attempts work correctly."""
    modal = GraphSettingsModal(mock_config_manager)

    # First save with changes
    modal.current_behavior = PersistentGraphOpenBehavior.ASK
    modal.selected_behavior = PersistentGraphOpenBehavior.ALWAYS_REUSE
    modal.dismiss = Mock()

    event = Mock()
    event.stop = Mock()

    await modal.handle_save(event)

    # Verify first save
    mock_config_manager.set_persistent_graph_behavior.assert_called_once_with(
        PersistentGraphOpenBehavior.ALWAYS_REUSE
    )
    modal.dismiss.assert_called_once_with(True)

    # Reset mock
    mock_config_manager.set_persistent_graph_behavior.reset_mock()
    modal.dismiss.reset_mock()

    # Second save without changes (current and selected are now same)
    modal.current_behavior = PersistentGraphOpenBehavior.ALWAYS_REUSE
    modal.selected_behavior = PersistentGraphOpenBehavior.ALWAYS_REUSE

    await modal.handle_save(event)

    # Verify second save didn't call config manager
    mock_config_manager.set_persistent_graph_behavior.assert_not_called()
    modal.dismiss.assert_called_once_with(False)


@pytest.mark.asyncio
async def test_selection_changes_multiple_times(mock_config_manager):
    """Test changing selection multiple times before saving."""
    modal = GraphSettingsModal(mock_config_manager)
    modal.current_behavior = PersistentGraphOpenBehavior.ASK

    # First selection: ALWAYS_REUSE
    event1 = Mock()
    event1.list_view = Mock()
    event1.list_view.index = 1
    event1.stop = Mock()
    modal.handle_selection(event1)
    assert modal.selected_behavior == PersistentGraphOpenBehavior.ALWAYS_REUSE

    # Second selection: ALWAYS_NEW
    event2 = Mock()
    event2.list_view = Mock()
    event2.list_view.index = 2
    event2.stop = Mock()
    modal.handle_selection(event2)
    assert modal.selected_behavior == PersistentGraphOpenBehavior.ALWAYS_NEW

    # Third selection: back to ASK
    event3 = Mock()
    event3.list_view = Mock()
    event3.list_view.index = 0
    event3.stop = Mock()
    modal.handle_selection(event3)
    assert modal.selected_behavior == PersistentGraphOpenBehavior.ASK

    # Save (no change from original)
    modal.dismiss = Mock()
    save_event = Mock()
    save_event.stop = Mock()

    await modal.handle_save(save_event)

    # Should not save since final selection equals initial behavior
    mock_config_manager.set_persistent_graph_behavior.assert_not_called()
    modal.dismiss.assert_called_once_with(False)
