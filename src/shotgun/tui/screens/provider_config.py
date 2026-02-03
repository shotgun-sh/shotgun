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
from shotgun.tui.layout import COMPACT_HEIGHT_THRESHOLD
from shotgun.tui.services.lm_studio import (
    LM_STUDIO_DOWNLOAD_URL,
    LMStudioStatus,
    get_lm_studio_status,
)
from shotgun.tui.services.ollama import (
    OLLAMA_DOWNLOAD_URL,
    OllamaStatus,
    get_ollama_status,
)

if TYPE_CHECKING:
    from ..app import ShotgunApp


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

        /* LM Studio tab styling */
        #lm-studio-status {
            padding: 0;
        }

        #lm-studio-status.running {
            color: $success;
        }

        #lm-studio-status.not-running {
            color: $text-muted;
        }

        /* LM Studio enable section */
        #lm-studio-enable-container {
            padding: 0;
        }

        #lm-studio-enable-checkbox {
            margin-right: 1;
        }

        #lm-studio-experimental-label {
            color: $warning;
            padding: 0 1;
        }

        #lm-studio-install-container {
            padding: 1 0;
        }

        #lm-studio-install-button {
            margin-right: 1;
        }

        #lm-studio-help {
            padding: 1 0;
            color: $text-muted;
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
    lm_studio_status: reactive[LMStudioStatus | None] = reactive(None)

    def __init__(self, initial_tab: str = "api-providers-tab") -> None:
        """Initialize the provider config screen.

        Args:
            initial_tab: ID of the tab to show initially ("api-providers-tab" or "ollama-tab")
        """
        super().__init__()
        self._initial_tab = initial_tab

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

            with TabPane("LM Studio (Local)", id="lm-studio-tab"):
                yield Static("Status: Checking...", id="lm-studio-status")
                yield Static("", id="lm-studio-help")
                with Horizontal(id="lm-studio-install-container"):
                    yield Button(
                        "Install LM Studio",
                        id="lm-studio-install-button",
                        variant="primary",
                    )
                    yield Static(
                        "Free, runs locally on your machine",
                        id="lm-studio-install-hint",
                    )
                with Horizontal(id="lm-studio-enable-container"):
                    yield Checkbox(
                        "Enable LM Studio",
                        id="lm-studio-enable-checkbox",
                    )
                    yield Static("Experimental", id="lm-studio-experimental-label")

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

        # Refresh UI asynchronously
        self.run_worker(self._refresh_ui(), exclusive=False)

        # Load Ollama status (exclusive to prevent duplicate widget IDs on concurrent refresh)
        self.run_worker(self._refresh_ollama_status(), exclusive=True, group="ollama")

        # Load LM Studio status
        self.run_worker(
            self._refresh_lm_studio_status(), exclusive=True, group="lm_studio"
        )

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

    def on_screenresume(self) -> None:
        """Refresh provider status when screen is resumed.

        This ensures the UI reflects any provider changes made elsewhere.
        """
        self.run_worker(self._refresh_ui(), exclusive=False)
        self.run_worker(self._refresh_ollama_status(), exclusive=True, group="ollama")
        self.run_worker(
            self._refresh_lm_studio_status(), exclusive=True, group="lm_studio"
        )

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

    async def _refresh_lm_studio_status(self) -> None:
        """Refresh LM Studio status, model list, and enable checkbox state."""
        status = await get_lm_studio_status()
        self.lm_studio_status = status
        self._update_lm_studio_ui(status)

        # Load the enable checkbox state from config
        is_enabled = await self.config_manager.is_lm_studio_enabled()
        checkbox = self.query_one("#lm-studio-enable-checkbox", Checkbox)
        checkbox.value = is_enabled

    def _update_lm_studio_ui(self, status: LMStudioStatus) -> None:
        """Update the LM Studio tab UI based on status."""
        status_label = self.query_one("#lm-studio-status", Static)
        help_label = self.query_one("#lm-studio-help", Static)
        install_container = self.query_one("#lm-studio-install-container", Horizontal)

        if status.running:
            model_count = len(status.models)
            if model_count > 0:
                status_label.update(
                    f"● Connected ({model_count} model{'s' if model_count != 1 else ''} available)"
                )
                help_label.update("")
            else:
                status_label.update("● Connected (no models loaded)")
                help_label.update("Load a model in LM Studio to use it here")
            status_label.remove_class("not-running")
            status_label.add_class("running")
            # Hide install button when LM Studio is running
            install_container.display = False
        else:
            status_label.update("○ Not connected")
            status_label.remove_class("running")
            status_label.add_class("not-running")
            # Show helpful instructions
            help_label.update(
                "1. Load a model with 64k+ context: lms load <model> -c 65536\n"
                "2. Start the server: lms server start"
            )
            # Show install button when LM Studio is not running
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

    @on(Button.Pressed, "#lm-studio-install-button")
    def _on_lm_studio_install_pressed(self) -> None:
        """Open LM Studio installation page in browser."""
        webbrowser.open(LM_STUDIO_DOWNLOAD_URL)

    @on(Checkbox.Changed, "#lm-studio-enable-checkbox")
    def _on_lm_studio_enable_changed(self, event: Checkbox.Changed) -> None:
        self.run_worker(self._do_update_lm_studio_enabled(event.value), exclusive=True)

    async def _do_update_lm_studio_enabled(self, enabled: bool) -> None:
        """Update LM Studio enabled state in config."""
        await self.config_manager.update_lm_studio_enabled(enabled)

        # When enabling LM Studio, auto-select the first available model if no model is selected
        if enabled and self.lm_studio_status and self.lm_studio_status.models:
            config = await self.config_manager.load()
            # Only auto-select if no model is currently selected
            if not config.selected_model:
                first_model = self.lm_studio_status.models[0]
                lm_studio_model_name = f"lmstudio/{first_model.id}"
                await self.config_manager.update_selected_model(lm_studio_model_name)

        # Update done button visibility since LM Studio can now provide models
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

        input_widget.value = ""
        await self.refresh_provider_status()
        await self._update_done_button_visibility()
        status_label.update(
            f"✓ Saved API key for {self._provider_display_name(self.selected_provider)}."
        )
        status_label.remove_class("error")

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
