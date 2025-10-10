"""Unit tests for provider_config screen module."""

from shotgun.tui.screens.provider_config import get_configurable_providers


def test_get_configurable_providers_includes_shotgun():
    """Test that get_configurable_providers always includes shotgun."""
    providers = get_configurable_providers()

    assert "shotgun" in providers
    assert "openai" in providers
    assert "anthropic" in providers
    assert "google" in providers


def test_get_configurable_providers_returns_all_providers():
    """Test that get_configurable_providers returns all four providers."""
    providers = get_configurable_providers()

    assert len(providers) == 4
    assert providers == ["openai", "anthropic", "google", "shotgun"]
