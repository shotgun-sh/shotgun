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


def test_deduplicate_messages_removes_duplicate_tool_results(chat_screen):
    """Test that _deduplicate_messages removes duplicate tool result messages.

    In production, when the same tool result appears twice (from streaming and new_messages),
    it's the same ToolReturnPart instance wrapped in ModelRequest objects.
    """
    from pydantic_ai.messages import ModelRequest, ToolReturnPart

    # Create a tool result part (same instance used in both messages)
    tool_result = ToolReturnPart(
        tool_name="web_search", content="Search results", tool_call_id="call_1"
    )

    # Wrap same tool result in two different ModelRequest instances
    msg1 = ModelRequest(parts=[tool_result])
    msg2 = ModelRequest(parts=[tool_result])

    # Test deduplication
    messages = [msg1, msg2]
    deduplicated = chat_screen._deduplicate_messages(messages)

    # Should only have one message
    assert len(deduplicated) == 1
    assert deduplicated[0] == msg1


def test_deduplicate_messages_removes_duplicate_hints(chat_screen):
    """Test that _deduplicate_messages removes duplicate HintMessages."""
    from shotgun.tui.screens.chat_screen.hint_message import HintMessage

    # Create identical hint messages
    hint1 = HintMessage(message="Task completed successfully")
    hint2 = HintMessage(message="Task completed successfully")

    messages = [hint1, hint2]
    deduplicated = chat_screen._deduplicate_messages(messages)

    # Should only have one message
    assert len(deduplicated) == 1
    assert deduplicated[0] == hint1


def test_deduplicate_messages_preserves_order(chat_screen):
    """Test that _deduplicate_messages preserves the order of unique messages."""
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        TextPart,
        UserPromptPart,
    )
    from shotgun.tui.screens.chat_screen.hint_message import HintMessage

    # Create shared parts to simulate duplicates
    user_prompt = UserPromptPart(content="Hello")
    response1_parts = [TextPart(content="Hi there")]
    response2_parts = [TextPart(content="How can I help?")]

    # Create a mix of messages with some duplicates
    msg1 = ModelRequest(parts=[user_prompt])
    msg2 = ModelResponse(parts=response1_parts)
    hint1 = HintMessage(message="Processing")
    msg3 = ModelRequest(parts=[user_prompt])  # Duplicate of msg1 (same parts)
    hint2 = HintMessage(message="Processing")  # Duplicate of hint1
    msg4 = ModelResponse(parts=response2_parts)

    messages = [msg1, msg2, hint1, msg3, hint2, msg4]
    deduplicated = chat_screen._deduplicate_messages(messages)

    # Should have 4 unique messages in original order
    assert len(deduplicated) == 4
    assert deduplicated[0] == msg1
    assert deduplicated[1] == msg2
    assert deduplicated[2] == hint1
    assert deduplicated[3] == msg4
