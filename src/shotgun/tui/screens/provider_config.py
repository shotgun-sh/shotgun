"""Screen for configuring provider API keys before entering chat."""

from __future__ import annotations

import webbrowser
from typing import TYPE_CHECKING, cast

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Resize
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    Label,
    ListItem,
    ListView,
    Markdown,
    Static,
    TabbedContent,
    TabPane,
)

from shotgun.agents.config import ConfigManager, ProviderType
from shotgun.agents.config.tier_detection import AnthropicTier, detect_anthropic_tier
from shotgun.logging_config import get_logger
from shotgun.posthog_telemetry import track_event
from shotgun.tui.layout import COMPACT_HEIGHT_THRESHOLD
from shotgun.tui.services.ollama import (
    OLLAMA_DOWNLOAD_URL,
    OllamaStatus,
    get_ollama_status,
)

from .tier1_warning_modal import Tier1WarningModal

if TYPE_CHECKING:
    from ..app import ShotgunApp

logger = get_logger(__name__)


def get_configurable_providers() -> list[str]:
    """Get list of configurable providers.

    Returns:
        List of provider identifiers that can be configured.
        Includes all providers: openai, anthropic, google, and shotgun.
    """
    return ["openai", "anthropic", "google", "shotgun"]


class ProviderConfigScreen(Screen[None]):
    """Collect API keys for available providers."""

    CSS = """
        ProviderConfigScreen {
            layout: vertical;
            overflow: hidden;
        }

        ProviderConfigScreen > * {
            height: auto;
        }

        #titlebox {
            height: auto;
            margin: 1 0;
            padding: 0 1;
            border: hkey $border;
            content-align: center middle;

            & > * {
                text-align: center;
            }
        }

        #provider-config-title {
            text-style: bold;
            color: $text-accent;
        }

        #provider-links {
            padding: 0;
        }

        #provider-list {
            margin: 1 0;
            height: auto;
            padding: 0;
        }

        #provider-actions {
            padding: 0;
        }

        #provider-actions > * {
            margin-right: 2;
        }

        #provider-status {
            height: auto;
            padding: 0 1;
            min-height: 1;
        }

        #provider-status.error {
            color: $error;
        }

        /* Tabbed content styling */
        #provider-tabs {
            height: auto;
            margin: 0;
        }

        #provider-tabs > ContentSwitcher {
            height: auto;
        }

        TabPane {
            height: auto;
            padding: 1 0;
        }

        /* Ollama tab styling */
        #ollama-status {
            padding: 0;
        }

        #ollama-status.running {
            color: $success;
        }

        #ollama-status.not-running {
            color: $text-muted;
        }

        /* Context7 tab styling */
        #context7-status {
            height: auto;
            padding: 0 1;
            min-height: 1;
        }

        #context7-status.error {
            color: $error;
        }

        #context7-actions {
            padding: 0;
        }

        #context7-actions > * {
            margin-right: 2;
        }

        /* Ollama enable section */
        #ollama-enable-container {
            padding: 0;
        }

        #ollama-enable-checkbox {
            margin-right: 1;
        }

        #ollama-experimental-label {
            color: $warning;
            padding: 0 1;
        }

        #ollama-install-container {
            padding: 1 0;
        }

        #ollama-install-button {
            margin-right: 1;
        }

        #done-container {
            dock: bottom;
            height: auto;
            padding: 1 0;
            background: $surface;
        }

        /* Compact styles for short terminals */
        ProviderConfigScreen.compact #titlebox {
            margin: 0;
            padding: 0;
            border: none;
        }

        ProviderConfigScreen.compact #provider-config-summary {
            display: none;
        }

        ProviderConfigScreen.compact #provider-links {
            display: none;
        }

        ProviderConfigScreen.compact #provider-list {
            margin: 0;
            padding: 0;
        }

        ProviderConfigScreen.compact #provider-actions {
            padding: 0;
        }
    """

    BINDINGS = [
        ("escape", "done", "Back"),
        ("ctrl+c", "app.quit", "Quit"),
    ]

    selected_provider: reactive[str] = reactive("openai")
    ollama_status: reactive[OllamaStatus | None] = reactive(None)

    def __init__(
        self,
        initial_tab: str = "api-providers-tab",
        initial_provider: str | None = None,
    ) -> None:
        """Initialize the provider config screen.

        Args:
            initial_tab: ID of the tab to show initially ("api-providers-tab", "ollama-tab", or "context7-tab")
            initial_provider: Provider to pre-select in the API Providers list (e.g. "google")
        """
        super().__init__()
        self._initial_tab = initial_tab
        self._initial_provider = initial_provider

    def compose(self) -> ComposeResult:
        with Vertical(id="titlebox"):
            yield Static("Provider setup", id="provider-config-title")
            yield Static(
                "Configure API keys or use local Ollama models.",
                id="provider-config-summary",
            )

        with TabbedContent(id="provider-tabs"):
            with TabPane("API Providers", id="api-providers-tab"):
                yield Markdown(
                    "Don't have an API Key? Use these links to get one: [OpenAI](https://platform.openai.com/api-keys) | [Anthropic](https://console.anthropic.com) | [Google Gemini](https://aistudio.google.com)",
                    id="provider-links",
                )
                yield ListView(*self._build_provider_items_sync(), id="provider-list")
                yield Input(
                    placeholder=self._input_placeholder(self.selected_provider),
                    password=True,
                    id="api-key",
                )
                yield Label("", id="provider-status")
                with Horizontal(id="provider-actions"):
                    yield Button("Save key \\[ENTER]", variant="primary", id="save")
                    yield Button("Authenticate", variant="success", id="authenticate")
                    yield Button("Clear key", id="clear", variant="warning")

            with TabPane("Ollama (Local)", id="ollama-tab"):
                yield Static("Status: Checking...", id="ollama-status")
                with Horizontal(id="ollama-install-container"):
                    yield Button(
                        "Install Ollama",
                        id="ollama-install-button",
                        variant="primary",
                    )
                    yield Static(
                        "Free, runs locally on your machine",
                        id="ollama-install-hint",
                    )
                with Horizontal(id="ollama-enable-container"):
                    yield Checkbox(
                        "Enable Ollama",
                        id="ollama-enable-checkbox",
                    )
                    yield Static("Experimental", id="ollama-experimental-label")

            with TabPane("Context7", id="context7-tab"):
                yield Markdown(
                    "Context7 provides up-to-date documentation for libraries as MCP tools. "
                    "Get a free API key to enable documentation-aware specs.",
                    id="context7-info",
                )
                with Horizontal(id="context7-link-actions"):
                    yield Button(
                        "Get API Key",
                        id="context7-get-key",
                        variant="primary",
                    )
                    yield Button(
                        "Copy link",
                        id="context7-copy-link",
                    )
                yield Input(
                    placeholder="Context7 API key",
                    password=True,
                    id="context7-api-key",
                )
                yield Label("", id="context7-status")
                with Horizontal(id="context7-actions"):
                    yield Button("Save key", variant="primary", id="context7-save")
                    yield Button("Clear key", id="context7-clear", variant="warning")

        with Horizontal(id="done-container"):
            yield Button("Back \\[ESC]", id="done", variant="primary")

    def on_mount(self) -> None:
        list_view = self.query_one("#provider-list", ListView)
        if list_view.children:
            list_view.index = 0
        self.selected_provider = "openai"

        # Hide authenticate button by default (shown only for shotgun)
        self.query_one("#authenticate", Button).display = False

        # Switch to initial tab if specified
        if self._initial_tab != "api-providers-tab":
            tabs = self.query_one("#provider-tabs", TabbedContent)
            tabs.active = self._initial_tab
        else:
            self.set_focus(self.query_one("#api-key", Input))

        # Pre-select provider if specified
        if self._initial_provider:
            providers = get_configurable_providers()
            if self._initial_provider in providers:
                idx = providers.index(self._initial_provider)
                list_view.index = idx
                self.selected_provider = self._initial_provider

        # Refresh UI asynchronously
        self.run_worker(self._refresh_ui(), exclusive=False)

        # Load Ollama status (exclusive to prevent duplicate widget IDs on concurrent refresh)
        self.run_worker(self._refresh_ollama_status(), exclusive=True, group="ollama")

        # Load Context7 key status
        self.run_worker(self._refresh_context7_status(), exclusive=False)

        # Apply layout based on terminal height
        self._apply_layout_for_height(self.app.size.height)

    @on(Resize)
    def handle_resize(self, event: Resize) -> None:
        """Adjust layout based on terminal height."""
        self._apply_layout_for_height(event.size.height)

    def _apply_layout_for_height(self, height: int) -> None:
        """Apply appropriate layout based on terminal height."""
        if height < COMPACT_HEIGHT_THRESHOLD:
            self.add_class("compact")
        else:
            self.remove_class("compact")

    def on_screen_resume(self) -> None:
        """Refresh provider status when screen is resumed.

        This ensures the UI reflects any provider changes made elsewhere.
        """
        self.run_worker(self._refresh_ui(), exclusive=False)
        self.run_worker(self._refresh_ollama_status(), exclusive=True, group="ollama")
        self.run_worker(self._refresh_context7_status(), exclusive=False)

    async def _refresh_ui(self) -> None:
        """Refresh provider status and button visibility."""
        await self.refresh_provider_status()
        await self._update_done_button_visibility()

    async def _refresh_ollama_status(self) -> None:
        """Refresh Ollama status, model list, and enable checkbox state."""
        status = await get_ollama_status()
        self.ollama_status = status
        self._update_ollama_ui(status)

        # Load the enable checkbox state from config
        is_enabled = await self.config_manager.is_ollama_enabled()
        checkbox = self.query_one("#ollama-enable-checkbox", Checkbox)
        checkbox.value = is_enabled

    def _update_ollama_ui(self, status: OllamaStatus) -> None:
        """Update the Ollama tab UI based on status."""
        status_label = self.query_one("#ollama-status", Static)
        install_container = self.query_one("#ollama-install-container", Horizontal)

        if status.running:
            model_count = len(status.models)
            if model_count > 0:
                status_label.update(
                    f"● Connected ({model_count} model{'s' if model_count != 1 else ''} available)"
                )
            else:
                status_label.update("● Connected (no models installed)")
            status_label.remove_class("not-running")
            status_label.add_class("running")
            # Hide install button when Ollama is running
            install_container.display = False
        else:
            status_label.update("○ Not connected - Install Ollama to use local models")
            status_label.remove_class("running")
            status_label.add_class("not-running")
            # Show install button when Ollama is not running
            install_container.display = True

    def action_done(self) -> None:
        self.dismiss()

    @on(ListView.Highlighted, "#provider-list")
    def _on_provider_highlighted(self, event: ListView.Highlighted) -> None:
        provider = self._provider_from_item(event.item)
        if provider:
            self.selected_provider = provider

    @on(ListView.Selected, "#provider-list")
    def _on_provider_selected(self, event: ListView.Selected) -> None:
        provider = self._provider_from_item(event.item)
        if provider:
            self.selected_provider = provider
            self.set_focus(self.query_one("#api-key", Input))

    @on(Button.Pressed, "#save")
    def _on_save_pressed(self) -> None:
        self._save_api_key()

    @on(Button.Pressed, "#authenticate")
    def _on_authenticate_pressed(self) -> None:
        self.run_worker(self._start_shotgun_auth(), exclusive=True)

    @on(Button.Pressed, "#clear")
    def _on_clear_pressed(self) -> None:
        self._clear_api_key()

    @on(Button.Pressed, "#done")
    def _on_done_pressed(self) -> None:
        self.action_done()

    @on(Button.Pressed, "#ollama-install-button")
    def _on_ollama_install_pressed(self) -> None:
        """Open Ollama installation page in browser."""
        webbrowser.open(OLLAMA_DOWNLOAD_URL)

    @on(Checkbox.Changed, "#ollama-enable-checkbox")
    def _on_ollama_enable_changed(self, event: Checkbox.Changed) -> None:
        self.run_worker(self._do_update_ollama_enabled(event.value), exclusive=True)

    async def _do_update_ollama_enabled(self, enabled: bool) -> None:
        """Update Ollama enabled state in config."""
        await self.config_manager.update_ollama_enabled(enabled)

        # When enabling Ollama, auto-select the first available model if no model is selected
        if enabled and self.ollama_status and self.ollama_status.models:
            config = await self.config_manager.load()
            # Only auto-select if no model is currently selected
            if not config.selected_model:
                first_model = self.ollama_status.models[0]
                ollama_model_name = f"ollama/{first_model.name}"
                await self.config_manager.update_selected_model(ollama_model_name)

        # Update done button visibility since Ollama can now provide models
        await self._update_done_button_visibility()

    @on(Input.Submitted, "#api-key")
    def _on_input_submitted(self, event: Input.Submitted) -> None:
        del event  # unused
        self._save_api_key()

    def watch_selected_provider(self, provider: ProviderType) -> None:
        if not self.is_mounted:
            return

        # Show/hide UI elements based on provider type asynchronously
        self.run_worker(self._update_provider_ui(provider), exclusive=False)

    async def _update_provider_ui(self, provider: ProviderType) -> None:
        """Update UI elements based on selected provider."""
        is_shotgun = provider == "shotgun"

        input_widget = self.query_one("#api-key", Input)
        save_button = self.query_one("#save", Button)
        auth_button = self.query_one("#authenticate", Button)

        if is_shotgun:
            # Hide API key input and save button
            input_widget.display = False
            save_button.display = False

            # Only show Authenticate button if shotgun is NOT already configured
            if await self._has_provider_key("shotgun"):
                auth_button.display = False
            else:
                auth_button.display = True
        else:
            # Show API key input and save button, hide authenticate button
            input_widget.display = True
            save_button.display = True
            auth_button.display = False
            input_widget.placeholder = self._input_placeholder(provider)
            input_widget.value = ""

    @property
    def config_manager(self) -> ConfigManager:
        app = cast("ShotgunApp", self.app)
        return app.config_manager

    async def refresh_provider_status(self) -> None:
        """Update the list view entries to reflect configured providers."""
        for provider_id in get_configurable_providers():
            label = self.query_one(f"#label-{provider_id}", Label)
            label.update(await self._provider_label(provider_id))

    async def _update_done_button_visibility(self) -> None:
        """Ensure Done button is always visible so users can exit the screen."""
        done_button = self.query_one("#done", Button)
        done_button.display = True

    def _build_provider_items_sync(self) -> list[ListItem]:
        """Build provider items synchronously for compose().

        Labels will be populated with status asynchronously in on_mount().
        """
        items: list[ListItem] = []
        for provider_id in get_configurable_providers():
            # Create labels with placeholder text - will be updated in on_mount()
            label = Label(
                self._provider_display_name(provider_id), id=f"label-{provider_id}"
            )
            items.append(ListItem(label, id=f"provider-{provider_id}"))
        return items

    def _provider_from_item(self, item: ListItem | None) -> str | None:
        if item is None or item.id is None:
            return None
        provider_id = item.id.removeprefix("provider-")
        return provider_id if provider_id in get_configurable_providers() else None

    async def _provider_label(self, provider_id: str) -> str:
        display = self._provider_display_name(provider_id)
        has_key = await self._has_provider_key(provider_id)
        status = "Configured" if has_key else "Not configured"
        return f"{display} · {status}"

    def _provider_display_name(self, provider_id: str) -> str:
        names = {
            "openai": "OpenAI",
            "anthropic": "Anthropic",
            "google": "Google Gemini",
            "shotgun": "Shotgun Account",
        }
        return names.get(provider_id, provider_id.title())

    def _input_placeholder(self, provider_id: str) -> str:
        return f"{self._provider_display_name(provider_id)} API key"

    async def _has_provider_key(self, provider_id: str) -> bool:
        """Check if provider has a configured API key."""
        if provider_id == "shotgun":
            # Check shotgun key directly
            config = await self.config_manager.load()
            return self.config_manager._provider_has_api_key(config.shotgun)
        else:
            # Check LLM provider key
            try:
                provider = ProviderType(provider_id)
                return await self.config_manager.has_provider_key(provider)
            except ValueError:
                return False

    def _save_api_key(self) -> None:
        self.run_worker(self._do_save_api_key(), exclusive=True)

    async def _do_save_api_key(self) -> None:
        """Async implementation of API key saving."""
        input_widget = self.query_one("#api-key", Input)
        api_key = input_widget.value.strip()
        status_label = self.query_one("#provider-status", Label)

        if not api_key:
            status_label.update("❌ Enter an API key before saving.")
            status_label.add_class("error")
            return

        try:
            await self.config_manager.update_provider(
                self.selected_provider,
                api_key=api_key,
            )
        except Exception as exc:  # pragma: no cover - defensive; textual path
            status_label.update(f"❌ Failed to save key: {exc}")
            status_label.add_class("error")
            return

        # Detect tier for Anthropic keys
        detected_tier: int | None = None
        should_warn_tier1 = False

        if self.selected_provider == ProviderType.ANTHROPIC:
            status_label.update("🔍 Detecting API tier...")

            try:
                tier_enum, rate_limits = await detect_anthropic_tier(api_key)
                detected_tier = (
                    int(tier_enum) if tier_enum != AnthropicTier.UNKNOWN else -1
                )
                should_warn_tier1 = tier_enum == AnthropicTier.TIER_1
            except Exception as exc:
                logger.warning(f"Failed to detect tier: {exc}")
                detected_tier = -1  # Mark as failed, don't block

            # Save tier to config
            try:
                await self.config_manager.update_provider(
                    self.selected_provider, tier=detected_tier
                )
            except Exception as exc:
                logger.warning(f"Failed to save tier to config: {exc}")

        input_widget.value = ""
        await self.refresh_provider_status()
        await self._update_done_button_visibility()

        # Update status with tier info
        if detected_tier == -1:
            status_label.update(
                "✓ Saved. (Tier detection failed - will retry on first use)"
            )
        elif detected_tier:
            status_label.update(
                f"✓ Saved API key for {self._provider_display_name(self.selected_provider)} (Tier {detected_tier})."
            )
        else:
            status_label.update(
                f"✓ Saved API key for {self._provider_display_name(self.selected_provider)}."
            )
        status_label.remove_class("error")

        # Track Tier 1 detection in PostHog (metadata only, no PII/keys)
        if should_warn_tier1:
            track_event(
                "tier1_anthropic_detected",
                {
                    "detected_tier": detected_tier,
                    "account_type": "byok",
                },
            )

        # Show Tier 1 warning modal (blocking)
        if should_warn_tier1:
            await self.app.push_screen_wait(Tier1WarningModal())

    def _clear_api_key(self) -> None:
        self.run_worker(self._do_clear_api_key(), exclusive=True)

    async def _do_clear_api_key(self) -> None:
        """Async implementation of API key clearing."""
        status_label = self.query_one("#provider-status", Label)
        try:
            await self.config_manager.clear_provider_key(self.selected_provider)
        except Exception as exc:  # pragma: no cover - defensive; textual path
            status_label.update(f"❌ Failed to clear key: {exc}")
            status_label.add_class("error")
            return

        await self.refresh_provider_status()
        await self._update_done_button_visibility()
        self.query_one("#api-key", Input).value = ""

        # If we just cleared shotgun, show the Authenticate button
        if self.selected_provider == "shotgun":
            auth_button = self.query_one("#authenticate", Button)
            auth_button.display = True

        status_label.update(
            f"✓ Cleared API key for {self._provider_display_name(self.selected_provider)}."
        )
        status_label.remove_class("error")

    @on(Button.Pressed, "#context7-get-key")
    def _on_context7_get_key(self) -> None:
        """Open Context7 website to get an API key."""
        webbrowser.open("https://context7.com")

    @on(Button.Pressed, "#context7-copy-link")
    def _on_context7_copy_link(self) -> None:
        """Copy Context7 URL to clipboard."""
        status_label = self.query_one("#context7-status", Label)
        try:
            import pyperclip  # type: ignore[import-untyped]

            pyperclip.copy("https://context7.com")
            status_label.update("Copied to clipboard!")
            status_label.remove_class("error")
        except ImportError:
            status_label.update("Clipboard unavailable. Visit https://context7.com")
            status_label.remove_class("error")
        except Exception as e:
            status_label.update(f"Copy failed: {e}")
            status_label.add_class("error")

    @on(Button.Pressed, "#context7-save")
    def _on_context7_save(self) -> None:
        self.run_worker(self._do_save_context7_key(), exclusive=True)

    @on(Button.Pressed, "#context7-clear")
    def _on_context7_clear(self) -> None:
        self.run_worker(self._do_clear_context7_key(), exclusive=True)

    async def _do_save_context7_key(self) -> None:
        """Save Context7 API key."""
        input_widget = self.query_one("#context7-api-key", Input)
        status_label = self.query_one("#context7-status", Label)
        api_key = input_widget.value.strip()

        if not api_key:
            status_label.update("Enter an API key before saving.")
            status_label.add_class("error")
            return

        try:
            await self.config_manager.update_context7(api_key)
            input_widget.value = ""
            status_label.update("Saved Context7 API key.")
            status_label.remove_class("error")
        except Exception as exc:
            status_label.update(f"Failed to save key: {exc}")
            status_label.add_class("error")

    async def _do_clear_context7_key(self) -> None:
        """Clear Context7 API key."""
        status_label = self.query_one("#context7-status", Label)
        try:
            await self.config_manager.update_context7(None)
            self.query_one("#context7-api-key", Input).value = ""
            status_label.update("Cleared Context7 API key.")
            status_label.remove_class("error")
        except Exception as exc:
            status_label.update(f"Failed to clear key: {exc}")
            status_label.add_class("error")

    async def _refresh_context7_status(self) -> None:
        """Load existing Context7 key status on mount."""
        config = await self.config_manager.load()
        status_label = self.query_one("#context7-status", Label)
        if config.context7.api_key and config.context7.api_key.get_secret_value():
            status_label.update("Context7 API key is configured.")
            status_label.remove_class("error")
        else:
            status_label.update("")

    async def _start_shotgun_auth(self) -> None:
        """Launch Shotgun Account authentication flow."""
        from .shotgun_auth import ShotgunAuthScreen

        # Push the auth screen and wait for result
        result = await self.app.push_screen_wait(ShotgunAuthScreen())

        # Refresh provider status after auth completes
        if result:
            await self.refresh_provider_status()
            # Auto-dismiss provider config screen after successful auth
            self.dismiss()
