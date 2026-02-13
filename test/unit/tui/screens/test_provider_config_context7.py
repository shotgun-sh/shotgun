"""Unit tests for ProviderConfigScreen - Context7 tab functionality."""

from shotgun.tui.screens.provider_config import ProviderConfigScreen


def test_provider_config_screen_init_default():
    """Test ProviderConfigScreen default initialization."""
    screen = ProviderConfigScreen()
    assert screen._initial_tab == "api-providers-tab"
    assert screen._initial_provider is None


def test_provider_config_screen_init_context7_tab():
    """Test ProviderConfigScreen with Context7 tab."""
    screen = ProviderConfigScreen(initial_tab="context7-tab")
    assert screen._initial_tab == "context7-tab"


def test_provider_config_screen_init_with_provider():
    """Test ProviderConfigScreen with initial provider pre-selection."""
    screen = ProviderConfigScreen(
        initial_tab="api-providers-tab", initial_provider="google"
    )
    assert screen._initial_tab == "api-providers-tab"
    assert screen._initial_provider == "google"
