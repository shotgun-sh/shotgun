"""Tests for DatabaseLockedDialog delete functionality."""

from typing import get_args, get_origin
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import pytest
from textual.screen import ModalScreen

from shotgun.codebase.core.errors import DatabaseIssue, KuzuErrorType
from shotgun.tui.screens.database_locked_dialog import DatabaseLockedDialog
from shotgun.tui.screens.models import LockedDialogAction


def test_dialog_class_type():
    """Test that DatabaseLockedDialog returns the correct LockedDialogAction type."""
    assert issubclass(DatabaseLockedDialog, ModalScreen)

    # Check the generic type annotation
    type_hint = DatabaseLockedDialog.__orig_bases__[0]
    origin = get_origin(type_hint)
    args = get_args(type_hint)

    # Should be ModalScreen[LockedDialogAction]
    assert origin is ModalScreen
    assert args == (LockedDialogAction,)


@pytest.fixture
def locked_db_test_context(
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
    """Create common test context for database locked dialog tests.

    Returns a dict with screen, mock_app, temp_storage_dir, and mock_agent_manager.
    """
    # Import ChatScreen inside fixture to avoid import ordering issues
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

    mock_app = Mock()
    mock_app.action_quit = AsyncMock()
    mock_app.size = Mock(height=50)

    return {
        "screen": screen,
        "mock_app": mock_app,
        "temp_storage_dir": temp_storage_dir,
        "mock_agent_manager": mock_agent_manager,
    }


@pytest.mark.asyncio
async def test_handle_pending_database_issues_delete_action(locked_db_test_context):
    """Test that delete action from locked dialog deletes the database."""
    ctx = locked_db_test_context
    screen = ctx["screen"]
    mock_app = ctx["mock_app"]
    temp_storage_dir = ctx["temp_storage_dir"]
    mock_agent_manager = ctx["mock_agent_manager"]

    locked_issue = DatabaseIssue(
        graph_id="test-graph-123",
        graph_path=temp_storage_dir / "test.kuzu",
        error_type=KuzuErrorType.LOCKED,
        message="Could not set lock",
    )
    mock_app.pending_db_issues = [locked_issue]
    mock_app.push_screen_wait = AsyncMock(return_value=LockedDialogAction.DELETE)

    with patch(
        "shotgun.codebase.core.manager.CodebaseGraphManager"
    ) as mock_manager_cls:
        mock_manager_instance = Mock()
        mock_manager_instance.delete_database = AsyncMock(return_value=True)
        mock_manager_cls.return_value = mock_manager_instance

        with patch.object(
            type(screen), "app", new_callable=PropertyMock
        ) as mock_app_prop:
            mock_app_prop.return_value = mock_app

            result = await screen._handle_pending_database_issues()

            assert result is True
            mock_manager_instance.delete_database.assert_called_once_with(
                "test-graph-123"
            )
            mock_agent_manager.add_hint_message.assert_called()
            call_args = mock_agent_manager.add_hint_message.call_args[0][0]
            assert "Deleted" in call_args.message
            assert "/index" in call_args.message


@pytest.mark.asyncio
async def test_handle_pending_database_issues_quit_action(locked_db_test_context):
    """Test that quit action from locked dialog exits the app."""
    ctx = locked_db_test_context
    screen = ctx["screen"]
    mock_app = ctx["mock_app"]
    temp_storage_dir = ctx["temp_storage_dir"]

    locked_issue = DatabaseIssue(
        graph_id="test-graph-123",
        graph_path=temp_storage_dir / "test.kuzu",
        error_type=KuzuErrorType.LOCKED,
        message="Could not set lock",
    )
    mock_app.pending_db_issues = [locked_issue]
    mock_app.push_screen_wait = AsyncMock(return_value=LockedDialogAction.QUIT)

    with patch(
        "shotgun.codebase.core.manager.CodebaseGraphManager"
    ) as mock_manager_cls:
        mock_manager_instance = Mock()
        mock_manager_cls.return_value = mock_manager_instance

        with patch.object(
            type(screen), "app", new_callable=PropertyMock
        ) as mock_app_prop:
            mock_app_prop.return_value = mock_app

            result = await screen._handle_pending_database_issues()

            assert result is False
            mock_app.action_quit.assert_called_once()


@pytest.mark.asyncio
async def test_handle_pending_database_issues_retry_success(locked_db_test_context):
    """Test that retry action continues if lock is cleared."""
    ctx = locked_db_test_context
    screen = ctx["screen"]
    mock_app = ctx["mock_app"]
    temp_storage_dir = ctx["temp_storage_dir"]

    locked_issue = DatabaseIssue(
        graph_id="test-graph-123",
        graph_path=temp_storage_dir / "test.kuzu",
        error_type=KuzuErrorType.LOCKED,
        message="Could not set lock",
    )
    mock_app.pending_db_issues = [locked_issue]
    mock_app.push_screen_wait = AsyncMock(return_value=LockedDialogAction.RETRY)

    with patch(
        "shotgun.codebase.core.manager.CodebaseGraphManager"
    ) as mock_manager_cls:
        mock_manager_instance = Mock()
        mock_manager_instance.detect_database_issues = AsyncMock(return_value=[])
        mock_manager_cls.return_value = mock_manager_instance

        with patch.object(
            type(screen), "app", new_callable=PropertyMock
        ) as mock_app_prop:
            mock_app_prop.return_value = mock_app

            result = await screen._handle_pending_database_issues()

            assert result is True
            mock_manager_instance.detect_database_issues.assert_called_once()


@pytest.mark.asyncio
async def test_handle_pending_database_issues_retry_still_locked(locked_db_test_context):
    """Test that retry action quits if lock persists."""
    ctx = locked_db_test_context
    screen = ctx["screen"]
    mock_app = ctx["mock_app"]
    temp_storage_dir = ctx["temp_storage_dir"]
    mock_agent_manager = ctx["mock_agent_manager"]

    locked_issue = DatabaseIssue(
        graph_id="test-graph-123",
        graph_path=temp_storage_dir / "test.kuzu",
        error_type=KuzuErrorType.LOCKED,
        message="Could not set lock",
    )
    mock_app.pending_db_issues = [locked_issue]
    mock_app.push_screen_wait = AsyncMock(return_value=LockedDialogAction.RETRY)

    with patch(
        "shotgun.codebase.core.manager.CodebaseGraphManager"
    ) as mock_manager_cls:
        mock_manager_instance = Mock()
        mock_manager_instance.detect_database_issues = AsyncMock(
            return_value=[locked_issue]
        )
        mock_manager_cls.return_value = mock_manager_instance

        with patch.object(
            type(screen), "app", new_callable=PropertyMock
        ) as mock_app_prop:
            mock_app_prop.return_value = mock_app

            result = await screen._handle_pending_database_issues()

            assert result is False
            mock_app.action_quit.assert_called_once()
            mock_agent_manager.add_hint_message.assert_called()
            call_args = mock_agent_manager.add_hint_message.call_args[0][0]
            assert "still locked" in call_args.message


@pytest.mark.asyncio
async def test_handle_pending_database_issues_delete_multiple_locked(
    locked_db_test_context,
):
    """Test that delete action deletes all locked databases."""
    ctx = locked_db_test_context
    screen = ctx["screen"]
    mock_app = ctx["mock_app"]
    temp_storage_dir = ctx["temp_storage_dir"]

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
    mock_app.push_screen_wait = AsyncMock(return_value=LockedDialogAction.DELETE)

    with patch(
        "shotgun.codebase.core.manager.CodebaseGraphManager"
    ) as mock_manager_cls:
        mock_manager_instance = Mock()
        mock_manager_instance.delete_database = AsyncMock(return_value=True)
        mock_manager_cls.return_value = mock_manager_instance

        with patch.object(
            type(screen), "app", new_callable=PropertyMock
        ) as mock_app_prop:
            mock_app_prop.return_value = mock_app

            result = await screen._handle_pending_database_issues()

            assert result is True
            assert mock_manager_instance.delete_database.call_count == 2
            mock_manager_instance.delete_database.assert_any_call("test-graph-111")
            mock_manager_instance.delete_database.assert_any_call("test-graph-222")
