"""Screen for configuring provider API keys before entering chat."""

from __future__ import annotations

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
from shotgun.tui.services.ollama import (
    OllamaStatus,
    get_ollama_status,
    sanitize_ollama_model_name_for_id,
)
from shotgun.utils import format_file_size

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
        ProviderConfig {
            layout: vertical;
        }

        ProviderConfig > * {
            height: auto;
        }

        #titlebox {
            height: auto;
            margin: 2 0;
            padding: 1;
            border: hkey $border;
            content-align: center middle;

            & > * {
                text-align: center;
            }
        }

        #provider-config-title {
            padding: 1 0;
            text-style: bold;
            color: $text-accent;
        }

        #provider-links {
            padding: 1 0;
        }

        #provider-list {
            margin: 2 0;
            height: auto;
            & > * {
            padding: 1 0;
            }
        }
        #provider-actions {
            padding: 1;
        }
        #provider-actions > * {
        margin-right: 2;
        }
        #provider-list {
            padding: 1;
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
            margin: 1 0;
        }

        TabPane {
            padding: 1;
        }

        /* Ollama tab styling */
        #ollama-status {
            padding: 1 0;
        }

        #ollama-status.running {
            color: $success;
        }

        #ollama-status.not-running {
            color: $text-muted;
        }

        #ollama-models-list {
            height: auto;
            max-height: 12;
            margin: 1 0;
        }

        #ollama-help {
            padding: 1 0;
            color: $text-muted;
        }

        #ollama-actions {
            padding: 1 0;
        }

        #ollama-actions > * {
            margin-right: 2;
        }

        /* Ollama enable section */
        #ollama-enable-container {
            padding: 1 0;
        }

        #ollama-enable-checkbox {
            margin-right: 1;
        }

        #ollama-experimental-label {
            color: $warning;
            padding: 0 1;
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

        ProviderConfigScreen.compact #ollama-help {
            display: none;
        }
    """

    BINDINGS = [
        ("escape", "done", "Back"),
        ("ctrl+c", "app.quit", "Quit"),
    ]

    selected_provider: reactive[str] = reactive("openai")
    ollama_status: reactive[OllamaStatus | None] = reactive(None)

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
                with Horizontal(id="ollama-enable-container"):
                    yield Checkbox(
                        "Enable Ollama",
                        id="ollama-enable-checkbox",
                    )
                    yield Static("Experimental", id="ollama-experimental-label")
                yield Static("Available Models:", id="ollama-models-header")
                yield ListView(id="ollama-models-list")
                yield Static("", id="ollama-help")
                with Horizontal(id="ollama-actions"):
                    yield Button("Refresh", id="ollama-refresh")

        with Horizontal(id="done-container"):
            yield Button("Done \\[ESC]", id="done")

    def on_mount(self) -> None:
        list_view = self.query_one("#provider-list", ListView)
        if list_view.children:
            list_view.index = 0
        self.selected_provider = "openai"

        # Hide authenticate button by default (shown only for shotgun)
        self.query_one("#authenticate", Button).display = False
        self.set_focus(self.query_one("#api-key", Input))

        # Refresh UI asynchronously
        self.run_worker(self._refresh_ui(), exclusive=False)

        # Load Ollama status (exclusive to prevent duplicate widget IDs on concurrent refresh)
        self.run_worker(self._refresh_ollama_status(), exclusive=True, group="ollama")

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
        models_list = self.query_one("#ollama-models-list", ListView)
        help_text = self.query_one("#ollama-help", Static)
        models_header = self.query_one("#ollama-models-header", Static)

        # Clear all existing items before adding new ones
        models_list.clear()

        if status.running:
            status_label.update("Status: ● Ollama is running")
            status_label.remove_class("not-running")
            status_label.add_class("running")

            if status.models:
                models_header.display = True
                models_list.display = True
                # Deduplicate by sanitized ID to avoid duplicate DOM IDs
                seen_ids: set[str] = set()
                for model in status.models:
                    safe_id = sanitize_ollama_model_name_for_id(model.name)
                    if safe_id in seen_ids:
                        continue
                    seen_ids.add(safe_id)
                    size_str = format_file_size(model.size)
                    label = Label(f"{model.name} · {size_str}")
                    models_list.append(ListItem(label, id=f"ollama-model-{safe_id}"))

                help_text.update(
                    "Tip: Use --model=ollama/<model-name> to run with a local model"
                )
            else:
                models_header.display = False
                models_list.display = False
                help_text.update("No models installed. Run: ollama pull <model-name>")
        else:
            status_label.update("Status: ○ Ollama is not running")
            status_label.remove_class("running")
            status_label.add_class("not-running")
            models_header.display = False
            models_list.display = False

            help_text.update(
                "Start Ollama on port 11434: ollama serve\n"
                "Learn more: https://ollama.com"
            )

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

    @on(Button.Pressed, "#ollama-refresh")
    def _on_ollama_refresh_pressed(self) -> None:
        self.run_worker(self._refresh_ollama_status(), exclusive=True, group="ollama")

    @on(Checkbox.Changed, "#ollama-enable-checkbox")
    def _on_ollama_enable_changed(self, event: Checkbox.Changed) -> None:
        self.run_worker(self._do_update_ollama_enabled(event.value), exclusive=True)

    async def _do_update_ollama_enabled(self, enabled: bool) -> None:
        """Update Ollama enabled state in config."""
        await self.config_manager.update_ollama_enabled(enabled)
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
        """Show/hide Done button based on whether any provider is available.

        Done button is shown if:
        - Any provider API key is configured, OR
        - Ollama is enabled and running with at least one model
        """
        done_button = self.query_one("#done", Button)
        has_keys = await self.config_manager.has_any_provider_key()

        # Also check if Ollama is enabled and has models
        has_ollama = False
        if await self.config_manager.is_ollama_enabled():
            if (
                self.ollama_status
                and self.ollama_status.running
                and self.ollama_status.models
            ):
                has_ollama = True

        done_button.display = has_keys or has_ollama

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
