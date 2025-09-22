"""Configuration manager for Shotgun CLI."""

import json
import os
import uuid
from pathlib import Path
from typing import Any

from pydantic import SecretStr

from shotgun.logging_config import get_logger
from shotgun.utils import get_shotgun_home

from .constants import (
    ANTHROPIC_API_KEY_ENV,
    ANTHROPIC_PROVIDER,
    API_KEY_FIELD,
    GEMINI_API_KEY_ENV,
    GOOGLE_PROVIDER,
    OPENAI_API_KEY_ENV,
    OPENAI_PROVIDER,
)
from .models import ProviderType, ShotgunConfig

logger = get_logger(__name__)


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
                "Configuration file not found, creating new config with user_id: %s",
                self.config_path,
            )
            # Create new config with generated user_id
            self._config = self.initialize()
            return self._config

        try:
            with open(self.config_path, encoding="utf-8") as f:
                data = json.load(f)

            # Convert plain text secrets to SecretStr objects
            self._convert_secrets_to_secretstr(data)

            self._config = ShotgunConfig.model_validate(data)
            logger.debug("Configuration loaded successfully from %s", self.config_path)

            # Check if the default provider has a key, if not find one that does
            if not self.has_provider_key(self._config.default_provider):
                original_default = self._config.default_provider
                # Find first provider with a configured key
                for provider in ProviderType:
                    if self.has_provider_key(provider):
                        logger.info(
                            "Default provider %s has no API key, updating to %s",
                            original_default.value,
                            provider.value,
                        )
                        self._config.default_provider = provider
                        self.save(self._config)
                        break

            return self._config

        except Exception as e:
            logger.error(
                "Failed to load configuration from %s: %s", self.config_path, e
            )
            logger.info("Creating new configuration with generated user_id")
            self._config = self.initialize()
            return self._config

    def save(self, config: ShotgunConfig | None = None) -> None:
        """Save configuration to file.

        Args:
            config: Configuration to save. If None, saves current loaded config
        """
        if config is None:
            if self._config:
                config = self._config
            else:
                # Create a new config with generated user_id
                config = ShotgunConfig(
                    user_id=str(uuid.uuid4()),
                    config_version=1,
                )

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
        provider_enum = self._ensure_provider_enum(provider)
        provider_config = self._get_provider_config(config, provider_enum)

        # Only support api_key updates
        if API_KEY_FIELD in kwargs:
            api_key_value = kwargs[API_KEY_FIELD]
            provider_config.api_key = (
                SecretStr(api_key_value) if api_key_value is not None else None
            )

        # Reject other fields
        unsupported_fields = set(kwargs.keys()) - {API_KEY_FIELD}
        if unsupported_fields:
            raise ValueError(f"Unsupported configuration fields: {unsupported_fields}")

        # If no other providers have keys configured and we just added one,
        # set this provider as the default
        if API_KEY_FIELD in kwargs and api_key_value is not None:
            other_providers = [p for p in ProviderType if p != provider_enum]
            has_other_keys = any(self.has_provider_key(p) for p in other_providers)
            if not has_other_keys:
                config.default_provider = provider_enum

        self.save(config)

    def clear_provider_key(self, provider: ProviderType | str) -> None:
        """Remove the API key for the given provider."""
        config = self.load()
        provider_enum = self._ensure_provider_enum(provider)
        provider_config = self._get_provider_config(config, provider_enum)
        provider_config.api_key = None
        self.save(config)

    def has_provider_key(self, provider: ProviderType | str) -> bool:
        """Check if the given provider has a non-empty API key configured.

        This checks both the configuration file and environment variables.
        """
        config = self.load()
        provider_enum = self._ensure_provider_enum(provider)
        provider_config = self._get_provider_config(config, provider_enum)

        # Check config first
        if self._provider_has_api_key(provider_config):
            return True

        # Check environment variable
        if provider_enum == ProviderType.OPENAI:
            return bool(os.getenv(OPENAI_API_KEY_ENV))
        elif provider_enum == ProviderType.ANTHROPIC:
            return bool(os.getenv(ANTHROPIC_API_KEY_ENV))
        elif provider_enum == ProviderType.GOOGLE:
            return bool(os.getenv(GEMINI_API_KEY_ENV))

        return False

    def has_any_provider_key(self) -> bool:
        """Determine whether any provider has a configured API key."""
        config = self.load()
        return any(
            self._provider_has_api_key(self._get_provider_config(config, provider))
            for provider in (
                ProviderType.OPENAI,
                ProviderType.ANTHROPIC,
                ProviderType.GOOGLE,
            )
        )

    def initialize(self) -> ShotgunConfig:
        """Initialize configuration with defaults and save to file.

        Returns:
            Default ShotgunConfig
        """
        # Generate unique user ID for new config
        config = ShotgunConfig(
            user_id=str(uuid.uuid4()),
            config_version=1,
        )
        self.save(config)
        logger.info(
            "Configuration initialized at %s with user_id: %s",
            self.config_path,
            config.user_id,
        )
        return config

    def _convert_secrets_to_secretstr(self, data: dict[str, Any]) -> None:
        """Convert plain text secrets in data to SecretStr objects."""
        for provider in [OPENAI_PROVIDER, ANTHROPIC_PROVIDER, GOOGLE_PROVIDER]:
            if provider in data and isinstance(data[provider], dict):
                if (
                    API_KEY_FIELD in data[provider]
                    and data[provider][API_KEY_FIELD] is not None
                ):
                    data[provider][API_KEY_FIELD] = SecretStr(
                        data[provider][API_KEY_FIELD]
                    )

    def _convert_secretstr_to_plain(self, data: dict[str, Any]) -> None:
        """Convert SecretStr objects in data to plain text for JSON serialization."""
        for provider in [OPENAI_PROVIDER, ANTHROPIC_PROVIDER, GOOGLE_PROVIDER]:
            if provider in data and isinstance(data[provider], dict):
                if (
                    API_KEY_FIELD in data[provider]
                    and data[provider][API_KEY_FIELD] is not None
                ):
                    if hasattr(data[provider][API_KEY_FIELD], "get_secret_value"):
                        data[provider][API_KEY_FIELD] = data[provider][
                            API_KEY_FIELD
                        ].get_secret_value()

    def _ensure_provider_enum(self, provider: ProviderType | str) -> ProviderType:
        """Normalize provider values to ProviderType enum."""
        return (
            provider if isinstance(provider, ProviderType) else ProviderType(provider)
        )

    def _get_provider_config(
        self, config: ShotgunConfig, provider: ProviderType
    ) -> Any:
        """Retrieve the provider-specific configuration section."""
        if provider == ProviderType.OPENAI:
            return config.openai
        if provider == ProviderType.ANTHROPIC:
            return config.anthropic
        if provider == ProviderType.GOOGLE:
            return config.google
        raise ValueError(f"Unsupported provider: {provider}")

    def _provider_has_api_key(self, provider_config: Any) -> bool:
        """Return True if the provider config contains a usable API key."""
        api_key = getattr(provider_config, API_KEY_FIELD, None)
        if api_key is None:
            return False

        if isinstance(api_key, SecretStr):
            value = api_key.get_secret_value()
        else:
            value = str(api_key)

        return bool(value.strip())

    def get_user_id(self) -> str:
        """Get the user ID from configuration.

        Returns:
            The unique user ID string
        """
        config = self.load()
        return config.user_id


def get_config_manager() -> ConfigManager:
    """Get the global ConfigManager instance."""
    return ConfigManager()
