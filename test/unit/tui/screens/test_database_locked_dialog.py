"""Tests for DatabaseLockedDialog delete functionality."""

from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import pytest

from shotgun.codebase.core.errors import DatabaseIssue, KuzuErrorType
from shotgun.tui.screens.database_locked_dialog import DatabaseLockedDialog


def test_dialog_class_type():
    """Test that DatabaseLockedDialog returns the correct Literal type."""
    # The dialog class should be a ModalScreen with Literal return type
    from typing import Literal, get_args, get_origin

    from textual.screen import ModalScreen

    assert issubclass(DatabaseLockedDialog, ModalScreen)

    # Check the generic type annotation
    type_hint = DatabaseLockedDialog.__orig_bases__[0]
    origin = get_origin(type_hint)
    args = get_args(type_hint)

    # Should be ModalScreen[Literal["retry", "delete", "quit"]]
    assert origin is ModalScreen
    assert args == (Literal["retry", "delete", "quit"],)


@pytest.mark.asyncio
async def test_handle_pending_database_issues_delete_action(
    mock_agent_manager,
    mock_conversation_manager,
    mock_conversation_service,
    mock_widget_coordinator,
    mock_processing_state,
    mock_command_handler,
    mock_placeholder_hints,
    mock_codebase_sdk,
    mock_agent_deps,
    temp_storage_dir,
):
    """Test that delete action from locked dialog deletes the database."""
    from shotgun.tui.screens.chat import ChatScreen

    screen = ChatScreen(
        agent_manager=mock_agent_manager,
        conversation_manager=mock_conversation_manager,
        conversation_service=mock_conversation_service,
        widget_coordinator=mock_widget_coordinator,
        processing_state=mock_processing_state,
        command_handler=mock_command_handler,
        placeholder_hints=mock_placeholder_hints,
        codebase_sdk=mock_codebase_sdk,
        deps=mock_agent_deps,
    )

    # Create a mock app with pending database issues
    mock_app = Mock()
    locked_issue = DatabaseIssue(
        graph_id="test-graph-123",
        graph_path=temp_storage_dir / "test.kuzu",
        error_type=KuzuErrorType.LOCKED,
        message="Could not set lock",
    )
    mock_app.pending_db_issues = [locked_issue]

    # Mock push_screen_wait to return "delete"
    mock_app.push_screen_wait = AsyncMock(return_value="delete")
    mock_app.action_quit = AsyncMock()
    mock_app.size = Mock(height=50)

    # Mock the CodebaseGraphManager at its source module
    with patch("shotgun.codebase.core.manager.CodebaseGraphManager") as mock_manager_cls:
        mock_manager_instance = Mock()
        mock_manager_instance.delete_database = AsyncMock(return_value=True)
        mock_manager_cls.return_value = mock_manager_instance

        # Mock the app property on screen
        with patch.object(
            type(screen), "app", new_callable=PropertyMock
        ) as mock_app_prop:
            mock_app_prop.return_value = mock_app

            # Call the handler
            result = await screen._handle_pending_database_issues()

            # Should return True (continue with startup)
            assert result is True

            # Should have called delete_database
            mock_manager_instance.delete_database.assert_called_once_with(
                "test-graph-123"
            )

            # Should have added hint message about deletion
            mock_agent_manager.add_hint_message.assert_called()
            # Verify hint message mentions deletion and re-indexing
            call_args = mock_agent_manager.add_hint_message.call_args[0][0]
            assert "Deleted" in call_args.message
            assert "/index" in call_args.message


