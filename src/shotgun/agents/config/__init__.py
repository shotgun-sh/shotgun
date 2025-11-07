"""Configuration module for Shotgun CLI."""

from .manager import (
    BACKUP_DIR_NAME,
    ConfigManager,
    ConfigMigrationError,
    get_backup_dir,
    get_config_manager,
)
from .models import ProviderType, ShotgunConfig
from .provider import get_provider_model

__all__ = [
    "BACKUP_DIR_NAME",
    "ConfigManager",
    "ConfigMigrationError",
    "get_backup_dir",
    "get_config_manager",
    "ProviderType",
    "ShotgunConfig",
    "get_provider_model",
]
