"""Tests for sub-agent streaming response persistence.

When the router agent delegates to a sub-agent, the sub-agent's streaming
responses should persist in ui_message_history so they survive the
MessageHistoryUpdated rebuild that happens when the router run completes.
"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)

from shotgun.agents.agent_manager import AgentManager, AgentType
from shotgun.agents.models import AgentDeps


@pytest.fixture
def agent_manager():
    """Create a minimal AgentManager for testing sub-agent message persistence."""
    deps = MagicMock(spec=AgentDeps)
    deps.interactive_mode = True
    deps.working_directory = Path("/test")
    deps.is_tui_context = False
    deps.max_iterations = 10
    deps.queue = asyncio.Queue()
    deps.tasks = []

    manager = AgentManager(deps=deps, initial_type=AgentType.ROUTER)
    manager._current_agent_type = AgentType.ROUTER
    return manager


def test_sub_agent_messages_list_initialized(agent_manager):
    """_sub_agent_messages should be initialized as empty list."""
    assert agent_manager._sub_agent_messages == []


def test_sub_agent_tool_calls_persisted_in_ui_history(agent_manager):
    """Sub-agent tool call responses should be inserted into ui_message_history.

    In practice, sub-agent turns are almost always ToolCallPart (read_file,
    list_directory, etc.), not TextPart. These render as "Reading file: X"
    in the TUI and must survive the MessageHistoryUpdated rebuild.
    """
    # Simulate sub-agent tool call responses (the real-world case)
    sub_agent_read = ModelResponse(
        parts=[
            ToolCallPart(tool_name="read_file", args='{"filename": "pyproject.toml"}')
        ]
    )
    sub_agent_read._shotgun_is_sub_agent = True  # type: ignore[attr-defined]

    sub_agent_list = ModelResponse(
        parts=[ToolCallPart(tool_name="list_directory", args='{"path": "test"}')]
    )
    sub_agent_list._shotgun_is_sub_agent = True  # type: ignore[attr-defined]

    agent_manager._sub_agent_messages = [sub_agent_read, sub_agent_list]

    # Simulate original messages
    original_messages = [
        ModelRequest(parts=[UserPromptPart(content="Research testing frameworks")])
    ]

    # Simulate router's new messages after run
    router_delegation = ModelResponse(
        parts=[ToolCallPart(tool_name="delegate_to_research", args="{}")]
    )
    router_final = ModelResponse(parts=[TextPart(content="Based on my research...")])
    deduplicated_new_messages = [router_delegation, router_final]

    # Build ui_message_history the same way run() does
    agent_manager.ui_message_history = original_messages + deduplicated_new_messages

    # Apply the sub-agent interleaving logic via the extracted method
    agent_manager._interleave_sub_agent_messages(len(original_messages))

    # Verify sub-agent tool calls are in ui_message_history
    assert sub_agent_read in agent_manager.ui_message_history
    assert sub_agent_list in agent_manager.ui_message_history

    # Verify ordering: sub-agent responses should come before router's final response
    read_idx = agent_manager.ui_message_history.index(sub_agent_read)
    list_idx = agent_manager.ui_message_history.index(sub_agent_list)
    final_idx = agent_manager.ui_message_history.index(router_final)
    assert read_idx < final_idx
    assert list_idx < final_idx


def test_sub_agent_response_has_marker():
    """Sub-agent responses should have _shotgun_is_sub_agent marker."""
    resp = ModelResponse(
        parts=[ToolCallPart(tool_name="read_file", args='{"filename": "test.py"}')]
    )
    resp._shotgun_is_sub_agent = True  # type: ignore[attr-defined]

    assert getattr(resp, "_shotgun_is_sub_agent", False) is True


def test_regular_response_no_marker():
    """Regular responses should not have _shotgun_is_sub_agent marker."""
    resp = ModelResponse(parts=[TextPart(content="test")])
    assert getattr(resp, "_shotgun_is_sub_agent", False) is False


def test_sub_agent_messages_cleared_after_interleaving(agent_manager):
    """_sub_agent_messages should be cleared after being interleaved."""
    sub_resp = ModelResponse(
        parts=[ToolCallPart(tool_name="read_file", args='{"filename": "test.py"}')]
    )
    sub_resp._shotgun_is_sub_agent = True  # type: ignore[attr-defined]
    agent_manager._sub_agent_messages = [sub_resp]

    router_resp = ModelResponse(parts=[TextPart(content="Done")])
    agent_manager.ui_message_history = [router_resp]

    agent_manager._interleave_sub_agent_messages(0)

    assert agent_manager._sub_agent_messages == []


def test_many_sub_agent_tool_calls_preserved(agent_manager):
    """Many sub-agent tool calls (realistic scenario) should all be preserved."""
    # Simulate a realistic sub-agent run with many tool calls
    tool_calls = [
        ("list_directory", '{"path": "."}'),
        ("read_file", '{"filename": "pyproject.toml"}'),
        ("list_directory", '{"path": "test"}'),
        ("read_file", '{"filename": "test/conftest.py"}'),
        ("codebase_shell", '{"command": "grep", "args": ["pytest", "test/"]}'),
    ]
    sub_messages = []
    for tool_name, args in tool_calls:
        msg = ModelResponse(parts=[ToolCallPart(tool_name=tool_name, args=args)])
        msg._shotgun_is_sub_agent = True  # type: ignore[attr-defined]
        sub_messages.append(msg)

    agent_manager._sub_agent_messages = sub_messages

    router_final = ModelResponse(parts=[TextPart(content="Research complete")])
    agent_manager.ui_message_history = [router_final]

    agent_manager._interleave_sub_agent_messages(0)

    # All sub-agent messages should be in the history
    for msg in sub_messages:
        assert msg in agent_manager.ui_message_history

    # All should be before router's final response
    final_idx = agent_manager.ui_message_history.index(router_final)
    for msg in sub_messages:
        assert agent_manager.ui_message_history.index(msg) < final_idx


def test_no_sub_agent_messages_no_op(agent_manager):
    """When there are no sub-agent messages, ui_message_history should be unchanged."""
    agent_manager._sub_agent_messages = []
    router_resp = ModelResponse(parts=[TextPart(content="Result")])
    agent_manager.ui_message_history = [router_resp]

    original = agent_manager.ui_message_history.copy()

    agent_manager._interleave_sub_agent_messages(0)

    assert agent_manager.ui_message_history == original
