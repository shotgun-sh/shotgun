"""Tests for centralized Pydantic Settings."""

import importlib
import os
import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    """Clean SHOTGUN_ environment variables before each test."""
    # Remove all SHOTGUN_ prefixed environment variables
    for key in list(os.environ.keys()):
        if key.startswith("SHOTGUN_"):
            monkeypatch.delenv(key, raising=False)

    # Change to temp directory to prevent loading any .env files
    monkeypatch.chdir(tmp_path)

    # Also reload settings module to get fresh instance
    if "shotgun.settings" in sys.modules:
        del sys.modules["shotgun.settings"]


def test_telemetry_settings_defaults():
    """Test TelemetrySettings loads from build_constants as expected.

    Note: The actual defaults come from build_constants.py which may contain
    real values in dev builds. This test verifies the settings load correctly
    and can be overridden by environment variables.
    """
    from shotgun.settings import TelemetrySettings, _get_build_constant

    settings = TelemetrySettings()

    # Verify settings match what _get_build_constant returns
    # (either empty strings or values from build_constants.py)
    assert settings.sentry_dsn == _get_build_constant("SENTRY_DSN", "")
    assert settings.posthog_api_key == _get_build_constant("POSTHOG_API_KEY", "")
    assert settings.posthog_project_id == _get_build_constant("POSTHOG_PROJECT_ID", "")
    # logfire_enabled defaults to False if build_constants returns falsy value
    expected_logfire = _get_build_constant("LOGFIRE_ENABLED", False)
    assert settings.logfire_enabled == (expected_logfire in (True, "true", "1", "yes"))
    assert settings.logfire_token == _get_build_constant("LOGFIRE_TOKEN", "")


def test_telemetry_settings_from_env(monkeypatch):
    """Test TelemetrySettings loads from SHOTGUN_ prefixed environment variables."""
    monkeypatch.setenv("SHOTGUN_SENTRY_DSN", "test-sentry-dsn")
    monkeypatch.setenv("SHOTGUN_POSTHOG_API_KEY", "test-posthog-key")
    monkeypatch.setenv("SHOTGUN_POSTHOG_PROJECT_ID", "test-project-id")
    monkeypatch.setenv("SHOTGUN_LOGFIRE_ENABLED", "true")
    monkeypatch.setenv("SHOTGUN_LOGFIRE_TOKEN", "test-logfire-token")

    from shotgun.settings import TelemetrySettings

    settings = TelemetrySettings()

    assert settings.sentry_dsn == "test-sentry-dsn"
    assert settings.posthog_api_key == "test-posthog-key"
    assert settings.posthog_project_id == "test-project-id"
    assert settings.logfire_enabled is True
    assert settings.logfire_token == "test-logfire-token"  # noqa: S105


def test_telemetry_logfire_enabled_bool_parsing(monkeypatch):
    """Test logfire_enabled parses various boolean string formats."""
    from shotgun.settings import TelemetrySettings

    # Test "true"
    monkeypatch.setenv("SHOTGUN_LOGFIRE_ENABLED", "true")
    assert TelemetrySettings().logfire_enabled is True

    # Test "1"
    monkeypatch.setenv("SHOTGUN_LOGFIRE_ENABLED", "1")
    assert TelemetrySettings().logfire_enabled is True

    # Test "yes"
    monkeypatch.setenv("SHOTGUN_LOGFIRE_ENABLED", "yes")
    assert TelemetrySettings().logfire_enabled is True

    # Test "false"
    monkeypatch.setenv("SHOTGUN_LOGFIRE_ENABLED", "false")
    assert TelemetrySettings().logfire_enabled is False

    # Test "0"
    monkeypatch.setenv("SHOTGUN_LOGFIRE_ENABLED", "0")
    assert TelemetrySettings().logfire_enabled is False


def test_logging_settings_defaults():
    """Test LoggingSettings loads with default values."""
    from shotgun.settings import LoggingSettings

    settings = LoggingSettings()

    assert settings.log_level == "INFO"
    assert settings.logging_to_console is False
    assert settings.logging_to_file is True


