"""Tests for ChatScreen dependency injection."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from shotgun.agents.models import AgentType
from shotgun.tui.screens.chat import ChatScreen


@pytest.fixture
def chat_screen(
    mock_agent_manager,
    mock_conversation_manager,
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


def test_backward_compatibility_with_deps(mock_agent_deps):
    """Test that ChatScreen works with only deps injected (partial DI)."""
    # Inject only deps, let ChatScreen create the rest
    screen = ChatScreen(deps=mock_agent_deps)

    # Verify deps is set
    assert screen.deps is mock_agent_deps

    # Verify other dependencies were auto-created
    assert screen.agent_manager is not None
    assert screen.conversation_manager is not None
    assert screen.processing_state is not None
    assert screen.codebase_sdk is not None


def test_processing_state_receives_telemetry_context(
    mock_agent_manager,
    mock_conversation_manager,
    mock_command_handler,
    mock_placeholder_hints,
    mock_codebase_sdk,
    mock_agent_deps,
):
    """Test that ProcessingStateManager receives correct telemetry context."""
    with patch("shotgun.tui.screens.chat.ProcessingStateManager") as mock_state_class:
        mock_state_instance = Mock()
        mock_state_class.return_value = mock_state_instance

        screen = ChatScreen(
            agent_manager=mock_agent_manager,
            conversation_manager=mock_conversation_manager,
            command_handler=mock_command_handler,
            placeholder_hints=mock_placeholder_hints,
            codebase_sdk=mock_codebase_sdk,
            deps=mock_agent_deps,
        )

        # Verify ProcessingStateManager was called with telemetry context
        mock_state_class.assert_called_once_with(
            screen, telemetry_context={"agent_mode": AgentType.RESEARCH.value}
        )


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


def test_mocked_conversation_save(chat_screen, mock_conversation_manager):
    """Test that conversation saving can be tested without filesystem access."""
    chat_screen.conversation_manager.save()

    mock_conversation_manager.save.assert_called_once()


def test_mocked_conversation_load(chat_screen, mock_conversation_manager):
    """Test that conversation loading can be tested without filesystem access."""
    mock_conversation_manager.load.return_value = None

    result = chat_screen.conversation_manager.load()

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
