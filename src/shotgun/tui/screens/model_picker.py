"""Screen for selecting AI model."""

from __future__ import annotations

import webbrowser
from typing import TYPE_CHECKING, cast

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import (
    Button,
    Label,
    ListItem,
    ListView,
    Static,
    TabbedContent,
    TabPane,
)

from shotgun.agents.agent_manager import ModelConfigUpdated
from shotgun.agents.config import ConfigManager
from shotgun.agents.config.models import (
    LM_STUDIO_MODEL_PREFIX,
    LM_STUDIO_PLACEHOLDER_API_KEY,
    MODEL_SPECS,
    OLLAMA_MODEL_PREFIX,
    OLLAMA_PLACEHOLDER_API_KEY,
    KeyProvider,
    ModelConfig,
    ModelName,
    ProviderType,
    ShotgunConfig,
    get_lm_studio_api_base_url,
    get_lm_studio_model_name,
    get_ollama_api_base_url,
    get_ollama_model_name,
    is_lm_studio_model,
    is_ollama_model,
)
from shotgun.agents.config.provider import (
    get_default_model_for_provider,
    get_provider_model,
)
from shotgun.logging_config import get_logger
from shotgun.tui.services.lm_studio import (
    LM_STUDIO_DOWNLOAD_URL,
    LMStudioStatus,
    get_lm_studio_status,
    sanitize_lm_studio_model_name_for_id,
)
from shotgun.tui.services.ollama import (
    OLLAMA_DOWNLOAD_URL,
    OllamaStatus,
    get_ollama_status,
    sanitize_ollama_model_name_for_id,
)
from shotgun.utils import format_file_size

if TYPE_CHECKING:
    from ..app import ShotgunApp

logger = get_logger(__name__)


# Available models for selection
AVAILABLE_MODELS = list(ModelName)


def _sanitize_model_name_for_id(model_name: ModelName) -> str:
    """Convert model name to valid Textual ID by replacing dots with hyphens."""
    return model_name.value.replace(".", "-")


