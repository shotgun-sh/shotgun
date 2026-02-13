"""Unit tests for WelcomeMessage model and build_welcome_state function."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from shotgun.tui.screens.chat_screen.welcome_message import (
    WelcomeMessage,
    WelcomeWidget,
    build_welcome_state,
)


def test_welcome_message_defaults():
    """Test WelcomeMessage creation with defaults."""
    msg = WelcomeMessage()
    assert msg.kind == "welcome"
    assert msg.is_home_directory is False
    assert msg.is_indexed is False
    assert msg.has_context7_key is False
    assert msg.is_frontier_model is False
    assert msg.frontier_model_label == ""
    assert msg.frontier_model_name == ""
    assert msg.is_ollama is False
    assert msg.is_byok is False
    assert msg.is_shotgun_account is False
    assert msg.has_gemini_key is False


def test_welcome_message_all_flags():
    """Test WelcomeMessage with all flags set."""
    msg = WelcomeMessage(
        is_home_directory=True,
        is_indexed=True,
        has_context7_key=True,
        is_frontier_model=True,
        frontier_model_label="Select Opus 4.5",
        frontier_model_name="claude-opus-4-5",
        is_ollama=False,
        is_byok=True,
        is_shotgun_account=False,
        has_gemini_key=True,
    )
    assert msg.is_home_directory is True
    assert msg.is_indexed is True
    assert msg.has_context7_key is True
    assert msg.is_frontier_model is True
    assert msg.frontier_model_label == "Select Opus 4.5"
    assert msg.frontier_model_name == "claude-opus-4-5"


def test_welcome_message_serialization():
    """Test WelcomeMessage JSON serialization roundtrip."""
    msg = WelcomeMessage(
        is_indexed=True,
        has_context7_key=True,
        frontier_model_label="Select GPT-5.2",
    )
    data = msg.model_dump()
    assert data["kind"] == "welcome"
    assert data["is_indexed"] is True
    assert data["has_context7_key"] is True

    msg2 = WelcomeMessage.model_validate(data)
    assert msg2.is_indexed is True
    assert msg2.has_context7_key is True
    assert msg2.frontier_model_label == "Select GPT-5.2"


def test_welcome_widget_initialization():
    """Test WelcomeWidget can be initialized with a WelcomeMessage."""
    state = WelcomeMessage(is_indexed=True)
    widget = WelcomeWidget(state)
    assert widget.state.is_indexed is True


def _make_config(
    *,
    anthropic_key: str | None = None,
    openai_key: str | None = None,
    google_key: str | None = None,
    shotgun_key: str | None = None,
    context7_key: str | None = None,
    selected_model: str | None = None,
    ollama_enabled: bool = False,
):
    """Create a mock ShotgunConfig with given provider keys."""
    config = MagicMock()
    config.anthropic.api_key = SecretStr(anthropic_key) if anthropic_key else None
    config.openai.api_key = SecretStr(openai_key) if openai_key else None
    config.google.api_key = SecretStr(google_key) if google_key else None
    config.shotgun.api_key = SecretStr(shotgun_key) if shotgun_key else None
    config.context7.api_key = SecretStr(context7_key) if context7_key else None
    config.selected_model = selected_model
    config.ollama.enabled = ollama_enabled
    return config


@pytest.mark.anyio
async def test_build_welcome_state_byok_anthropic_frontier():
    """Test frontier model detection for BYOK with Anthropic key."""
    config = _make_config(anthropic_key="sk-ant-test")
    mock_cm = AsyncMock()
    mock_cm.load = AsyncMock(return_value=config)
    mock_cm._provider_has_api_key = MagicMock(return_value=False)

    mock_sdk_instance = AsyncMock()
    mock_result = MagicMock()
    mock_result.graphs = []
    mock_sdk_instance.list_codebases_for_directory = AsyncMock(return_value=mock_result)

    with (
        patch(
            "shotgun.agents.config.get_config_manager",
            return_value=mock_cm,
        ),
        patch(
            "shotgun.sdk.codebase.CodebaseSDK",
            return_value=mock_sdk_instance,
        ),
        patch(
            "shotgun.tui.screens.chat_screen.welcome_message._is_home_directory",
            return_value=False,
        ),
    ):
        state = await build_welcome_state()

    assert state.is_byok is True
    assert state.is_shotgun_account is False
    assert state.frontier_model_label == "Select Opus 4.5"
    assert state.frontier_model_name == "claude-opus-4-5"
    assert state.is_frontier_model is False


@pytest.mark.anyio
async def test_build_welcome_state_byok_openai_frontier():
    """Test frontier model detection for BYOK with only OpenAI key."""
    config = _make_config(openai_key="sk-openai-test")
    mock_cm = AsyncMock()
    mock_cm.load = AsyncMock(return_value=config)
    mock_cm._provider_has_api_key = MagicMock(return_value=False)

    mock_sdk_instance = AsyncMock()
    mock_result = MagicMock()
    mock_result.graphs = []
    mock_sdk_instance.list_codebases_for_directory = AsyncMock(return_value=mock_result)

    with (
        patch(
            "shotgun.agents.config.get_config_manager",
            return_value=mock_cm,
        ),
        patch(
            "shotgun.sdk.codebase.CodebaseSDK",
            return_value=mock_sdk_instance,
        ),
        patch(
            "shotgun.tui.screens.chat_screen.welcome_message._is_home_directory",
            return_value=False,
        ),
    ):
        state = await build_welcome_state()

    assert state.frontier_model_label == "Select GPT-5.2"
    assert state.frontier_model_name == "gpt-5.2"


@pytest.mark.anyio
async def test_build_welcome_state_byok_google_frontier():
    """Test frontier model detection for BYOK with only Google key."""
    config = _make_config(google_key="google-test")
    mock_cm = AsyncMock()
    mock_cm.load = AsyncMock(return_value=config)
    mock_cm._provider_has_api_key = MagicMock(return_value=False)

    mock_sdk_instance = AsyncMock()
    mock_result = MagicMock()
    mock_result.graphs = []
    mock_sdk_instance.list_codebases_for_directory = AsyncMock(return_value=mock_result)

    with (
        patch(
            "shotgun.agents.config.get_config_manager",
            return_value=mock_cm,
        ),
        patch(
            "shotgun.sdk.codebase.CodebaseSDK",
            return_value=mock_sdk_instance,
        ),
        patch(
            "shotgun.tui.screens.chat_screen.welcome_message._is_home_directory",
            return_value=False,
        ),
    ):
        state = await build_welcome_state()

    assert state.frontier_model_label == "Select Gemini 3 Pro"
    assert state.frontier_model_name == "gemini-3-pro-preview"
    assert state.has_gemini_key is True


@pytest.mark.anyio
async def test_build_welcome_state_shotgun_account():
    """Test shotgun account always suggests Opus 4.5."""
    config = _make_config(shotgun_key="shotgun-test")
    mock_cm = AsyncMock()
    mock_cm.load = AsyncMock(return_value=config)
    mock_cm._provider_has_api_key = MagicMock(return_value=True)

    mock_sdk_instance = AsyncMock()
    mock_result = MagicMock()
    mock_result.graphs = []
    mock_sdk_instance.list_codebases_for_directory = AsyncMock(return_value=mock_result)

    with (
        patch(
            "shotgun.agents.config.get_config_manager",
            return_value=mock_cm,
        ),
        patch(
            "shotgun.sdk.codebase.CodebaseSDK",
            return_value=mock_sdk_instance,
        ),
        patch(
            "shotgun.tui.screens.chat_screen.welcome_message._is_home_directory",
            return_value=False,
        ),
    ):
        state = await build_welcome_state()

    assert state.is_shotgun_account is True
    assert state.frontier_model_label == "Select Opus 4.5"
    assert state.frontier_model_name == "claude-opus-4-5"


@pytest.mark.anyio
async def test_build_welcome_state_ollama_hides_model():
    """Test that Ollama mode hides frontier model selection."""
    config = _make_config(ollama_enabled=True)
    mock_cm = AsyncMock()
    mock_cm.load = AsyncMock(return_value=config)
    mock_cm._provider_has_api_key = MagicMock(return_value=False)

    mock_sdk_instance = AsyncMock()
    mock_result = MagicMock()
    mock_result.graphs = []
    mock_sdk_instance.list_codebases_for_directory = AsyncMock(return_value=mock_result)

    with (
        patch(
            "shotgun.agents.config.get_config_manager",
            return_value=mock_cm,
        ),
        patch(
            "shotgun.sdk.codebase.CodebaseSDK",
            return_value=mock_sdk_instance,
        ),
        patch(
            "shotgun.tui.screens.chat_screen.welcome_message._is_home_directory",
            return_value=False,
        ),
    ):
        state = await build_welcome_state()

    assert state.is_ollama is True
    assert state.frontier_model_label == ""
    assert state.frontier_model_name == ""


@pytest.mark.anyio
async def test_build_welcome_state_home_directory():
    """Test home directory detection."""
    config = _make_config()
    mock_cm = AsyncMock()
    mock_cm.load = AsyncMock(return_value=config)
    mock_cm._provider_has_api_key = MagicMock(return_value=False)

    with (
        patch(
            "shotgun.agents.config.get_config_manager",
            return_value=mock_cm,
        ),
        patch(
            "shotgun.tui.screens.chat_screen.welcome_message._is_home_directory",
            return_value=True,
        ),
    ):
        state = await build_welcome_state()

    assert state.is_home_directory is True
    assert state.is_indexed is False


@pytest.mark.anyio
async def test_build_welcome_state_indexed_codebase():
    """Test detection of already-indexed codebase."""
    config = _make_config(anthropic_key="sk-ant-test")
    mock_cm = AsyncMock()
    mock_cm.load = AsyncMock(return_value=config)
    mock_cm._provider_has_api_key = MagicMock(return_value=False)

    mock_sdk_instance = AsyncMock()
    mock_result = MagicMock()
    mock_result.graphs = [MagicMock()]  # Non-empty = indexed
    mock_sdk_instance.list_codebases_for_directory = AsyncMock(return_value=mock_result)

    with (
        patch(
            "shotgun.agents.config.get_config_manager",
            return_value=mock_cm,
        ),
        patch(
            "shotgun.sdk.codebase.CodebaseSDK",
            return_value=mock_sdk_instance,
        ),
        patch(
            "shotgun.tui.screens.chat_screen.welcome_message._is_home_directory",
            return_value=False,
        ),
    ):
        state = await build_welcome_state()

    assert state.is_indexed is True


@pytest.mark.anyio
async def test_build_welcome_state_context7_key():
    """Test Context7 key detection."""
    config = _make_config(anthropic_key="sk-ant-test", context7_key="ctx7-test")
    mock_cm = AsyncMock()
    mock_cm.load = AsyncMock(return_value=config)
    mock_cm._provider_has_api_key = MagicMock(return_value=False)

    mock_sdk_instance = AsyncMock()
    mock_result = MagicMock()
    mock_result.graphs = []
    mock_sdk_instance.list_codebases_for_directory = AsyncMock(return_value=mock_result)

    with (
        patch(
            "shotgun.agents.config.get_config_manager",
            return_value=mock_cm,
        ),
        patch(
            "shotgun.sdk.codebase.CodebaseSDK",
            return_value=mock_sdk_instance,
        ),
        patch(
            "shotgun.tui.screens.chat_screen.welcome_message._is_home_directory",
            return_value=False,
        ),
    ):
        state = await build_welcome_state()

    assert state.has_context7_key is True


@pytest.mark.anyio
async def test_build_welcome_state_already_frontier():
    """Test already-selected frontier model is detected."""
    config = _make_config(anthropic_key="sk-ant-test", selected_model="claude-opus-4-5")
    mock_cm = AsyncMock()
    mock_cm.load = AsyncMock(return_value=config)
    mock_cm._provider_has_api_key = MagicMock(return_value=False)

    mock_sdk_instance = AsyncMock()
    mock_result = MagicMock()
    mock_result.graphs = []
    mock_sdk_instance.list_codebases_for_directory = AsyncMock(return_value=mock_result)

    with (
        patch(
            "shotgun.agents.config.get_config_manager",
            return_value=mock_cm,
        ),
        patch(
            "shotgun.sdk.codebase.CodebaseSDK",
            return_value=mock_sdk_instance,
        ),
        patch(
            "shotgun.tui.screens.chat_screen.welcome_message._is_home_directory",
            return_value=False,
        ),
    ):
        state = await build_welcome_state()

    assert state.is_frontier_model is True


@pytest.mark.anyio
async def test_build_welcome_state_byok_shows_gemini():
    """Test BYOK mode shows Gemini item."""
    config = _make_config(anthropic_key="sk-ant-test")
    mock_cm = AsyncMock()
    mock_cm.load = AsyncMock(return_value=config)
    mock_cm._provider_has_api_key = MagicMock(return_value=False)

    mock_sdk_instance = AsyncMock()
    mock_result = MagicMock()
    mock_result.graphs = []
    mock_sdk_instance.list_codebases_for_directory = AsyncMock(return_value=mock_result)

    with (
        patch(
            "shotgun.agents.config.get_config_manager",
            return_value=mock_cm,
        ),
        patch(
            "shotgun.sdk.codebase.CodebaseSDK",
            return_value=mock_sdk_instance,
        ),
        patch(
            "shotgun.tui.screens.chat_screen.welcome_message._is_home_directory",
            return_value=False,
        ),
    ):
        state = await build_welcome_state()

    assert state.is_byok is True
    assert state.has_gemini_key is False


@pytest.mark.anyio
async def test_build_welcome_state_frontier_priority():
    """Test frontier model priority: Anthropic > OpenAI > Google."""
    # With both Anthropic and OpenAI keys, should prefer Anthropic
    config = _make_config(anthropic_key="sk-ant-test", openai_key="sk-openai-test")
    mock_cm = AsyncMock()
    mock_cm.load = AsyncMock(return_value=config)
    mock_cm._provider_has_api_key = MagicMock(return_value=False)

    mock_sdk_instance = AsyncMock()
    mock_result = MagicMock()
    mock_result.graphs = []
    mock_sdk_instance.list_codebases_for_directory = AsyncMock(return_value=mock_result)

    with (
        patch(
            "shotgun.agents.config.get_config_manager",
            return_value=mock_cm,
        ),
        patch(
            "shotgun.sdk.codebase.CodebaseSDK",
            return_value=mock_sdk_instance,
        ),
        patch(
            "shotgun.tui.screens.chat_screen.welcome_message._is_home_directory",
            return_value=False,
        ),
    ):
        state = await build_welcome_state()

    assert state.frontier_model_label == "Select Opus 4.5"
    assert state.frontier_model_name == "claude-opus-4-5"