@pytest.mark.asyncio
async def test_handle_pending_database_issues_quit_action(
    mock_agent_manager,
    mock_conversation_manager,
    mock_conversation_service,
    mock_widget_coordinator,
    mock_processing_state,
    mock_command_handler,
    mock_placeholder_hints,
    mock_codebase_sdk,
    mock_agent_deps,
    temp_storage_dir,
):
    """Test that quit action from locked dialog exits the app."""
    from shotgun.tui.screens.chat import ChatScreen

    screen = ChatScreen(
        agent_manager=mock_agent_manager,
        conversation_manager=mock_conversation_manager,
        conversation_service=mock_conversation_service,
        widget_coordinator=mock_widget_coordinator,
        processing_state=mock_processing_state,
        command_handler=mock_command_handler,
        placeholder_hints=mock_placeholder_hints,
        codebase_sdk=mock_codebase_sdk,
        deps=mock_agent_deps,
    )

    # Create a mock app with pending database issues
    mock_app = Mock()
    locked_issue = DatabaseIssue(
        graph_id="test-graph-123",
        graph_path=temp_storage_dir / "test.kuzu",
        error_type=KuzuErrorType.LOCKED,
        message="Could not set lock",
    )
    mock_app.pending_db_issues = [locked_issue]

    # Mock push_screen_wait to return "quit"
    mock_app.push_screen_wait = AsyncMock(return_value="quit")
    mock_app.action_quit = AsyncMock()
    mock_app.size = Mock(height=50)

    # Mock the CodebaseGraphManager at its source module
    with patch("shotgun.codebase.core.manager.CodebaseGraphManager") as mock_manager_cls:
        mock_manager_instance = Mock()
        mock_manager_cls.return_value = mock_manager_instance

        # Mock the app property on screen
        with patch.object(
            type(screen), "app", new_callable=PropertyMock
        ) as mock_app_prop:
            mock_app_prop.return_value = mock_app

            # Call the handler
            result = await screen._handle_pending_database_issues()

            # Should return False (abort startup)
            assert result is False

            # Should have called action_quit
            mock_app.action_quit.assert_called_once()


@pytest.mark.asyncio
async def test_handle_pending_database_issues_retry_success(
    mock_agent_manager,
    mock_conversation_manager,
    mock_conversation_service,
    mock_widget_coordinator,
    mock_processing_state,
    mock_command_handler,
    mock_placeholder_hints,
    mock_codebase_sdk,
    mock_agent_deps,
    temp_storage_dir,
):
    """Test that retry action continues if lock is cleared."""
    from shotgun.tui.screens.chat import ChatScreen

    screen = ChatScreen(
        agent_manager=mock_agent_manager,
        conversation_manager=mock_conversation_manager,
        conversation_service=mock_conversation_service,
        widget_coordinator=mock_widget_coordinator,
        processing_state=mock_processing_state,
        command_handler=mock_command_handler,
        placeholder_hints=mock_placeholder_hints,
        codebase_sdk=mock_codebase_sdk,
        deps=mock_agent_deps,
    )

    # Create a mock app with pending database issues
    mock_app = Mock()
    locked_issue = DatabaseIssue(
        graph_id="test-graph-123",
        graph_path=temp_storage_dir / "test.kuzu",
        error_type=KuzuErrorType.LOCKED,
        message="Could not set lock",
    )
    mock_app.pending_db_issues = [locked_issue]

    # Mock push_screen_wait to return "retry"
    mock_app.push_screen_wait = AsyncMock(return_value="retry")
    mock_app.action_quit = AsyncMock()
    mock_app.size = Mock(height=50)

    # Mock the CodebaseGraphManager at its source module
    with patch("shotgun.codebase.core.manager.CodebaseGraphManager") as mock_manager_cls:
        mock_manager_instance = Mock()
        # Simulate lock being cleared on retry
        mock_manager_instance.detect_database_issues = AsyncMock(return_value=[])
        mock_manager_cls.return_value = mock_manager_instance

        # Mock the app property on screen
        with patch.object(
            type(screen), "app", new_callable=PropertyMock
        ) as mock_app_prop:
            mock_app_prop.return_value = mock_app

            # Call the handler
            result = await screen._handle_pending_database_issues()

            # Should return True (continue with startup)
            assert result is True

            # Should have called detect_database_issues to check if lock cleared
            mock_manager_instance.detect_database_issues.assert_called_once()


