"""Test that different prompt types are preserved during history compaction."""

from unittest.mock import MagicMock

import pytest
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from shotgun.agents.conversation.history.message_utils import (
    get_agent_system_prompt,
    get_latest_system_status,
)
from shotgun.agents.messages import AgentSystemPrompt, SystemStatusPrompt
from shotgun.agents.models import AgentDeps


@pytest.fixture
def mock_ctx():
    """Create mock context for testing."""

    # Create a minimal context that token_limit_compactor expects
    class MockContext:
        def __init__(self):
            self.deps = MagicMock(spec=AgentDeps)
            self.deps.llm_model = MagicMock()
            self.deps.llm_model.max_input_tokens = 128000
            self.usage = None

    return MockContext()


@pytest.mark.asyncio
async def test_system_prompts_preserved_in_messages():
    """Test that both AgentSystemPrompt and SystemStatusPrompt can be retrieved."""

    # Create test messages with both prompt types
    messages: list[ModelMessage] = [
        ModelRequest(
            parts=[
                AgentSystemPrompt(content="You are a helpful assistant."),
                SystemStatusPrompt(
                    content="Current status: Files available: research.md"
                ),
                UserPromptPart(content="Hello"),
            ]
        ),
        ModelResponse(parts=[TextPart(content="Hi there!")]),
        ModelRequest(
            parts=[
                UserPromptPart(content="How are you?"),
            ]
        ),
        ModelResponse(parts=[TextPart(content="I'm doing well, thanks!")]),
        # Add a newer status update
        ModelRequest(
            parts=[
                SystemStatusPrompt(
                    content="Current status: Files available: research.md, plan.md"
                ),
                UserPromptPart(content="What files do we have?"),
            ]
        ),
        ModelResponse(parts=[TextPart(content="We have research.md and plan.md")]),
    ]

    # Check that agent system prompt can be retrieved
    agent_prompt = get_agent_system_prompt(messages)
    assert agent_prompt == "You are a helpful assistant."

    # Check that the LATEST system status can be retrieved
    system_status = get_latest_system_status(messages)
    assert system_status == "Current status: Files available: research.md, plan.md"


@pytest.mark.asyncio
async def test_only_latest_system_status_preserved():
    """Test that only the most recent SystemStatusPrompt is preserved."""

    messages: list[ModelMessage] = [
        ModelRequest(
            parts=[
                AgentSystemPrompt(content="Main agent prompt"),
                SystemStatusPrompt(content="Status 1"),
                UserPromptPart(content="First query"),
            ]
        ),
        ModelResponse(parts=[TextPart(content="Response 1")]),
        ModelRequest(
            parts=[
                SystemStatusPrompt(content="Status 2"),
                UserPromptPart(content="Second query"),
            ]
        ),
        ModelResponse(parts=[TextPart(content="Response 2")]),
        ModelRequest(
            parts=[
                SystemStatusPrompt(content="Status 3 - Latest"),
                UserPromptPart(content="Third query"),
            ]
        ),
        ModelResponse(parts=[TextPart(content="Response 3")]),
    ]

    # Should preserve the agent prompt
    agent_prompt = get_agent_system_prompt(messages)
    assert agent_prompt == "Main agent prompt"

    # Should only have the latest status
    system_status = get_latest_system_status(messages)
    assert system_status == "Status 3 - Latest"


@pytest.mark.asyncio
async def test_prompt_preservation_without_user_content():
    """Test that prompts can be retrieved even without user content."""

    messages: list[ModelMessage] = [
        ModelRequest(
            parts=[
                AgentSystemPrompt(content="Agent instructions"),
                SystemStatusPrompt(content="System state info"),
            ]
        ),
        ModelResponse(parts=[TextPart(content="Ready")]),
    ]

    # Both prompts should be retrievable
    agent_prompt = get_agent_system_prompt(messages)
    assert agent_prompt == "Agent instructions"

    system_status = get_latest_system_status(messages)
    assert system_status == "System state info"
