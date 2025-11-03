"""Test fixtures for TUI tests."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic_ai import RunContext

from shotgun.agents.agent_manager import AgentManager
from shotgun.agents.config.models import (
    KeyProvider,
    ModelConfig,
    ModelName,
    ProviderType,
)
from shotgun.agents.conversation_manager import ConversationManager
from shotgun.agents.models import AgentDeps, AgentType
from shotgun.codebase.service import CodebaseService
from shotgun.sdk.codebase import CodebaseSDK
from shotgun.tui.commands import CommandHandler
from shotgun.tui.state.processing_state import ProcessingStateManager
from shotgun.tui.utils.mode_progress import PlaceholderHints


@pytest.fixture
def mock_model_config():
    """Create a proper ModelConfig instance for testing."""
    return ModelConfig(
        name=ModelName.CLAUDE_SONNET_4_5,
        provider=ProviderType.ANTHROPIC,
        key_provider=KeyProvider.BYOK,
        max_input_tokens=200_000,
        max_output_tokens=16_000,
        api_key="test-api-key",
    )


@pytest.fixture
def mock_codebase_service(temp_storage_dir):
    """Create a real CodebaseService with temp storage for testing."""
    service = CodebaseService(temp_storage_dir / "codebases")
    return service


@pytest.fixture
def mock_agent_deps(mock_model_config, mock_codebase_service):
    """Create real AgentDeps for testing."""

    def _placeholder_system_prompt_fn(ctx: RunContext[AgentDeps]) -> str:
        return "Test system prompt"

    return AgentDeps(
        interactive_mode=True,
        is_tui_context=True,
        llm_model=mock_model_config,
        codebase_service=mock_codebase_service,
        system_prompt_fn=_placeholder_system_prompt_fn,
    )


@pytest.fixture
def mock_agent_manager(mock_agent_deps):
    """Create a mock AgentManager for testing."""
    manager = Mock(spec=AgentManager)
    manager.deps = mock_agent_deps
    manager.current_agent = Mock()
    manager.current_type = AgentType.RESEARCH
    manager.switch_agent = Mock()
    manager.run_agent = AsyncMock(return_value="Test response")
    return manager


@pytest.fixture
def mock_conversation_manager():
    """Create a mock ConversationManager for testing."""
    manager = Mock(spec=ConversationManager)
    manager.save = Mock()
    manager.load = Mock(return_value=None)
    manager.exists = Mock(return_value=False)
    return manager


@pytest.fixture
def mock_processing_state():
    """Create a mock ProcessingStateManager for testing."""
    state = Mock(spec=ProcessingStateManager)
    state.is_working = False
    state.start_processing = Mock()
    state.stop_processing = Mock()
    state.bind_worker = Mock()
    state.bind_spinner = Mock()
    state.cancel_current_operation = Mock(return_value=False)
    state.update_spinner_text = Mock()
    return state


@pytest.fixture
def mock_command_handler():
    """Create a mock CommandHandler for testing."""
    handler = Mock(spec=CommandHandler)
    handler.handle_command = AsyncMock(return_value=None)
    return handler


@pytest.fixture
def mock_placeholder_hints():
    """Create a mock PlaceholderHints for testing."""
    hints = Mock(spec=PlaceholderHints)
    hints.get_hints = Mock(return_value=["Hint 1", "Hint 2"])
    return hints


@pytest.fixture
def mock_codebase_sdk():
    """Create a mock CodebaseSDK for testing."""
    sdk = Mock(spec=CodebaseSDK)
    sdk.list_codebases_for_directory = AsyncMock(return_value=Mock(graphs=[]))
    sdk.delete_codebase = AsyncMock()
    return sdk
