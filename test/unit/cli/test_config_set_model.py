"""Tests for the config set-model CLI command."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from shotgun.agents.config.models import ModelName
from shotgun.cli.config import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _mock_config_manager():
    """Mock the config manager for all tests."""
    mock_manager = MagicMock()
    mock_manager.load = AsyncMock()
    mock_manager.update_selected_model = AsyncMock()
    with patch("shotgun.cli.config.get_config_manager", return_value=mock_manager):
        yield mock_manager


def _make_config(
    *,
    shotgun_api_key: str | None = None,
    openrouter_api_key: str | None = None,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
    google_api_key: str | None = None,
):
    """Create a mock ShotgunConfig with specified API keys."""
    from pydantic import SecretStr

    from shotgun.agents.config.models import ShotgunConfig

    config = ShotgunConfig(shotgun_instance_id="test-id")
    if shotgun_api_key:
        config.shotgun.api_key = SecretStr(shotgun_api_key)
    if openrouter_api_key:
        config.openrouter.api_key = SecretStr(openrouter_api_key)
    if openai_api_key:
        config.openai.api_key = SecretStr(openai_api_key)
    if anthropic_api_key:
        config.anthropic.api_key = SecretStr(anthropic_api_key)
    if google_api_key:
        config.google.api_key = SecretStr(google_api_key)
    return config


def test_set_model_valid_with_byok_key(_mock_config_manager):
    """Valid model with BYOK key succeeds."""
    config = _make_config(anthropic_api_key="sk-ant-test")
    _mock_config_manager.load.return_value = config

    result = runner.invoke(app, ["set-model", "claude-sonnet-4-6"])

    assert result.exit_code == 0
    assert "claude-sonnet-4-6" in result.output
    _mock_config_manager.update_selected_model.assert_called_once_with(
        ModelName.CLAUDE_SONNET_4_6
    )


def test_set_model_valid_with_shotgun_account_key(_mock_config_manager):
    """Valid model with Shotgun Account key succeeds."""
    config = _make_config(shotgun_api_key="sg-test-key")
    _mock_config_manager.load.return_value = config

    result = runner.invoke(app, ["set-model", "gpt-5.2"])

    assert result.exit_code == 0
    assert "gpt-5.2" in result.output
    _mock_config_manager.update_selected_model.assert_called_once_with(
        ModelName.GPT_5_2
    )


def test_set_model_valid_with_openrouter_key(_mock_config_manager):
    """Valid model with OpenRouter key succeeds."""
    config = _make_config(openrouter_api_key="or-test-key")
    _mock_config_manager.load.return_value = config

    result = runner.invoke(app, ["set-model", "claude-opus-4-6"])

    assert result.exit_code == 0
    assert "claude-opus-4-6" in result.output


def test_set_model_valid_with_env_var_key(_mock_config_manager):
    """Valid model with API key from env var succeeds."""
    config = _make_config()  # No config keys
    _mock_config_manager.load.return_value = config

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-env-test"}):
        result = runner.invoke(app, ["set-model", "claude-sonnet-4-6"])

    assert result.exit_code == 0
    assert "claude-sonnet-4-6" in result.output


def test_set_model_unknown_model_errors(_mock_config_manager):
    """Unknown model name produces error with valid model list."""
    result = runner.invoke(app, ["set-model", "fake-model-999"])

    assert result.exit_code == 1
    assert "Unknown model" in result.output
    assert "fake-model-999" in result.output
    # Should show valid model names
    assert "claude-sonnet-4-6" in result.output
    _mock_config_manager.update_selected_model.assert_not_called()


def test_set_model_no_api_key_errors(_mock_config_manager):
    """Valid model with no API key produces descriptive error."""
    config = _make_config()  # No keys at all
    _mock_config_manager.load.return_value = config

    with patch.dict("os.environ", {}, clear=True):
        result = runner.invoke(app, ["set-model", "claude-sonnet-4-6"])

    assert result.exit_code == 1
    assert "No API key available" in result.output
    assert "anthropic" in result.output
    _mock_config_manager.update_selected_model.assert_not_called()


def test_set_model_provider_prefixed_format(_mock_config_manager):
    """Provider-prefixed model name is accepted."""
    config = _make_config(anthropic_api_key="sk-ant-test")
    _mock_config_manager.load.return_value = config

    result = runner.invoke(app, ["set-model", "anthropic/claude-sonnet-4-6"])

    assert result.exit_code == 0
    assert "claude-sonnet-4-6" in result.output
    _mock_config_manager.update_selected_model.assert_called_once_with(
        ModelName.CLAUDE_SONNET_4_6
    )


def test_set_model_openrouter_env_var_key(_mock_config_manager):
    """Valid model with OPENROUTER_API_KEY env var succeeds."""
    config = _make_config()  # No config keys
    _mock_config_manager.load.return_value = config

    with patch.dict("os.environ", {"OPENROUTER_API_KEY": "or-env-test"}):
        result = runner.invoke(app, ["set-model", "gpt-5.2"])

    assert result.exit_code == 0
    assert "gpt-5.2" in result.output
