"""Unit tests for provider_config screen module."""

import pytest

from shotgun.tui.screens.provider_config import get_configurable_providers


@pytest.mark.smoke
def test_get_configurable_providers_includes_all():
    """Test that get_configurable_providers includes all expected providers."""
    providers = get_configurable_providers()

    assert "shotgun" in providers
    assert "openai" in providers
    assert "anthropic" in providers
    assert "google" in providers
    assert "openrouter" in providers


def test_get_configurable_providers_returns_all_providers():
    """Test that get_configurable_providers returns all five providers in order."""
    providers = get_configurable_providers()

    assert len(providers) == 5
    assert providers == ["openrouter", "openai", "anthropic", "google", "shotgun"]


def test_get_configurable_providers_openrouter_is_first():
    """Test that openrouter is the first provider in the list."""
    providers = get_configurable_providers()

    assert providers[0] == "openrouter"
