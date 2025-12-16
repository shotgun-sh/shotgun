"""Tests for ChatScreen dependency injection."""

from unittest.mock import AsyncMock, Mock

import pytest

from shotgun.agents.models import AgentType
from shotgun.tui.screens.chat import ChatScreen


@pytest.fixture
def chat_screen(
    mock_agent_manager,
    mock_conversation_manager,
    mock_conversation_service,
    mock_widget_coordinator,
    mock_processing_state,
    mock_command_handler,
    mock_placeholder_hints,
    mock_codebase_sdk,
    mock_agent_deps,
):
    """Create a ChatScreen instance with mocked dependencies."""
    return ChatScreen(
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


def test_dependency_injection(chat_screen, mock_agent_manager):
    """Test that dependencies are properly injected."""
    assert chat_screen.agent_manager is mock_agent_manager
    assert chat_screen.agent_manager.current_type == AgentType.RESEARCH


def test_initial_state(chat_screen):
    """Test that ChatScreen initializes with correct default state."""
    assert chat_screen.mode == AgentType.RESEARCH
    assert chat_screen.working is False
    assert chat_screen.qa_mode is False
    assert chat_screen.messages == []


def test_all_dependencies_required(
    mock_agent_deps,
    mock_agent_manager,
    mock_conversation_manager,
    mock_conversation_service,
    mock_widget_coordinator,
    mock_processing_state,
    mock_command_handler,
    mock_placeholder_hints,
    mock_codebase_sdk,
):
    """Test that all dependencies are required and must be provided."""
    # All dependencies must be provided via dependency injection
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

    # Verify all dependencies are properly set
    assert screen.deps is mock_agent_deps
    assert screen.agent_manager is mock_agent_manager
    assert screen.conversation_manager is mock_conversation_manager
    assert screen.conversation_service is mock_conversation_service
    assert screen.widget_coordinator is mock_widget_coordinator
    assert screen.processing_state is mock_processing_state
    assert screen.codebase_sdk is mock_codebase_sdk
    assert screen.command_handler is mock_command_handler
    assert screen.placeholder_hints is mock_placeholder_hints


def test_processing_state_receives_telemetry_context(
    mock_agent_manager,
    mock_conversation_manager,
    mock_conversation_service,
    mock_widget_coordinator,
    mock_command_handler,
    mock_placeholder_hints,
    mock_codebase_sdk,
    mock_agent_deps,
    mock_processing_state,
):
    """Test that ProcessingStateManager receives correct telemetry context via DI."""
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

    # Verify ProcessingStateManager was injected correctly
    assert screen.processing_state is mock_processing_state


@pytest.mark.asyncio
async def test_mocked_agent_run(chat_screen, mock_agent_manager):
    """Test that mocked agent manager can simulate responses without real LLM calls."""
    mock_agent_manager.run_agent.return_value = "Mocked response"

    result = await mock_agent_manager.run_agent("Test prompt")

    assert result == "Mocked response"
    mock_agent_manager.run_agent.assert_called_once_with("Test prompt")


def test_mocked_cancellation(chat_screen, mock_processing_state):
    """Test that cancellation can be simulated without real operations."""
    # Simulate that an operation is running
    mock_processing_state.is_working = True
    mock_processing_state.cancel_current_operation.return_value = True

    # Test cancellation
    result = mock_processing_state.cancel_current_operation(cancel_key="Escape")

    assert result is True
    mock_processing_state.cancel_current_operation.assert_called_once_with(
        cancel_key="Escape"
    )


@pytest.mark.asyncio
async def test_mocked_conversation_save(chat_screen, mock_conversation_manager):
    """Test that conversation saving can be tested without filesystem access."""
    await chat_screen.conversation_manager.save()

    mock_conversation_manager.save.assert_called_once()


@pytest.mark.asyncio
async def test_mocked_conversation_load(chat_screen, mock_conversation_manager):
    """Test that conversation loading can be tested without filesystem access."""
    mock_conversation_manager.load.return_value = None

    result = await chat_screen.conversation_manager.load()

    assert result is None
    mock_conversation_manager.load.assert_called_once()


@pytest.mark.asyncio
async def test_agent_manager_error_handling(chat_screen, mock_agent_manager):
    """Test that agent manager errors can be simulated and tested."""
    # Simulate an error from the agent
    mock_agent_manager.run_agent.side_effect = RuntimeError("LLM API error")

    with pytest.raises(RuntimeError, match="LLM API error"):
        await mock_agent_manager.run_agent("Test prompt")


def test_codebase_sdk_mocked(chat_screen, mock_codebase_sdk):
    """Test that CodebaseSDK operations can be mocked."""
    # Verify the SDK is the mocked instance
    assert chat_screen.codebase_sdk is mock_codebase_sdk

    # Test that we can configure mock behavior
    mock_codebase_sdk.list_codebases_for_directory.return_value = AsyncMock(
        return_value=Mock(graphs=[])
    )


class TestQAModeToggle:
    """Tests for Q&A mode toggle behavior - SHIFT+TAB exits Q&A mode."""

    def test_shift_tab_exits_qa_mode_when_questions_empty(
        self,
        mock_agent_manager,
        mock_conversation_manager,
        mock_conversation_service,
        mock_widget_coordinator,
        mock_processing_state,
        mock_command_handler,
        mock_placeholder_hints,
        mock_codebase_sdk,
        mock_agent_deps,
    ):
        """Test that SHIFT+TAB exits Q&A mode when qa_questions is empty."""
        from shotgun.agents.router.models import RouterDeps, RouterMode
        from shotgun.tui.screens.chat import ChatScreen

        router_deps = RouterDeps(
            interactive_mode=True,
            is_tui_context=True,
            llm_model=mock_agent_deps.llm_model,
            codebase_service=mock_agent_deps.codebase_service,
            system_prompt_fn=mock_agent_deps.system_prompt_fn,
            router_mode=RouterMode.PLANNING,
        )

        screen = ChatScreen(
            agent_manager=mock_agent_manager,
            conversation_manager=mock_conversation_manager,
            conversation_service=mock_conversation_service,
            widget_coordinator=mock_widget_coordinator,
            processing_state=mock_processing_state,
            command_handler=mock_command_handler,
            placeholder_hints=mock_placeholder_hints,
            codebase_sdk=mock_codebase_sdk,
            deps=router_deps,
        )

        # Simulate stuck Q&A mode: qa_mode=True but qa_questions is empty
        screen.qa_mode = True
        screen.qa_questions = []

        # Press SHIFT+TAB (action_toggle_mode)
        screen.action_toggle_mode()

        # Q&A mode should be exited
        assert screen.qa_mode is False
        # Mode should NOT have changed (just exits Q&A, doesn't toggle)
        assert router_deps.router_mode == RouterMode.PLANNING
        # Hint should have been shown
        mock_agent_manager.add_hint_message.assert_called()

    def test_shift_tab_exits_qa_mode_when_questions_exist(
        self,
        mock_agent_manager,
        mock_conversation_manager,
        mock_conversation_service,
        mock_widget_coordinator,
        mock_processing_state,
        mock_command_handler,
        mock_placeholder_hints,
        mock_codebase_sdk,
        mock_agent_deps,
    ):
        """Test that SHIFT+TAB exits Q&A mode even when questions exist."""
        from shotgun.agents.router.models import RouterDeps, RouterMode
        from shotgun.tui.screens.chat import ChatScreen

        router_deps = RouterDeps(
            interactive_mode=True,
            is_tui_context=True,
            llm_model=mock_agent_deps.llm_model,
            codebase_service=mock_agent_deps.codebase_service,
            system_prompt_fn=mock_agent_deps.system_prompt_fn,
            router_mode=RouterMode.PLANNING,
        )

        screen = ChatScreen(
            agent_manager=mock_agent_manager,
            conversation_manager=mock_conversation_manager,
            conversation_service=mock_conversation_service,
            widget_coordinator=mock_widget_coordinator,
            processing_state=mock_processing_state,
            command_handler=mock_command_handler,
            placeholder_hints=mock_placeholder_hints,
            codebase_sdk=mock_codebase_sdk,
            deps=router_deps,
        )

        # Active Q&A mode with questions
        screen.qa_mode = True
        screen.qa_questions = ["Question 1?", "Question 2?"]

        # Press SHIFT+TAB (action_toggle_mode)
        screen.action_toggle_mode()

        # Q&A mode should be exited
        assert screen.qa_mode is False
        # Mode should NOT have changed (just exits Q&A, doesn't toggle)
        assert router_deps.router_mode == RouterMode.PLANNING
        # Hint should have been shown
        mock_agent_manager.add_hint_message.assert_called()

    def test_handle_clarifying_questions_skips_empty_questions(
        self,
        mock_agent_manager,
        mock_conversation_manager,
        mock_conversation_service,
        mock_widget_coordinator,
        mock_processing_state,
        mock_command_handler,
        mock_placeholder_hints,
        mock_codebase_sdk,
        mock_agent_deps,
    ):
        """Test that handle_clarifying_questions doesn't enter Q&A mode with empty questions."""
        from shotgun.agents.agent_manager import ClarifyingQuestionsMessage
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

        # Create event with empty questions
        event = ClarifyingQuestionsMessage(questions=[], response_text="Test response")

        # Handle the event
        screen.handle_clarifying_questions(event)

        # Q&A mode should NOT be active
        assert screen.qa_mode is False
        assert screen.qa_questions == []