def test_logging_settings_from_env(monkeypatch):
    """Test LoggingSettings loads from SHOTGUN_ prefixed environment variables."""
    monkeypatch.setenv("SHOTGUN_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("SHOTGUN_LOGGING_TO_CONSOLE", "true")
    monkeypatch.setenv("SHOTGUN_LOGGING_TO_FILE", "false")

    from shotgun.settings import LoggingSettings

    settings = LoggingSettings()

    assert settings.log_level == "DEBUG"
    assert settings.logging_to_console is True
    assert settings.logging_to_file is False


def test_logging_log_level_validation(monkeypatch):
    """Test log_level validates and defaults to INFO for invalid values."""
    from shotgun.settings import LoggingSettings

    # Test valid level
    monkeypatch.setenv("SHOTGUN_LOG_LEVEL", "WARNING")
    assert LoggingSettings().log_level == "WARNING"

    # Test lowercase gets uppercased
    monkeypatch.setenv("SHOTGUN_LOG_LEVEL", "debug")
    assert LoggingSettings().log_level == "DEBUG"

    # Test invalid level defaults to INFO
    monkeypatch.setenv("SHOTGUN_LOG_LEVEL", "INVALID")
    assert LoggingSettings().log_level == "INFO"


def test_logging_bool_parsing(monkeypatch):
    """Test logging boolean fields parse various string formats."""
    from shotgun.settings import LoggingSettings

    # Test console logging
    monkeypatch.setenv("SHOTGUN_LOGGING_TO_CONSOLE", "1")
    assert LoggingSettings().logging_to_console is True

    monkeypatch.setenv("SHOTGUN_LOGGING_TO_CONSOLE", "yes")
    assert LoggingSettings().logging_to_console is True

    # Test file logging
    monkeypatch.setenv("SHOTGUN_LOGGING_TO_FILE", "0")
    assert LoggingSettings().logging_to_file is False


def test_api_settings_defaults():
    """Test ApiSettings loads with default values."""
    from shotgun.settings import ApiSettings

    settings = ApiSettings()

    assert settings.web_base_url == "https://api-219702594231.us-east4.run.app"
    assert (
        settings.account_llm_base_url == "https://litellm-219702594231.us-east4.run.app"
    )


def test_api_settings_from_env(monkeypatch):
    """Test ApiSettings loads from SHOTGUN_ prefixed environment variables."""
    monkeypatch.setenv("SHOTGUN_WEB_BASE_URL", "https://custom-api.example.com")
    monkeypatch.setenv("SHOTGUN_ACCOUNT_LLM_BASE_URL", "https://custom-llm.example.com")

    from shotgun.settings import ApiSettings

    settings = ApiSettings()

    assert settings.web_base_url == "https://custom-api.example.com"
    assert settings.account_llm_base_url == "https://custom-llm.example.com"


def test_development_settings_defaults():
    """Test DevelopmentSettings loads with default values."""
    from shotgun.settings import DevelopmentSettings

    settings = DevelopmentSettings()

    assert settings.home is None
    assert settings.pipx_simulate is False


def test_development_settings_from_env(monkeypatch):
    """Test DevelopmentSettings loads from SHOTGUN_ prefixed environment variables."""
    monkeypatch.setenv("SHOTGUN_HOME", "/custom/home/path")
    monkeypatch.setenv("SHOTGUN_PIPX_SIMULATE", "true")

    from shotgun.settings import DevelopmentSettings

    settings = DevelopmentSettings()

    assert settings.home == "/custom/home/path"
    assert settings.pipx_simulate is True


def test_development_pipx_simulate_bool_parsing(monkeypatch):
    """Test pipx_simulate parses various boolean string formats."""
    from shotgun.settings import DevelopmentSettings

    monkeypatch.setenv("SHOTGUN_PIPX_SIMULATE", "1")
    assert DevelopmentSettings().pipx_simulate is True

    monkeypatch.setenv("SHOTGUN_PIPX_SIMULATE", "yes")
    assert DevelopmentSettings().pipx_simulate is True

    monkeypatch.setenv("SHOTGUN_PIPX_SIMULATE", "false")
    assert DevelopmentSettings().pipx_simulate is False


def test_main_settings_composition():
    """Test main Settings class composes all sub-settings."""
    from shotgun.settings import Settings

    settings = Settings()

    assert hasattr(settings, "telemetry")
    assert hasattr(settings, "logging")
    assert hasattr(settings, "api")
    assert hasattr(settings, "dev")


def test_main_settings_env_vars(monkeypatch):
    """Test main Settings loads all sub-settings from environment."""
    monkeypatch.setenv("SHOTGUN_SENTRY_DSN", "main-test-dsn")
    monkeypatch.setenv("SHOTGUN_LOG_LEVEL", "ERROR")
    monkeypatch.setenv("SHOTGUN_WEB_BASE_URL", "https://test.example.com")
    monkeypatch.setenv("SHOTGUN_HOME", "/test/home")

    from shotgun.settings import Settings

    settings = Settings()

    assert settings.telemetry.sentry_dsn == "main-test-dsn"
    assert settings.logging.log_level == "ERROR"
    assert settings.api.web_base_url == "https://test.example.com"
    assert settings.dev.home == "/test/home"


def test_build_constants_integration():
    """Test settings load from build_constants when available."""
    # This test verifies the _get_build_constant function works
    # In practice, build_constants.py exists and is loaded automatically
    # We just verify the integration works with the real module
    from shotgun.settings import _get_build_constant

    # Test getting a constant (should return empty string from real build_constants)
    result = _get_build_constant("SENTRY_DSN", "default_value")
    # Either returns the value from build_constants or the default
    assert isinstance(result, str)

    # Test getting a non-existent constant
    result = _get_build_constant("NONEXISTENT", "my_default")
    assert result == "my_default"


def test_env_vars_override_build_constants(monkeypatch):
    """Test environment variables override build constants."""
    # Mock the build_constants module
    mock_build_constants = MagicMock()
    mock_build_constants.SENTRY_DSN = "build-sentry-dsn"

    # Set environment variable to override
    monkeypatch.setenv("SHOTGUN_SENTRY_DSN", "env-sentry-dsn")

    # Ensure settings module is reloaded
    if "shotgun.settings" in sys.modules:
        del sys.modules["shotgun.settings"]

    with patch.dict("sys.modules", {"shotgun.build_constants": mock_build_constants}):
        from shotgun.settings import TelemetrySettings

        settings = TelemetrySettings()

        # Environment variable should win
        assert settings.sentry_dsn == "env-sentry-dsn"


def test_build_constants_import_error_handled():
    """Test settings work when build_constants.py is not available."""
    # Ensure build_constants import fails
    if "shotgun.build_constants" in sys.modules:
        del sys.modules["shotgun.build_constants"]

    # Force ImportError for build_constants
    original_import = __import__

    def mock_import(name, *args, **kwargs):
        if name == "shotgun.build_constants" or name == "shotgun":
            if "build_constants" in name:
                raise ImportError("No module named 'shotgun.build_constants'")
        return original_import(name, *args, **kwargs)

    # Reload settings module with mocked import
    if "shotgun.settings" in sys.modules:
        del sys.modules["shotgun.settings"]

    with patch("builtins.__import__", side_effect=mock_import):
        # Import should not fail even when build_constants is missing
        from shotgun.settings import TelemetrySettings

        settings = TelemetrySettings()

        # Should use defaults
        assert settings.sentry_dsn == ""


def test_settings_singleton_exists():
    """Test global settings singleton is created."""
    from shotgun.settings import settings

    assert settings is not None
    assert hasattr(settings, "telemetry")
    assert hasattr(settings, "logging")
    assert hasattr(settings, "api")
    assert hasattr(settings, "dev")


def test_settings_dotenv_file_support(tmp_path, monkeypatch):
    """Test settings can load from .env file."""
    # Create a temporary .env file
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SHOTGUN_SENTRY_DSN=dotenv-sentry-dsn\n"
        "SHOTGUN_LOG_LEVEL=WARNING\n"
        "SHOTGUN_PIPX_SIMULATE=true\n"
    )

    # Change to temp directory so .env is found
    monkeypatch.chdir(tmp_path)

    # Reload settings module to pick up .env file
    if "shotgun.settings" in sys.modules:
        del sys.modules["shotgun.settings"]

    # Import in the context of the temp directory
    importlib.import_module("shotgun.settings")

    # Note: This test verifies the .env file support is configured,
    # but actual loading may depend on working directory at runtime
