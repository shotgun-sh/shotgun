"""Centralized application settings using Pydantic Settings.

All environment variables use the SHOTGUN_ prefix to avoid conflicts with other tools.
Settings are loaded with the following priority:
1. Environment variables (highest priority)
2. Build constants (embedded at build time)
3. Default values (lowest priority)

Example usage:
    from shotgun.settings import settings

    # Access telemetry settings
    if settings.telemetry.sentry_dsn:
        sentry_sdk.init(dsn=settings.telemetry.sentry_dsn)

    # Access logging settings
    logger.setLevel(settings.logging.log_level)

    # Access API settings
    response = httpx.get(settings.api.web_base_url)
"""

from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_build_constant(name: str, default: Any = None) -> Any:
    """Get a value from build_constants.py, falling back to default.

    Args:
        name: The constant name to retrieve (e.g., "SENTRY_DSN")
        default: Default value if constant not found

    Returns:
        The constant value, or default if not found/import fails
    """
    try:
        from shotgun import build_constants

        return getattr(build_constants, name, default)
    except ImportError:
        return default


class TelemetrySettings(BaseSettings):
    """Telemetry and observability settings.

    These settings control error tracking (Sentry), analytics (PostHog),
    and observability (Logfire) integrations.
    """

    sentry_dsn: str = Field(
        default_factory=lambda: _get_build_constant("SENTRY_DSN", ""),
        description="Sentry DSN for error tracking",
    )
    posthog_api_key: str = Field(
        default_factory=lambda: _get_build_constant("POSTHOG_API_KEY", ""),
        description="PostHog API key for analytics",
    )
    posthog_project_id: str = Field(
        default_factory=lambda: _get_build_constant("POSTHOG_PROJECT_ID", ""),
        description="PostHog project ID",
    )
    logfire_enabled: bool = Field(
        default_factory=lambda: _get_build_constant("LOGFIRE_ENABLED", False),
        description="Enable Logfire observability (dev builds only)",
    )
    logfire_token: str = Field(
        default_factory=lambda: _get_build_constant("LOGFIRE_TOKEN", ""),
        description="Logfire authentication token",
    )

    model_config = SettingsConfigDict(
        env_prefix="SHOTGUN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("logfire_enabled", mode="before")
    @classmethod
    def parse_bool(cls, v: Any) -> bool:
        """Parse boolean values from strings (matches is_truthy behavior)."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return bool(v)


class LoggingSettings(BaseSettings):
    """Logging configuration settings.

    Controls log level, console output, and file logging behavior.
    """

    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    logging_to_console: bool = Field(
        default=False,
        description="Enable console logging output",
    )
    logging_to_file: bool = Field(
        default=True,
        description="Enable file logging output",
    )

    model_config = SettingsConfigDict(
        env_prefix="SHOTGUN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is one of the allowed values."""
        v = v.upper()
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v not in valid_levels:
            return "INFO"  # Default to INFO if invalid
        return v

    @field_validator("logging_to_console", "logging_to_file", mode="before")
    @classmethod
    def parse_bool(cls, v: Any) -> bool:
        """Parse boolean values from strings (matches is_truthy behavior)."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return bool(v)


class ApiSettings(BaseSettings):
    """API endpoint settings.

    Configuration for Shotgun backend services.
    """

    web_base_url: str = Field(
        default="https://api-219702594231.us-east4.run.app",
        description="Shotgun Web API base URL (authentication/subscription)",
    )
    account_llm_base_url: str = Field(
        default="https://litellm-219702594231.us-east4.run.app",
        description="Shotgun's LiteLLM proxy base URL (AI model requests)",
    )

    model_config = SettingsConfigDict(
        env_prefix="SHOTGUN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class DevelopmentSettings(BaseSettings):
    """Development and testing settings.

    These settings are primarily used for testing and development purposes.
    """

    home: str | None = Field(
        default=None,
        description="Override Shotgun home directory (for testing)",
    )
    pipx_simulate: bool = Field(
        default=False,
        description="Simulate pipx installation (for testing)",
    )

    model_config = SettingsConfigDict(
        env_prefix="SHOTGUN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("pipx_simulate", mode="before")
    @classmethod
    def parse_bool(cls, v: Any) -> bool:
        """Parse boolean values from strings (matches is_truthy behavior)."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return bool(v)


class Settings(BaseSettings):
    """Main application settings with SHOTGUN_ prefix.

    This is the main settings class that composes all other settings groups.
    Access settings via the global `settings` singleton instance.

    Example:
        from shotgun.settings import settings

        # Telemetry settings
        settings.telemetry.sentry_dsn
        settings.telemetry.posthog_api_key
        settings.telemetry.logfire_enabled

        # Logging settings
        settings.logging.log_level
        settings.logging.logging_to_console

        # API settings
        settings.api.web_base_url
        settings.api.account_llm_base_url

        # Development settings
        settings.dev.home
        settings.dev.pipx_simulate
    """

    telemetry: TelemetrySettings = Field(default_factory=TelemetrySettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)
    dev: DevelopmentSettings = Field(default_factory=DevelopmentSettings)

    model_config = SettingsConfigDict(
        env_prefix="SHOTGUN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Global settings singleton
# Import this in your modules: from shotgun.settings import settings
settings = Settings()