@pytest.mark.asyncio
async def test_handle_pending_database_issues_retry_still_locked(
    mock_agent_manager,
    mock_conversation_manager,
    mock_conversation_service,
    mock_widget_coordinator,
    mock_processing_state,
    mock_command_handler,
    mock_placeholder_hints,
    mock_codebase_sdk,
    mock_agent_deps,
    temp_storage_dir,
):
    """Test that retry action quits if lock persists."""
    from shotgun.tui.screens.chat import ChatScreen

    screen = ChatScreen(
        agent_manager=mock_agent_manager,
        conversation_manager=mock_conversation_manager,
        conversation_service=mock_conversation_service,
        widget_coordinator=mock_widget_coordinator,
        processing_state=mock_processing_state,
        command_handler=mock_command_handler,
        placeholder_hints=mock_placeholder_hints,
        codebase_sdk=mock_codebase_sdk,
        deps=mock_agent_deps,
    )

    # Create a mock app with pending database issues
    mock_app = Mock()
    locked_issue = DatabaseIssue(
        graph_id="test-graph-123",
        graph_path=temp_storage_dir / "test.kuzu",
        error_type=KuzuErrorType.LOCKED,
        message="Could not set lock",
    )
    mock_app.pending_db_issues = [locked_issue]

    # Mock push_screen_wait to return "retry"
    mock_app.push_screen_wait = AsyncMock(return_value="retry")
    mock_app.action_quit = AsyncMock()
    mock_app.size = Mock(height=50)

    # Mock the CodebaseGraphManager at its source module
    with patch("shotgun.codebase.core.manager.CodebaseGraphManager") as mock_manager_cls:
        mock_manager_instance = Mock()
        # Simulate lock still present on retry
        mock_manager_instance.detect_database_issues = AsyncMock(
            return_value=[locked_issue]
        )
        mock_manager_cls.return_value = mock_manager_instance

        # Mock the app property on screen
        with patch.object(
            type(screen), "app", new_callable=PropertyMock
        ) as mock_app_prop:
            mock_app_prop.return_value = mock_app

            # Call the handler
            result = await screen._handle_pending_database_issues()

            # Should return False (abort startup)
            assert result is False

            # Should have called action_quit since still locked
            mock_app.action_quit.assert_called_once()

            # Should have added hint message about still being locked
            mock_agent_manager.add_hint_message.assert_called()
            call_args = mock_agent_manager.add_hint_message.call_args[0][0]
            assert "still locked" in call_args.message


@pytest.mark.asyncio
async def test_handle_pending_database_issues_delete_multiple_locked(
    mock_agent_manager,
    mock_conversation_manager,
    mock_conversation_service,
    mock_widget_coordinator,
    mock_processing_state,
    mock_command_handler,
    mock_placeholder_hints,
    mock_codebase_sdk,
    mock_agent_deps,
    temp_storage_dir,
):
    """Test that delete action deletes all locked databases."""
    from shotgun.tui.screens.chat import ChatScreen

    screen = ChatScreen(
        agent_manager=mock_agent_manager,
        conversation_manager=mock_conversation_manager,
        conversation_service=mock_conversation_service,
        widget_coordinator=mock_widget_coordinator,
        processing_state=mock_processing_state,
        command_handler=mock_command_handler,
        placeholder_hints=mock_placeholder_hints,
        codebase_sdk=mock_codebase_sdk,
        deps=mock_agent_deps,
    )

    # Create a mock app with multiple locked database issues
    mock_app = Mock()
    locked_issue1 = DatabaseIssue(
        graph_id="test-graph-111",
        graph_path=temp_storage_dir / "test1.kuzu",
        error_type=KuzuErrorType.LOCKED,
        message="Could not set lock",
    )
    locked_issue2 = DatabaseIssue(
        graph_id="test-graph-222",
        graph_path=temp_storage_dir / "test2.kuzu",
        error_type=KuzuErrorType.LOCKED,
        message="Could not set lock",
    )
    mock_app.pending_db_issues = [locked_issue1, locked_issue2]

    # Mock push_screen_wait to return "delete"
    mock_app.push_screen_wait = AsyncMock(return_value="delete")
    mock_app.action_quit = AsyncMock()
    mock_app.size = Mock(height=50)

    # Mock the CodebaseGraphManager at its source module
    with patch("shotgun.codebase.core.manager.CodebaseGraphManager") as mock_manager_cls:
        mock_manager_instance = Mock()
        mock_manager_instance.delete_database = AsyncMock(return_value=True)
        mock_manager_cls.return_value = mock_manager_instance

        # Mock the app property on screen
        with patch.object(
            type(screen), "app", new_callable=PropertyMock
        ) as mock_app_prop:
            mock_app_prop.return_value = mock_app

            # Call the handler
            result = await screen._handle_pending_database_issues()

            # Should return True (continue with startup)
            assert result is True

            # Should have called delete_database for both
            assert mock_manager_instance.delete_database.call_count == 2
            mock_manager_instance.delete_database.assert_any_call("test-graph-111")
            mock_manager_instance.delete_database.assert_any_call("test-graph-222")
