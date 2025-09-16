"""Configuration manager for Shotgun CLI."""

import json
from pathlib import Path
from typing import Any

from pydantic import SecretStr

from shotgun.logging_config import setup_logger

from .models import ProviderType, ShotgunConfig

logger = setup_logger(__name__)


def get_shotgun_home() -> Path:
    """Get the Shotgun home directory path.

    Can be overridden with SHOTGUN_HOME environment variable for testing.

    Returns:
        Path to shotgun home directory (default: ~/.shotgun-sh/)
    """
    import os

    # Allow override via environment variable (useful for testing)
    if custom_home := os.environ.get("SHOTGUN_HOME"):
        return Path(custom_home)

    return Path.home() / ".shotgun-sh"


class ConfigManager:
    """Manager for Shotgun configuration."""

    def __init__(self, config_path: Path | None = None):
        """Initialize ConfigManager.

        Args:
            config_path: Path to config file. If None, uses default ~/.shotgun-sh/config.json
        """
        if config_path is None:
            self.config_path = get_shotgun_home() / "config.json"
        else:
            self.config_path = config_path

        self._config: ShotgunConfig | None = None

    def load(self) -> ShotgunConfig:
        """Load configuration from file.

        Returns:
            ShotgunConfig: Loaded configuration or default config if file doesn't exist
        """
        if self._config is not None:
            return self._config

        if not self.config_path.exists():
            logger.info(
                "Configuration file not found, using defaults: %s", self.config_path
            )
            self._config = ShotgunConfig()
            return self._config

        try:
            with open(self.config_path, encoding="utf-8") as f:
                data = json.load(f)

            # Convert plain text secrets to SecretStr objects
            self._convert_secrets_to_secretstr(data)

            self._config = ShotgunConfig.model_validate(data)
            logger.debug("Configuration loaded successfully from %s", self.config_path)
            return self._config

        except Exception as e:
            logger.error(
                "Failed to load configuration from %s: %s", self.config_path, e
            )
            logger.info("Using default configuration")
            self._config = ShotgunConfig()
            return self._config

    def save(self, config: ShotgunConfig | None = None) -> None:
        """Save configuration to file.

        Args:
            config: Configuration to save. If None, saves current loaded config
        """
        if config is None:
            config = self._config or ShotgunConfig()

        # Ensure directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Convert SecretStr to plain text for JSON serialization
            data = config.model_dump()
            self._convert_secretstr_to_plain(data)

            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.debug("Configuration saved to %s", self.config_path)
            self._config = config

        except Exception as e:
            logger.error("Failed to save configuration to %s: %s", self.config_path, e)
            raise

    def update_provider(self, provider: ProviderType | str, **kwargs: Any) -> None:
        """Update provider configuration.

        Args:
            provider: Provider to update
            **kwargs: Configuration fields to update (only api_key supported)
        """
        config = self.load()
        # Convert string to ProviderType enum if needed
        provider_enum = (
            provider if isinstance(provider, ProviderType) else ProviderType(provider)
        )

        if provider_enum == ProviderType.OPENAI:
            provider_config = config.openai
        elif provider_enum == ProviderType.ANTHROPIC:
            provider_config = config.anthropic  # type: ignore[assignment]
        elif provider_enum == ProviderType.GOOGLE:
            provider_config = config.google  # type: ignore[assignment]
        else:
            raise ValueError(f"Unsupported provider: {provider_enum}")

        # Only support api_key updates
        if "api_key" in kwargs and kwargs["api_key"] is not None:
            provider_config.api_key = SecretStr(kwargs["api_key"])

        # Reject other fields
        unsupported_fields = set(kwargs.keys()) - {"api_key"}
        if unsupported_fields:
            raise ValueError(f"Unsupported configuration fields: {unsupported_fields}")

        self.save(config)

    def initialize(self) -> ShotgunConfig:
        """Initialize configuration with defaults and save to file.

        Returns:
            Default ShotgunConfig
        """
        config = ShotgunConfig()
        self.save(config)
        logger.info("Configuration initialized at %s", self.config_path)
        return config

    def _convert_secrets_to_secretstr(self, data: dict[str, Any]) -> None:
        """Convert plain text secrets in data to SecretStr objects."""
        for provider in ["openai", "anthropic", "google"]:
            if provider in data and isinstance(data[provider], dict):
                if (
                    "api_key" in data[provider]
                    and data[provider]["api_key"] is not None
                ):
                    data[provider]["api_key"] = SecretStr(data[provider]["api_key"])

    def _convert_secretstr_to_plain(self, data: dict[str, Any]) -> None:
        """Convert SecretStr objects in data to plain text for JSON serialization."""
        for provider in ["openai", "anthropic", "google"]:
            if provider in data and isinstance(data[provider], dict):
                if (
                    "api_key" in data[provider]
                    and data[provider]["api_key"] is not None
                ):
                    if hasattr(data[provider]["api_key"], "get_secret_value"):
                        data[provider]["api_key"] = data[provider][
                            "api_key"
                        ].get_secret_value()


def get_config_manager() -> ConfigManager:
    """Get the global ConfigManager instance."""
    return ConfigManager()
