"""Configuration module for Shotgun CLI."""

from .manager import ConfigManager, get_config_manager
from .models import ProviderType, ShotgunConfig
from .provider import get_provider_model

__all__ = [
    "ConfigManager",
    "get_config_manager",
    "ProviderType",
    "ShotgunConfig",
    "get_provider_model",
]
