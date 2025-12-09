"""Configuration manager for Shotgun CLI."""

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles
import aiofiles.os
from pydantic import SecretStr

from shotgun.logging_config import get_logger
from shotgun.utils import get_shotgun_home

from .constants import (
    API_KEY_FIELD,
    SHOTGUN_INSTANCE_ID_FIELD,
    SUPABASE_JWT_FIELD,
    ConfigSection,
)
from .models import (
    AnthropicConfig,
    GoogleConfig,
    ModelName,
    OpenAIConfig,
    ProviderType,
    ShotgunAccountConfig,
    ShotgunConfig,
)

logger = get_logger(__name__)


class ConfigMigrationError(Exception):
    """Exception raised when config migration fails."""

    def __init__(self, message: str, backup_path: Path | None = None):
        """Initialize with error message and optional backup path.

        Args:
            message: Error message describing what went wrong
            backup_path: Path to backup file if one was created
        """
        self.backup_path = backup_path
        super().__init__(message)


# Type alias for provider configuration objects
ProviderConfig = OpenAIConfig | AnthropicConfig | GoogleConfig | ShotgunAccountConfig

# Current config version
CURRENT_CONFIG_VERSION = 6

# Backup directory name
BACKUP_DIR_NAME = "backup"


def get_backup_dir(config_path: Path) -> Path:
    """Get the backup directory path for a given config file.

    Args:
        config_path: Path to the config file

    Returns:
        Path to the backup directory (e.g., ~/.shotgun-sh/backup/)
    """
    return config_path.parent / BACKUP_DIR_NAME


def _create_backup(config_path: Path) -> Path:
    """Create a timestamped backup of the config file before migration.

    Backups are saved to ~/.shotgun-sh/backup/ directory.

    Args:
        config_path: Path to the config file to backup

    Returns:
        Path to the backup file in the backup directory

    Raises:
        OSError: If backup creation fails
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = get_backup_dir(config_path)
    backup_path = backup_dir / f"config.backup.{timestamp}.json"

    try:
        # Create backup directory if it doesn't exist
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(config_path, backup_path)
        logger.info(f"Created config backup at {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Failed to create config backup: {e}")
        raise OSError(f"Failed to create config backup: {e}") from e


def _migrate_v2_to_v3(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate config from version 2 to version 3.

    Changes:
    - Rename 'user_id' field to 'shotgun_instance_id'

    Args:
        data: Config data dict at version 2

    Returns:
        Modified config data dict at version 3
    """
    if "user_id" in data and SHOTGUN_INSTANCE_ID_FIELD not in data:
        data[SHOTGUN_INSTANCE_ID_FIELD] = data.pop("user_id")
        data["config_version"] = 3
        logger.info("Migrated config v2->v3: renamed user_id to shotgun_instance_id")

    return data