class ModelPickerScreen(Screen[ModelConfigUpdated | None]):
    """Select AI model to use.

    Returns ModelConfigUpdated when a model is selected, None if cancelled.
    """

    CSS = """
        ModelPicker {
            layout: vertical;
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

        #model-picker-title {
            padding: 1 0;
            text-style: bold;
            color: $text-accent;
        }

        /* Tabbed content styling */
        #model-tabs {
            height: auto;
            margin: 1 0;
        }

        TabPane {
            padding: 1;
        }

        #cloud-model-list, #ollama-model-list, #lm-studio-model-list {
            margin: 1 0;
            height: auto;
            padding: 1;
            max-height: 15;
            & > * {
            padding: 1 0;
            }
        }
        #model-picker-status {
            height: auto;
            padding: 0 1;
            color: $error;
        }
        #model-actions {
            padding: 1;
        }
        #model-actions > * {
        margin-right: 2;
        }

        /* Ollama tab styling */
        #ollama-status {
            padding: 1 0;
            color: $text-muted;
        }

        #ollama-status.success {
            color: $success;
        }

        #ollama-help {
            padding: 1 0;
            color: $text-muted;
        }

        /* LM Studio tab styling */
        #lm-studio-status {
            padding: 1 0;
            color: $text-muted;
        }

        #lm-studio-status.success {
            color: $success;
        }

        #lm-studio-help {
            padding: 1 0;
            color: $text-muted;
        }

        #cloud-models-disabled-msg {
            display: none;
            padding: 1;
            color: $text-muted;
        }

        #cloud-models-disabled-msg.visible {
            display: block;
        }

        /* Ollama setup buttons */
        #ollama-setup-container {
            display: none;
            padding: 1 0;
        }

        #ollama-setup-container.visible {
            display: block;
        }

        #ollama-setup-container Button {
            margin-right: 1;
        }

        /* LM Studio setup buttons */
        #lm-studio-setup-container {
            display: none;
            padding: 1 0;
        }

        #lm-studio-setup-container.visible {
            display: block;
        }

        #lm-studio-setup-container Button {
            margin-right: 1;
        }

        /* Disabled models (no tool support) */
        #ollama-model-list ListItem.-disabled,
        #lm-studio-model-list ListItem.-disabled {
            color: $text-muted;
            text-style: italic;
        }

        #ollama-model-list ListItem.-disabled:hover,
        #lm-studio-model-list ListItem.-disabled:hover {
            background: transparent;
        }
    """

    BINDINGS = [
        ("escape", "done", "Back"),
    ]

    selected_model: reactive[ModelName] = reactive(ModelName.GPT_5_1)
    selected_ollama_model: reactive[str | None] = reactive(None)
    selected_lm_studio_model: reactive[str | None] = reactive(None)
    ollama_status: reactive[OllamaStatus | None] = reactive(None)
    lm_studio_status: reactive[LMStudioStatus | None] = reactive(None)

    def compose(self) -> ComposeResult:
        with Vertical(id="titlebox"):
            yield Static("Model selection", id="model-picker-title")
            yield Static(
                "Select the AI model you want to use for your tasks.",
                id="model-picker-summary",
            )

        with TabbedContent(id="model-tabs"):
            with TabPane("Cloud Models", id="cloud-models-tab"):
                yield Static(
                    "No API keys configured. Add keys in Provider Setup to use cloud models.",
                    id="cloud-models-disabled-msg",
                )
                yield ListView(id="cloud-model-list")

            with TabPane("Ollama", id="ollama-tab"):
                yield Static("Checking Ollama status...", id="ollama-status")
                with Horizontal(id="ollama-setup-container"):
                    yield Button(
                        "Enable Ollama",
                        id="enable-ollama-button",
                        variant="primary",
                    )
                    yield Button(
                        "Install Ollama",
                        id="install-ollama-button",
                        variant="success",
                    )
                yield ListView(id="ollama-model-list")
                yield Static("", id="ollama-help")

            with TabPane("LM Studio", id="lm-studio-tab"):
                yield Static("Checking LM Studio status...", id="lm-studio-status")
                with Horizontal(id="lm-studio-setup-container"):
                    yield Button(
                        "Enable LM Studio",
                        id="enable-lm-studio-button",
                        variant="primary",
                    )
                    yield Button(
                        "Install LM Studio",
                        id="install-lm-studio-button",
                        variant="success",
                    )
                yield ListView(id="lm-studio-model-list")
                yield Static("", id="lm-studio-help")

        yield Label("", id="model-picker-status")
        with Horizontal(id="model-actions"):
            yield Button("Select \\[ENTER]", variant="primary", id="select")
            yield Button("Done \\[ESC]", id="done")

    async def _rebuild_model_list(self) -> None:
        """Rebuild the cloud model list from current config.

        This method is called both on first show and when screen is resumed
        to ensure the list always reflects the current configuration.
        """
        logger.debug("Rebuilding model list from current config")

        # Load current config with force_reload to get latest API keys
        config_manager = self.config_manager
        config = await config_manager.load(force_reload=True)

        # Check if any cloud provider keys are configured
        has_cloud_keys = (
            config_manager._provider_has_api_key(config.openai)
            or config_manager._provider_has_api_key(config.anthropic)
            or config_manager._provider_has_api_key(config.google)
            or config_manager._provider_has_api_key(config.shotgun)
        )

        # Log provider key status
        logger.debug(
            "Provider keys: openai=%s, anthropic=%s, google=%s, shotgun=%s, has_any=%s",
            config_manager._provider_has_api_key(config.openai),
            config_manager._provider_has_api_key(config.anthropic),
            config_manager._provider_has_api_key(config.google),
            config_manager._provider_has_api_key(config.shotgun),
            has_cloud_keys,
        )

        # Update cloud models tab state
        cloud_tab = self.query_one("#cloud-models-tab", TabPane)
        cloud_list = self.query_one("#cloud-model-list", ListView)
        disabled_msg = self.query_one("#cloud-models-disabled-msg", Static)

        if has_cloud_keys:
            cloud_tab.disabled = False
            cloud_list.display = True
            disabled_msg.remove_class("visible")
        else:
            cloud_tab.disabled = True
            cloud_list.display = False
            disabled_msg.add_class("visible")
            # Switch to Ollama tab if cloud is disabled
            tabs = self.query_one("#model-tabs", TabbedContent)
            tabs.active = "ollama-tab"

        current_model = config.selected_model or get_default_model_for_provider(config)
        # Handle cloud models (ModelName enum), Ollama models, and LM Studio models (strings)
        if is_ollama_model(current_model):
            # Ollama model - extract model name without prefix for display
            self.selected_ollama_model = get_ollama_model_name(current_model)
        elif is_lm_studio_model(current_model):
            # LM Studio model - extract model name without prefix for display
            self.selected_lm_studio_model = get_lm_studio_model_name(current_model)
        elif isinstance(current_model, ModelName):
            self.selected_model = current_model
        else:
            # Default fallback for unknown string models
            self.selected_model = get_default_model_for_provider(config)
        logger.debug("Current selected model: %s", current_model)

        # Rebuild the cloud model list with current available models
        list_view = self.query_one("#cloud-model-list", ListView)

        # Remove all existing items
        old_count = len(list(list_view.children))
        for child in list(list_view.children):
            child.remove()
        logger.debug("Removed %d existing model items from list", old_count)

        # Add new items (labels already have correct text including current indicator)
        new_items = await self._build_model_items(config)
        for item in new_items:
            list_view.append(item)
        logger.debug("Added %d available model items to list", len(new_items))

        # Find and highlight current selection (if it's in the filtered list)
        if list_view.children:
            for i, child in enumerate(list_view.children):
                if isinstance(child, ListItem) and child.id:
                    model_id = child.id.removeprefix("model-")
                    # Find the model name
                    for model_name in AVAILABLE_MODELS:
                        if _sanitize_model_name_for_id(model_name) == model_id:
                            if model_name == current_model:
                                list_view.index = i
                                break

        # Also refresh local provider models
        await self._refresh_ollama_models(config)
        await self._refresh_lm_studio_models(config)

    async def _refresh_ollama_models(self, config: ShotgunConfig | None = None) -> None:
        """Refresh the Ollama tab with Ollama models."""
        if config is None:
            config = await self.config_manager.load(force_reload=False)

        status_label = self.query_one("#ollama-status", Static)
        list_view = self.query_one("#ollama-model-list", ListView)
        help_text = self.query_one("#ollama-help", Static)
        setup_container = self.query_one("#ollama-setup-container", Horizontal)
        enable_button = self.query_one("#enable-ollama-button", Button)
        install_button = self.query_one("#install-ollama-button", Button)

        # Clear existing items
        list_view.clear()

        # Check if Ollama is enabled
        if not config.ollama.enabled:
            status_label.update("Ollama is not enabled")
            status_label.remove_class("success")
            list_view.display = False
            help_text.update("Enable Ollama to use free, local AI models")
            # Show setup buttons - enable button visible, install hidden
            setup_container.add_class("visible")
            enable_button.display = True
            install_button.display = False
            return

        # Check Ollama status
        status = await get_ollama_status(base_url=config.ollama.base_url)
        self.ollama_status = status

        if not status.running:
            status_label.update("Ollama is not running")
            status_label.remove_class("success")
            list_view.display = False
            help_text.update("Install and start Ollama to use local models")
            # Show setup buttons - both visible
            setup_container.add_class("visible")
            enable_button.display = False
            install_button.display = True
            return

        if not status.models:
            status_label.update("No Ollama models installed")
            status_label.remove_class("success")
            list_view.display = False
            help_text.update("Install a model with: ollama pull <model-name>")
            # Hide setup buttons when Ollama is running
            setup_container.remove_class("visible")
            return

        # Ollama is running and has models
        status_label.update(f"● {len(status.models)} model(s) available (Experimental)")
        status_label.add_class("success")
        list_view.display = True
        help_text.update("")
        # Hide setup buttons
        setup_container.remove_class("visible")

        # Add model items, deduplicating by sanitized ID to avoid duplicate DOM IDs
        seen_ids: set[str] = set()
        tool_capable_count = 0
        for model in status.models:
            safe_id = sanitize_ollama_model_name_for_id(model.name)
            if safe_id in seen_ids:
                logger.debug("Skipping duplicate Ollama model ID: %s", safe_id)
                continue
            seen_ids.add(safe_id)
            size_str = format_file_size(model.size)

            # Check if model supports tool calling
            if model.supports_tools:
                label_text = f"{model.name} · {size_str}"
                tool_capable_count += 1
            else:
                label_text = f"{model.name} · {size_str} · No tool support"

            label = Label(label_text)
            item = ListItem(label, id=f"ollama-model-{safe_id}")

            # Disable models that don't support tools
            if not model.supports_tools:
                item.disabled = True

            list_view.append(item)

        # Update status to show how many models support tools
        if tool_capable_count < len(status.models):
            status_label.update(
                f"● {tool_capable_count}/{len(status.models)} model(s) support tools (Experimental)"
            )

    async def _refresh_lm_studio_models(
        self, config: ShotgunConfig | None = None
    ) -> None:
        """Refresh the LM Studio tab with LM Studio models."""
        if config is None:
            config = await self.config_manager.load(force_reload=False)

        status_label = self.query_one("#lm-studio-status", Static)
        list_view = self.query_one("#lm-studio-model-list", ListView)
        help_text = self.query_one("#lm-studio-help", Static)
        setup_container = self.query_one("#lm-studio-setup-container", Horizontal)
        enable_button = self.query_one("#enable-lm-studio-button", Button)
        install_button = self.query_one("#install-lm-studio-button", Button)

        # Clear existing items
        list_view.clear()

        # Check if LM Studio is enabled
        if not config.lm_studio.enabled:
            status_label.update("LM Studio is not enabled")
            status_label.remove_class("success")
            list_view.display = False
            help_text.update("Enable LM Studio to use free, local AI models")
            # Show setup buttons - enable button visible, install hidden
            setup_container.add_class("visible")
            enable_button.display = True
            install_button.display = False
            return

        # Check LM Studio status
        status = await get_lm_studio_status(base_url=config.lm_studio.base_url)
        self.lm_studio_status = status

        if not status.running:
            status_label.update("LM Studio is not running")
            status_label.remove_class("success")
            list_view.display = False
            help_text.update(
                "To start: run 'lms server start' or open LM Studio → Local Server → Start"
            )
            # Show setup buttons - both visible
            setup_container.add_class("visible")
            enable_button.display = False
            install_button.display = True
            return

        if not status.models:
            status_label.update("No models loaded in LM Studio")
            status_label.remove_class("success")
            list_view.display = False
            help_text.update("Load a model in LM Studio to use it here")
            # Hide setup buttons when LM Studio is running
            setup_container.remove_class("visible")
            return

        # LM Studio is running and has models
        status_label.update(f"● {len(status.models)} model(s) available (Experimental)")
        status_label.add_class("success")
        list_view.display = True
        help_text.update("")
        # Hide setup buttons
        setup_container.remove_class("visible")

        # Add model items
        seen_ids: set[str] = set()
        for model in status.models:
            safe_id = sanitize_lm_studio_model_name_for_id(model.id)
            if safe_id in seen_ids:
                logger.debug("Skipping duplicate LM Studio model ID: %s", safe_id)
                continue
            seen_ids.add(safe_id)

            label_text = model.id
            label = Label(label_text)
            item = ListItem(label, id=f"lm-studio-model-{safe_id}")
            list_view.append(item)

    def on_show(self) -> None:
        """Rebuild model list when screen is first shown."""
        logger.debug("ModelPickerScreen.on_show() called")
        self.run_worker(self._rebuild_model_list(), exclusive=True)

    def on_screenresume(self) -> None:
        """Rebuild model list when screen is resumed (subsequent visits).

        This is called when returning to the screen after it was suspended,
        ensuring the model list reflects any config changes made while away.
        """
        logger.debug("ModelPickerScreen.on_screenresume() called")
        self.run_worker(self._rebuild_model_list(), exclusive=True)

    def action_done(self) -> None:
        self.dismiss()

    @on(ListView.Highlighted, "#cloud-model-list")
    def _on_cloud_model_highlighted(self, event: ListView.Highlighted) -> None:
        model_name = self._model_from_item(event.item)
        if model_name:
            self.selected_model = model_name
            self.selected_ollama_model = None  # Clear ollama selection

    @on(ListView.Selected, "#cloud-model-list")
    def _on_cloud_model_selected(self, event: ListView.Selected) -> None:
        model_name = self._model_from_item(event.item)
        if model_name:
            self.selected_model = model_name
            self.selected_ollama_model = None
            self._select_cloud_model()

    @on(ListView.Highlighted, "#ollama-model-list")
    def _on_ollama_model_highlighted(self, event: ListView.Highlighted) -> None:
        ollama_model = self._ollama_model_from_item(event.item)
        if ollama_model:
            self.selected_ollama_model = ollama_model

    @on(ListView.Selected, "#ollama-model-list")
    def _on_ollama_model_selected(self, event: ListView.Selected) -> None:
        ollama_model = self._ollama_model_from_item(event.item)
        if ollama_model:
            self.selected_ollama_model = ollama_model
            self._select_ollama_model()

    @on(ListView.Highlighted, "#lm-studio-model-list")
    def _on_lm_studio_model_highlighted(self, event: ListView.Highlighted) -> None:
        lm_studio_model = self._lm_studio_model_from_item(event.item)
        if lm_studio_model:
            self.selected_lm_studio_model = lm_studio_model

    @on(ListView.Selected, "#lm-studio-model-list")
    def _on_lm_studio_model_selected(self, event: ListView.Selected) -> None:
        lm_studio_model = self._lm_studio_model_from_item(event.item)
        if lm_studio_model:
            self.selected_lm_studio_model = lm_studio_model
            self._select_lm_studio_model()

    @on(Button.Pressed, "#select")
    def _on_select_pressed(self) -> None:
        # Check which tab is active and select accordingly
        tabs = self.query_one("#model-tabs", TabbedContent)
        if tabs.active == "ollama-tab" and self.selected_ollama_model:
            self._select_ollama_model()
        elif tabs.active == "lm-studio-tab" and self.selected_lm_studio_model:
            self._select_lm_studio_model()
        else:
            self._select_cloud_model()

    @on(Button.Pressed, "#done")
    def _on_done_pressed(self) -> None:
        self.action_done()

    @on(Button.Pressed, "#enable-ollama-button")
    def _on_enable_ollama_pressed(self) -> None:
        """Open provider setup screen to Ollama tab."""
        self.run_worker(self._open_ollama_provider_setup(), exclusive=True)

    @on(Button.Pressed, "#install-ollama-button")
    def _on_install_ollama_pressed(self) -> None:
        """Open Ollama download page in browser."""
        webbrowser.open(OLLAMA_DOWNLOAD_URL)

    @on(Button.Pressed, "#enable-lm-studio-button")
    def _on_enable_lm_studio_pressed(self) -> None:
        """Open provider setup screen to LM Studio tab."""
        self.run_worker(self._open_lm_studio_provider_setup(), exclusive=True)

    @on(Button.Pressed, "#install-lm-studio-button")
    def _on_install_lm_studio_pressed(self) -> None:
        """Open LM Studio download page in browser."""
        webbrowser.open(LM_STUDIO_DOWNLOAD_URL)

    async def _open_ollama_provider_setup(self) -> None:
        """Open provider setup screen to Ollama tab and refresh on return."""
        from .provider_config import ProviderConfigScreen

        await self.app.push_screen_wait(ProviderConfigScreen(initial_tab="ollama-tab"))
        # Refresh Ollama models after returning from provider setup
        await self._refresh_ollama_models()

    async def _open_lm_studio_provider_setup(self) -> None:
        """Open provider setup screen to LM Studio tab and refresh on return."""
        from .provider_config import ProviderConfigScreen

        await self.app.push_screen_wait(
            ProviderConfigScreen(initial_tab="lm-studio-tab")
        )
        # Refresh LM Studio models after returning from provider setup
        await self._refresh_lm_studio_models()

    def _ollama_model_from_item(self, item: ListItem | None) -> str | None:
        """Get Ollama model name from a ListItem."""
        if item is None or item.id is None:
            return None
        if not item.id.startswith("ollama-model-"):
            return None
        # The ID is sanitized, need to find original model name from status
        sanitized_id = item.id.removeprefix("ollama-model-")
        if self.ollama_status and self.ollama_status.models:
            for model in self.ollama_status.models:
                if sanitize_ollama_model_name_for_id(model.name) == sanitized_id:
                    return model.name
        return None

    def _lm_studio_model_from_item(self, item: ListItem | None) -> str | None:
        """Get LM Studio model name from a ListItem."""
        if item is None or item.id is None:
            return None
        if not item.id.startswith("lm-studio-model-"):
            return None
        # The ID is sanitized, need to find original model name from status
        sanitized_id = item.id.removeprefix("lm-studio-model-")
        if self.lm_studio_status and self.lm_studio_status.models:
            for model in self.lm_studio_status.models:
                if sanitize_lm_studio_model_name_for_id(model.id) == sanitized_id:
                    return model.id
        return None

    @property
    def config_manager(self) -> ConfigManager:
        app = cast("ShotgunApp", self.app)
        return app.config_manager

    async def refresh_model_labels(self) -> None:
        """Update the list view entries to reflect current selection.

        Note: This method only updates labels for currently displayed models.
        To rebuild the entire list after provider changes, on_show() should be used.
        """
        # Load config once with force_reload
        config = await self.config_manager.load(force_reload=True)
        current_model = config.selected_model or get_default_model_for_provider(config)

        # Update labels for available cloud models only
        for model_name in AVAILABLE_MODELS:
            # Pass config to avoid multiple force reloads
            if not self._is_model_available(model_name, config):
                continue
            try:
                label = self.query_one(
                    f"#label-{_sanitize_model_name_for_id(model_name)}", Label
                )
                label.update(
                    self._model_label(
                        model_name, is_current=model_name == current_model
                    )
                )
            except Exception:  # noqa: S110
                # Label might not exist if model was filtered out
                pass

    async def _build_model_items(
        self, config: ShotgunConfig | None = None
    ) -> list[ListItem]:
        if config is None:
            config = await self.config_manager.load(force_reload=True)

        items: list[ListItem] = []
        current_model = self.selected_model
        for model_name in AVAILABLE_MODELS:
            # Only add models that are available
            if not self._is_model_available(model_name, config):
                continue

            label = Label(
                self._model_label(model_name, is_current=model_name == current_model),
                id=f"label-{_sanitize_model_name_for_id(model_name)}",
            )
            items.append(
                ListItem(label, id=f"model-{_sanitize_model_name_for_id(model_name)}")
            )
        return items

    def _model_from_item(self, item: ListItem | None) -> ModelName | None:
        """Get ModelName from a ListItem."""
        if item is None or item.id is None:
            return None
        sanitized_id = item.id.removeprefix("model-")
        # Find the original model name by comparing sanitized versions
        for model_name in AVAILABLE_MODELS:
            if _sanitize_model_name_for_id(model_name) == sanitized_id:
                return model_name
        return None

    def _is_model_available(self, model_name: ModelName, config: ShotgunConfig) -> bool:
        """Check if a model is available based on provider key configuration.

        A model is available if:
        1. Shotgun Account key is configured (provides access to all models), OR
        2. The model's provider has an API key configured (BYOK mode)

        Args:
            model_name: The model to check availability for
            config: Pre-loaded config (must be provided)

        Returns:
            True if the model can be used, False otherwise
        """
        # If Shotgun Account is configured, all models are available
        if self.config_manager._provider_has_api_key(config.shotgun):
            logger.debug("Model %s available (Shotgun Account configured)", model_name)
            return True

        # In BYOK mode, check if the model's provider has a key
        if model_name not in MODEL_SPECS:
            logger.debug("Model %s not available (not in MODEL_SPECS)", model_name)
            return False

        spec = MODEL_SPECS[model_name]
        # Check provider key directly using the loaded config to avoid stale cache
        provider_config = self.config_manager._get_provider_config(
            config, spec.provider
        )
        has_key = self.config_manager._provider_has_api_key(provider_config)
        logger.debug(
            "Model %s available=%s (provider=%s, has_key=%s)",
            model_name,
            has_key,
            spec.provider,
            has_key,
        )
        return has_key

    def _format_tokens(self, tokens: int) -> str:
        """Format token count for display (K for thousands, M for millions)."""
        if tokens >= 1_000_000:
            return f"{tokens / 1_000_000:.1f}M"
        return f"{tokens // 1000}K"

    def _model_label(self, model_name: ModelName, is_current: bool) -> str:
        """Generate label for model with specs and current indicator."""
        if model_name not in MODEL_SPECS:
            return model_name.value

        spec = MODEL_SPECS[model_name]
        display_name = self._model_display_name(model_name)

        # Format context/output tokens in readable format
        input_fmt = self._format_tokens(spec.max_input_tokens)
        output_fmt = self._format_tokens(spec.max_output_tokens)

        label = f"{display_name} · {input_fmt} context · {output_fmt} output"

        # Add cost indicator for expensive models
        if model_name == ModelName.CLAUDE_OPUS_4_5:
            label += " · Expensive"

        if is_current:
            label += " · Current"

        return label

    def _model_display_name(self, model_name: ModelName) -> str:
        """Get human-readable model name."""
        names = {
            ModelName.GPT_5_1: "GPT-5.1 (OpenAI)",
            ModelName.GPT_5_2: "GPT-5.2 (OpenAI)",
            ModelName.CLAUDE_OPUS_4_5: "Claude Opus 4.5 (Anthropic)",
            ModelName.CLAUDE_SONNET_4_5: "Claude Sonnet 4.5 (Anthropic)",
            ModelName.CLAUDE_HAIKU_4_5: "Claude Haiku 4.5 (Anthropic)",
            ModelName.GEMINI_2_5_FLASH_LITE: "Gemini 2.5 Flash Lite (Google)",
            ModelName.GEMINI_3_PRO_PREVIEW: "Gemini 3 Pro Preview (Google)",
            ModelName.GEMINI_3_FLASH_PREVIEW: "Gemini 3 Flash Preview (Google)",
        }
        return names.get(model_name, model_name.value)

    def _select_cloud_model(self) -> None:
        """Save the selected cloud model."""
        self.run_worker(self._do_select_cloud_model(), exclusive=True)

    async def _do_select_cloud_model(self) -> None:
        """Async implementation of cloud model selection."""
        try:
            # Get old model before updating
            config = await self.config_manager.load()
            old_model = config.selected_model

            # Update the selected model in config
            await self.config_manager.update_selected_model(self.selected_model)
            await self.refresh_model_labels()

            # Get the full model config with provider information
            model_config = await get_provider_model(self.selected_model)

            # Dismiss the screen and return the model config update to the caller
            self.dismiss(
                ModelConfigUpdated(
                    old_model=old_model,
                    new_model=self.selected_model,
                    provider=model_config.provider,
                    key_provider=model_config.key_provider,
                    model_config=model_config,
                )
            )
        except Exception as exc:  # pragma: no cover - defensive; textual path
            status_label = self.query_one("#model-picker-status", Label)
            status_label.update(f"❌ Failed to select model: {exc}")

    def _select_ollama_model(self) -> None:
        """Select an Ollama model."""
        self.run_worker(self._do_select_ollama_model(), exclusive=True)

    async def _do_select_ollama_model(self) -> None:
        """Async implementation of Ollama model selection."""
        if not self.selected_ollama_model:
            return

        try:
            config = await self.config_manager.load()

            # Find the OllamaModel to get its capabilities
            supports_vision = False
            if self.ollama_status and self.ollama_status.models:
                for model in self.ollama_status.models:
                    if model.name == self.selected_ollama_model:
                        supports_vision = model.supports_vision
                        break

            # Create a ModelConfig for the Ollama model using OpenAI-compatible settings
            # Ollama provides an OpenAI-compatible API at /v1
            ollama_base_url = get_ollama_api_base_url(config.ollama.base_url)

            # Store the model name in "ollama/<model>" format for config persistence
            ollama_model_name = f"{OLLAMA_MODEL_PREFIX}{self.selected_ollama_model}"

            model_config = ModelConfig(
                name=ollama_model_name,
                provider=ProviderType.OPENAI_COMPATIBLE,
                key_provider=KeyProvider.BYOK,
                max_input_tokens=128_000,  # Conservative default
                max_output_tokens=16_000,  # Conservative default
                api_key=OLLAMA_PLACEHOLDER_API_KEY,
                supports_streaming=True,
                supports_pdf=False,  # Ollama never supports PDFs
                supports_images=supports_vision,  # From model capabilities
                base_url=ollama_base_url,
            )

            # Save the selected Ollama model to config for persistence across restarts
            await self.config_manager.update_selected_model(ollama_model_name)

            # Dismiss the screen and return the model config
            # Note: For Ollama, we return new_model as a string (not ModelName enum)
            # The caller handles this via model_config.name
            self.dismiss(
                ModelConfigUpdated(
                    old_model=config.selected_model,
                    new_model=ollama_model_name,  # Pass the Ollama model name with prefix
                    provider=ProviderType.OPENAI_COMPATIBLE,
                    key_provider=KeyProvider.BYOK,
                    model_config=model_config,
                )
            )
        except Exception as exc:  # pragma: no cover - defensive; textual path
            status_label = self.query_one("#model-picker-status", Label)
            status_label.update(f"❌ Failed to select Ollama model: {exc}")

    def _select_lm_studio_model(self) -> None:
        """Select an LM Studio model."""
        self.run_worker(self._do_select_lm_studio_model(), exclusive=True)

    async def _do_select_lm_studio_model(self) -> None:
        """Async implementation of LM Studio model selection."""
        if not self.selected_lm_studio_model:
            return

        try:
            config = await self.config_manager.load()

            # Create a ModelConfig for the LM Studio model using OpenAI-compatible settings
            # LM Studio provides an OpenAI-compatible API at /v1
            lm_studio_base_url = get_lm_studio_api_base_url(config.lm_studio.base_url)

            # Store the model name in "lmstudio/<model>" format for config persistence
            lm_studio_model_name = (
                f"{LM_STUDIO_MODEL_PREFIX}{self.selected_lm_studio_model}"
            )

            model_config = ModelConfig(
                name=lm_studio_model_name,
                provider=ProviderType.OPENAI_COMPATIBLE,
                key_provider=KeyProvider.BYOK,
                max_input_tokens=8_000,  # Conservative default for local models (most are 4k-8k)
                max_output_tokens=2_000,
                api_key=LM_STUDIO_PLACEHOLDER_API_KEY,
                supports_streaming=True,
                supports_pdf=False,  # LM Studio doesn't support PDFs
                supports_images=False,  # Conservative default
                base_url=lm_studio_base_url,
            )

            # Save the selected LM Studio model to config for persistence across restarts
            await self.config_manager.update_selected_model(lm_studio_model_name)

            # Dismiss the screen and return the model config
            # Note: For LM Studio, we return new_model as a string (not ModelName enum)
            # The caller handles this via model_config.name
            self.dismiss(
                ModelConfigUpdated(
                    old_model=config.selected_model,
                    new_model=lm_studio_model_name,  # Pass the LM Studio model name with prefix
                    provider=ProviderType.OPENAI_COMPATIBLE,
                    key_provider=KeyProvider.BYOK,
                    model_config=model_config,
                )
            )
        except Exception as exc:  # pragma: no cover - defensive; textual path
            status_label = self.query_one("#model-picker-status", Label)
            status_label.update(f"❌ Failed to select LM Studio model: {exc}")