def _migrate_v3_to_v4(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate config from version 3 to version 4.

    Changes:
    - Add 'marketing' field with empty messages dict
    - Set 'shown_welcome_screen' to False for existing BYOK users

    Args:
        data: Config data dict at version 3

    Returns:
        Modified config data dict at version 4
    """
    # Add marketing config
    if "marketing" not in data:
        data["marketing"] = {"messages": {}}
        logger.info("Migrated config v3->v4: added marketing configuration")

    # Set shown_welcome_screen for existing BYOK users
    # If shown_welcome_screen doesn't exist AND any BYOK provider has a key,
    # set it to False so they see the welcome screen once
    if "shown_welcome_screen" not in data:
        has_byok_key = False
        for section in ["openai", "anthropic", "google"]:
            if (
                section in data
                and isinstance(data[section], dict)
                and data[section].get("api_key")
            ):
                has_byok_key = True
                break

        if has_byok_key:
            data["shown_welcome_screen"] = False
            logger.info(
                "Existing BYOK user detected: set shown_welcome_screen=False to show welcome screen"
            )

    data["config_version"] = 4
    return data


def _migrate_v4_to_v5(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate config from version 4 to version 5.

    Changes:
    - Add 'supports_streaming' field to OpenAI config (initially None for auto-detection)

    Args:
        data: Config data dict at version 4

    Returns:
        Modified config data dict at version 5
    """
    if "openai" in data and isinstance(data["openai"], dict):
        if "supports_streaming" not in data["openai"]:
            data["openai"]["supports_streaming"] = None
            logger.info(
                "Migrated config v4->v5: added streaming capability detection for OpenAI"
            )

    data["config_version"] = 5
    return data


def _migrate_v5_to_v6(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate config from version 5 to version 6.

    Changes:
    - Add 'router_mode' field with default 'planning'

    Args:
        data: Config data dict at version 5

    Returns:
        Modified config data dict at version 6
    """
    if "router_mode" not in data:
        data["router_mode"] = "planning"
        logger.info("Migrated config v5->v6: added router_mode field")

    data["config_version"] = 6
    return data


def _apply_migrations(data: dict[str, Any]) -> dict[str, Any]:
    """Apply all necessary migrations to bring config to current version.

    Migrations are applied sequentially from the config's current version
    to CURRENT_CONFIG_VERSION.

    Args:
        data: Config data dict at any version

    Returns:
        Config data dict at CURRENT_CONFIG_VERSION
    """
    # Get current version (default to 2 for very old configs)
    current_version = data.get("config_version", 2)

    # Define migrations in order
    migrations = {
        2: _migrate_v2_to_v3,
        3: _migrate_v3_to_v4,
        4: _migrate_v4_to_v5,
        5: _migrate_v5_to_v6,
    }

    # Apply migrations sequentially
    while current_version < CURRENT_CONFIG_VERSION:
        if current_version in migrations:
            logger.info(
                f"Applying migration from v{current_version} to v{current_version + 1}"
            )
            data = migrations[current_version](data)
            current_version = data.get("config_version", current_version + 1)
        else:
            logger.warning(
                f"No migration defined for v{current_version}, skipping to v{current_version + 1}"
            )
            current_version += 1
            data["config_version"] = current_version

    return data


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

    async def load(self, force_reload: bool = True) -> ShotgunConfig:
        """Load configuration from file.

        Args:
            force_reload: If True, reload from disk even if cached (default: True)

        Returns:
            ShotgunConfig: Loaded configuration or default config if file doesn't exist
        """
        if self._config is not None and not force_reload:
            return self._config

        if not await aiofiles.os.path.exists(self.config_path):
            logger.info(
                "Configuration file not found, creating new config at: %s",
                self.config_path,
            )
            # Create new config with generated shotgun_instance_id
            self._config = await self.initialize()
            return self._config

        backup_path: Path | None = None
        try:
            async with aiofiles.open(self.config_path, encoding="utf-8") as f:
                content = await f.read()
                data = json.loads(content)

            # Get current version to determine if migration is needed
            current_version = data.get("config_version", 2)

            # Create backup before migration if config needs upgrading
            if current_version < CURRENT_CONFIG_VERSION:
                logger.info(
                    f"Config needs migration from v{current_version} to v{CURRENT_CONFIG_VERSION}"
                )
                try:
                    backup_path = _create_backup(self.config_path)
                except OSError as backup_error:
                    logger.warning(
                        f"Could not create backup before migration: {backup_error}"
                    )
                    # Continue without backup - better than failing completely

            # Apply all necessary migrations to bring config to current version
            try:
                data = _apply_migrations(data)
            except Exception as migration_error:
                error_msg = (
                    f"Failed to migrate configuration from v{current_version} to v{CURRENT_CONFIG_VERSION}. "
                    f"Error: {migration_error}"
                )
                if backup_path:
                    error_msg += f"\n\nYour original config has been backed up to:\n{backup_path}"
                    error_msg += (
                        "\n\nTo start fresh, delete or rename your config file:\n"
                        f"  rm {self.config_path}\n"
                        f"  shotgun config init\n\n"
                        "To restore your backup:\n"
                        f"  cp {backup_path} {self.config_path}"
                    )
                else:
                    error_msg += "\n\nTo start fresh, run: shotgun config init"

                raise ConfigMigrationError(error_msg, backup_path) from migration_error

            # Convert plain text secrets to SecretStr objects
            self._convert_secrets_to_secretstr(data)

            # Clean up invalid selected_model before Pydantic validation
            if "selected_model" in data and data["selected_model"] is not None:
                from .models import MODEL_SPECS, ModelName

                try:
                    # Try to convert to ModelName enum
                    model_name = ModelName(data["selected_model"])
                    # Check if it exists in MODEL_SPECS
                    if model_name not in MODEL_SPECS:
                        data["selected_model"] = None
                except (ValueError, KeyError):
                    # Invalid model name - reset to None
                    data["selected_model"] = None

            self._config = ShotgunConfig.model_validate(data)
            logger.debug("Configuration loaded successfully from %s", self.config_path)

            # Clear migration_failed flag if config loaded successfully
            should_save = False
            if self._config.migration_failed:
                self._config.migration_failed = False
                self._config.migration_backup_path = None
                should_save = True

            # Validate selected_model for BYOK mode - verify provider has a key
            if not self._provider_has_api_key(self._config.shotgun):
                # If selected_model is set, verify its provider has a key
                if self._config.selected_model:
                    from .models import MODEL_SPECS

                    spec = MODEL_SPECS[self._config.selected_model]
                    if not await self.has_provider_key(spec.provider):
                        # Provider has no key - reset to None
                        logger.info(
                            "Selected model %s provider has no API key, finding available model",
                            self._config.selected_model.value,
                        )
                        self._config.selected_model = None
                        should_save = True

                # If no selected_model or it was invalid, find first available model
                if not self._config.selected_model:
                    for provider in ProviderType:
                        if await self.has_provider_key(provider):
                            # Set to that provider's default model
                            from .models import MODEL_SPECS, ModelName

                            # Find default model for this provider
                            provider_models = {
                                ProviderType.OPENAI: ModelName.GPT_5_1,
                                ProviderType.ANTHROPIC: ModelName.CLAUDE_HAIKU_4_5,
                                ProviderType.GOOGLE: ModelName.GEMINI_2_5_PRO,
                            }

                            if provider in provider_models:
                                self._config.selected_model = provider_models[provider]
                                should_save = True
                                break

                if should_save:
                    await self.save(self._config)

            return self._config

        except ConfigMigrationError as migration_error:
            # Migration failed - automatically create fresh config with migration info
            logger.error(
                "Config migration failed, creating fresh config: %s", migration_error
            )
            backup_path = migration_error.backup_path

            # Create fresh config with migration failure info
            self._config = await self.initialize()
            self._config.migration_failed = True
            if backup_path:
                self._config.migration_backup_path = str(backup_path)

            # Save the fresh config
            await self.save(self._config)
            logger.info("Created fresh config after migration failure")

            return self._config

        except json.JSONDecodeError as json_error:
            # Invalid JSON - create backup and fresh config
            logger.error("Config file has invalid JSON: %s", json_error)

            try:
                backup_path = _create_backup(self.config_path)
            except OSError:
                backup_path = None

            self._config = await self.initialize()
            self._config.migration_failed = True
            if backup_path:
                self._config.migration_backup_path = str(backup_path)

            await self.save(self._config)
            logger.info("Created fresh config after JSON parse error")

            return self._config

        except Exception as e:
            # Generic error - create fresh config
            logger.error("Failed to load config: %s", e)

            self._config = await self.initialize()
            self._config.migration_failed = True
            if backup_path:
                self._config.migration_backup_path = str(backup_path)

            await self.save(self._config)
            logger.info("Created fresh config after load error")

            return self._config

    async def save(self, config: ShotgunConfig | None = None) -> None:
        """Save configuration to file.

        Args:
            config: Configuration to save. If None, saves current loaded config
        """
        if config is None:
            if self._config:
                config = self._config
            else:
                # Create a new config with generated shotgun_instance_id
                config = ShotgunConfig(
                    shotgun_instance_id=str(uuid.uuid4()),
                )

        # Ensure directory exists
        await aiofiles.os.makedirs(self.config_path.parent, exist_ok=True)

        try:
            # Convert SecretStr to plain text for JSON serialization
            data = config.model_dump()
            self._convert_secretstr_to_plain(data)
            self._convert_datetime_to_isoformat(data)

            json_content = json.dumps(data, indent=2, ensure_ascii=False)
            async with aiofiles.open(self.config_path, "w", encoding="utf-8") as f:
                await f.write(json_content)

            logger.debug("Configuration saved to %s", self.config_path)
            self._config = config

        except Exception as e:
            logger.error("Failed to save configuration to %s: %s", self.config_path, e)
            raise

    async def update_provider(
        self, provider: ProviderType | str, **kwargs: Any
    ) -> None:
        """Update provider configuration.

        Args:
            provider: Provider to update
            **kwargs: Configuration fields to update (only api_key supported)
        """
        config = await self.load()

        # Get provider config and check if it's shotgun
        provider_config, is_shotgun = self._get_provider_config_and_type(
            config, provider
        )
        # For non-shotgun providers, we need the enum for default provider logic
        provider_enum = None if is_shotgun else self._ensure_provider_enum(provider)

        # Only support api_key updates
        if API_KEY_FIELD in kwargs:
            api_key_value = kwargs[API_KEY_FIELD]
            provider_config.api_key = (
                SecretStr(api_key_value) if api_key_value is not None else None
            )

            # Reset streaming capabilities when OpenAI API key is changed
            if not is_shotgun and provider_enum == ProviderType.OPENAI:
                if isinstance(provider_config, OpenAIConfig):
                    provider_config.supports_streaming = None

        # Reject other fields
        unsupported_fields = set(kwargs.keys()) - {API_KEY_FIELD}
        if unsupported_fields:
            raise ValueError(f"Unsupported configuration fields: {unsupported_fields}")

        # If no other providers have keys configured and we just added one,
        # set selected_model to that provider's default model (only for LLM providers, not shotgun)
        if not is_shotgun and API_KEY_FIELD in kwargs and api_key_value is not None:
            # provider_enum is guaranteed to be non-None here since is_shotgun is False
            if provider_enum is None:
                raise RuntimeError("Provider enum should not be None for LLM providers")
            other_providers = [p for p in ProviderType if p != provider_enum]
            has_other_keys = any(self.has_provider_key(p) for p in other_providers)
            if not has_other_keys:
                # Set selected_model to this provider's default model
                from .models import ModelName

                provider_models = {
                    ProviderType.OPENAI: ModelName.GPT_5_1,
                    ProviderType.ANTHROPIC: ModelName.CLAUDE_HAIKU_4_5,
                    ProviderType.GOOGLE: ModelName.GEMINI_2_5_PRO,
                }
                if provider_enum in provider_models:
                    config.selected_model = provider_models[provider_enum]

            # Mark welcome screen as shown when BYOK provider is configured
            # This prevents the welcome screen from showing again after user has made their choice
            config.shown_welcome_screen = True

        # Clear migration failure flag when user successfully configures a provider
        if API_KEY_FIELD in kwargs and api_key_value is not None:
            config.migration_failed = False
            config.migration_backup_path = None

        await self.save(config)

    async def clear_provider_key(self, provider: ProviderType | str) -> None:
        """Remove the API key for the given provider (LLM provider or shotgun)."""
        config = await self.load()

        # Get provider config (shotgun or LLM provider)
        provider_config, is_shotgun = self._get_provider_config_and_type(
            config, provider
        )

        provider_config.api_key = None

        # For Shotgun Account, also clear the JWT
        if is_shotgun and isinstance(provider_config, ShotgunAccountConfig):
            provider_config.supabase_jwt = None

        # Reset streaming capabilities when OpenAI API key is cleared
        if not is_shotgun:
            provider_enum = self._ensure_provider_enum(provider)
            if provider_enum == ProviderType.OPENAI:
                if isinstance(provider_config, OpenAIConfig):
                    provider_config.supports_streaming = None

        await self.save(config)

    async def update_selected_model(self, model_name: "ModelName") -> None:
        """Update the selected model.

        Args:
            model_name: Model to select
        """
        config = await self.load()
        config.selected_model = model_name
        await self.save(config)

    async def has_provider_key(self, provider: ProviderType | str) -> bool:
        """Check if the given provider has a non-empty API key configured.

        This checks only the configuration file.
        """
        # Use force_reload=False to avoid infinite loop when called from load()
        config = await self.load(force_reload=False)
        provider_enum = self._ensure_provider_enum(provider)
        provider_config = self._get_provider_config(config, provider_enum)

        return self._provider_has_api_key(provider_config)

    async def has_any_provider_key(self) -> bool:
        """Determine whether any provider has a configured API key."""
        # Use force_reload=False to avoid infinite loop when called from load()
        config = await self.load(force_reload=False)
        # Check LLM provider keys (BYOK)
        has_llm_key = any(
            self._provider_has_api_key(self._get_provider_config(config, provider))
            for provider in (
                ProviderType.OPENAI,
                ProviderType.ANTHROPIC,
                ProviderType.GOOGLE,
            )
        )
        # Also check Shotgun Account key
        has_shotgun_key = self._provider_has_api_key(config.shotgun)
        return has_llm_key or has_shotgun_key

    async def initialize(self) -> ShotgunConfig:
        """Initialize configuration with defaults and save to file.

        Returns:
            Default ShotgunConfig
        """
        # Generate unique shotgun instance ID for new config
        config = ShotgunConfig(
            shotgun_instance_id=str(uuid.uuid4()),
        )
        await self.save(config)
        logger.info(
            "Configuration initialized at %s with shotgun_instance_id: %s",
            self.config_path,
            config.shotgun_instance_id,
        )
        return config

    def _convert_secrets_to_secretstr(self, data: dict[str, Any]) -> None:
        """Convert plain text secrets in data to SecretStr objects."""
        for section in ConfigSection:
            if section.value in data and isinstance(data[section.value], dict):
                # Convert API key
                if (
                    API_KEY_FIELD in data[section.value]
                    and data[section.value][API_KEY_FIELD] is not None
                ):
                    data[section.value][API_KEY_FIELD] = SecretStr(
                        data[section.value][API_KEY_FIELD]
                    )
                # Convert supabase JWT (shotgun section only)
                if (
                    section == ConfigSection.SHOTGUN
                    and SUPABASE_JWT_FIELD in data[section.value]
                    and data[section.value][SUPABASE_JWT_FIELD] is not None
                ):
                    data[section.value][SUPABASE_JWT_FIELD] = SecretStr(
                        data[section.value][SUPABASE_JWT_FIELD]
                    )

    def _convert_secretstr_to_plain(self, data: dict[str, Any]) -> None:
        """Convert SecretStr objects in data to plain text for JSON serialization."""
        for section in ConfigSection:
            if section.value in data and isinstance(data[section.value], dict):
                # Convert API key
                if (
                    API_KEY_FIELD in data[section.value]
                    and data[section.value][API_KEY_FIELD] is not None
                ):
                    if hasattr(data[section.value][API_KEY_FIELD], "get_secret_value"):
                        data[section.value][API_KEY_FIELD] = data[section.value][
                            API_KEY_FIELD
                        ].get_secret_value()
                # Convert supabase JWT (shotgun section only)
                if (
                    section == ConfigSection.SHOTGUN
                    and SUPABASE_JWT_FIELD in data[section.value]
                    and data[section.value][SUPABASE_JWT_FIELD] is not None
                ):
                    if hasattr(
                        data[section.value][SUPABASE_JWT_FIELD], "get_secret_value"
                    ):
                        data[section.value][SUPABASE_JWT_FIELD] = data[section.value][
                            SUPABASE_JWT_FIELD
                        ].get_secret_value()

    def _convert_datetime_to_isoformat(self, data: dict[str, Any]) -> None:
        """Convert datetime objects in data to ISO8601 format strings for JSON serialization."""
        from datetime import datetime

        def convert_dict(d: dict[str, Any]) -> None:
            """Recursively convert datetime objects in a dict."""
            for key, value in d.items():
                if isinstance(value, datetime):
                    d[key] = value.isoformat()
                elif isinstance(value, dict):
                    convert_dict(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            convert_dict(item)

        convert_dict(data)

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

    def _is_shotgun_provider(self, provider: ProviderType | str) -> bool:
        """Check if provider string represents Shotgun Account.

        Args:
            provider: Provider type or string

        Returns:
            True if provider is shotgun account
        """
        return (
            isinstance(provider, str)
            and provider.lower() == ConfigSection.SHOTGUN.value
        )

    def _get_provider_config_and_type(
        self, config: ShotgunConfig, provider: ProviderType | str
    ) -> tuple[ProviderConfig, bool]:
        """Get provider config, handling shotgun as special case.

        Args:
            config: Shotgun configuration
            provider: Provider type or string

        Returns:
            Tuple of (provider_config, is_shotgun)
        """
        if self._is_shotgun_provider(provider):
            return (config.shotgun, True)

        provider_enum = self._ensure_provider_enum(provider)
        return (self._get_provider_config(config, provider_enum), False)

    async def get_shotgun_instance_id(self) -> str:
        """Get the shotgun instance ID from configuration.

        Returns:
            The unique shotgun instance ID string
        """
        config = await self.load()
        return config.shotgun_instance_id

    async def update_shotgun_account(
        self,
        api_key: str | None = None,
        supabase_jwt: str | None = None,
        workspace_id: str | None = None,
    ) -> None:
        """Update Shotgun Account configuration.

        Args:
            api_key: LiteLLM proxy API key (optional)
            supabase_jwt: Supabase authentication JWT (optional)
            workspace_id: Default workspace ID for shared specs (optional)
        """
        config = await self.load()

        if api_key is not None:
            config.shotgun.api_key = SecretStr(api_key) if api_key else None

        if supabase_jwt is not None:
            config.shotgun.supabase_jwt = (
                SecretStr(supabase_jwt) if supabase_jwt else None
            )

        if workspace_id is not None:
            config.shotgun.workspace_id = workspace_id

        await self.save(config)
        logger.info("Updated Shotgun Account configuration")

    async def get_router_mode(self) -> str:
        """Get the saved router mode.

        Returns:
            The router mode string ('planning' or 'drafting')
        """
        config = await self.load()
        return config.router_mode

    async def set_router_mode(self, mode: str) -> None:
        """Save the router mode.

        Args:
            mode: Router mode to save ('planning' or 'drafting')
        """
        config = await self.load()
        config.router_mode = mode
        await self.save(config)
        logger.debug("Router mode saved: %s", mode)


# Global singleton instance
_config_manager_instance: ConfigManager | None = None


def get_config_manager() -> ConfigManager:
    """Get the global singleton ConfigManager instance.

    Returns:
        The singleton ConfigManager instance
    """
    global _config_manager_instance
    if _config_manager_instance is None:
        _config_manager_instance = ConfigManager()
    return _config_manager_instance
