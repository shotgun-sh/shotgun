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
    MODEL_SPECS,
    OLLAMA_MODEL_PREFIX,
    OLLAMA_PLACEHOLDER_API_KEY,
    KeyProvider,
    ModelConfig,
    ModelName,
    ProviderType,
    ShotgunConfig,
    get_ollama_api_base_url,
    get_ollama_model_name,
    is_ollama_model,
)
from shotgun.agents.config.provider import (
    get_default_model_for_provider,
    get_provider_model,
)
from shotgun.logging_config import get_logger
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

        #cloud-model-list, #local-model-list {
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

        /* Local models tab styling */
        #local-models-status {
            padding: 1 0;
            color: $text-muted;
        }

        #local-models-status.success {
            color: $success;
        }

        #local-models-help {
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

        /* Disabled Ollama models (no tool support) */
        #local-model-list ListItem.-disabled {
            color: $text-muted;
            text-style: italic;
        }

        #local-model-list ListItem.-disabled:hover {
            background: transparent;
        }
    """

    BINDINGS = [
        ("escape", "done", "Back"),
    ]

    selected_model: reactive[ModelName] = reactive(ModelName.GPT_5_1)
    selected_ollama_model: reactive[str | None] = reactive(None)
    ollama_status: reactive[OllamaStatus | None] = reactive(None)

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

            with TabPane("Local Models", id="local-models-tab"):
                yield Static("Checking Ollama status...", id="local-models-status")
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
                yield ListView(id="local-model-list")
                yield Static("", id="local-models-help")

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
            config_manager.provider_has_api_key(config.openai)
            or config_manager.provider_has_api_key(config.anthropic)
            or config_manager.provider_has_api_key(config.google)
            or config_manager.provider_has_api_key(config.shotgun)
            or config_manager.provider_has_api_key(config.openrouter)
        )

        # Log provider key status
        logger.debug(
            "Provider keys: openai=%s, anthropic=%s, google=%s, shotgun=%s, openrouter=%s, has_any=%s",
            config_manager.provider_has_api_key(config.openai),
            config_manager.provider_has_api_key(config.anthropic),
            config_manager.provider_has_api_key(config.google),
            config_manager.provider_has_api_key(config.shotgun),
            config_manager.provider_has_api_key(config.openrouter),
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
            # Switch to local models tab if cloud is disabled
            tabs = self.query_one("#model-tabs", TabbedContent)
            tabs.active = "local-models-tab"

        current_model = config.selected_model or get_default_model_for_provider(config)
        # Handle both cloud models (ModelName enum) and Ollama models (strings)
        if is_ollama_model(current_model):
            # Ollama model - extract model name without prefix for display
            self.selected_ollama_model = get_ollama_model_name(current_model)
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

        # Also refresh local models
        await self._refresh_local_models(config)

    async def _refresh_local_models(self, config: ShotgunConfig | None = None) -> None:
        """Refresh the local models tab with Ollama models."""
        if config is None:
            config = await self.config_manager.load(force_reload=False)

        status_label = self.query_one("#local-models-status", Static)
        list_view = self.query_one("#local-model-list", ListView)
        help_text = self.query_one("#local-models-help", Static)
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

    def on_show(self) -> None:
        """Rebuild model list when screen is first shown."""
        logger.debug("ModelPickerScreen.on_show() called")
        self.run_worker(self._rebuild_model_list(), exclusive=True)

    def on_screen_resume(self) -> None:
        """Rebuild model list when screen is resumed (subsequent visits).

        This is called when returning to the screen after it was suspended,
        ensuring the model list reflects any config changes made while away.
        """
        logger.debug("ModelPickerScreen.on_screen_resume() called")
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

    @on(ListView.Highlighted, "#local-model-list")
    def _on_local_model_highlighted(self, event: ListView.Highlighted) -> None:
        ollama_model = self._ollama_model_from_item(event.item)
        if ollama_model:
            self.selected_ollama_model = ollama_model

    @on(ListView.Selected, "#local-model-list")
    def _on_local_model_selected(self, event: ListView.Selected) -> None:
        ollama_model = self._ollama_model_from_item(event.item)
        if ollama_model:
            self.selected_ollama_model = ollama_model
            self._select_ollama_model()

    @on(Button.Pressed, "#select")
    def _on_select_pressed(self) -> None:
        # Check which tab is active and select accordingly
        tabs = self.query_one("#model-tabs", TabbedContent)
        if tabs.active == "local-models-tab" and self.selected_ollama_model:
            self._select_ollama_model()
        else:
            self._select_cloud_model()

    @on(Button.Pressed, "#done")
    def _on_done_pressed(self) -> None:
        self.action_done()

    @on(Button.Pressed, "#enable-ollama-button")
    def _on_enable_ollama_pressed(self) -> None:
        """Open provider setup screen to Ollama tab."""
        self.run_worker(self._open_provider_setup(), exclusive=True)

    @on(Button.Pressed, "#install-ollama-button")
    def _on_install_ollama_pressed(self) -> None:
        """Open Ollama download page in browser."""
        webbrowser.open(OLLAMA_DOWNLOAD_URL)

    async def _open_provider_setup(self) -> None:
        """Open provider setup screen to Ollama tab and refresh on return."""
        from .provider_config import ProviderConfigScreen

        await self.app.push_screen_wait(ProviderConfigScreen(initial_tab="ollama-tab"))
        # Refresh local models after returning from provider setup
        await self._refresh_local_models()

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
        if self.config_manager.provider_has_api_key(config.shotgun):
            logger.debug("Model %s available (Shotgun Account configured)", model_name)
            return True

        # If OpenRouter is configured, all models are available
        if self.config_manager.provider_has_api_key(config.openrouter):
            logger.debug("Model %s available (OpenRouter configured)", model_name)
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
        has_key = self.config_manager.provider_has_api_key(provider_config)
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
        if model_name in (ModelName.CLAUDE_OPUS_4_6, ModelName.GPT_5_4_PRO):
            label += " · Expensive"

        if is_current:
            label += " · Current"

        return label

    def _model_display_name(self, model_name: ModelName) -> str:
        """Get human-readable model name."""
        names = {
            ModelName.GPT_5_1: "GPT-5.1 (OpenAI)",
            ModelName.GPT_5_2: "GPT-5.2 (OpenAI)",
            ModelName.GPT_5_4: "GPT-5.4 (OpenAI)",
            ModelName.GPT_5_4_PRO: "GPT-5.4 Pro (OpenAI)",
            ModelName.CLAUDE_OPUS_4_6: "Claude Opus 4.6 (Anthropic)",
            ModelName.CLAUDE_SONNET_4_6: "Claude Sonnet 4.6 (Anthropic)",
            ModelName.CLAUDE_HAIKU_4_5: "Claude Haiku 4.5 (Anthropic)",
            ModelName.GEMINI_2_5_FLASH_LITE: "Gemini 2.5 Flash Lite (Google)",
            ModelName.GEMINI_3_1_PRO_PREVIEW: "Gemini 3.1 Pro Preview (Google)",
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
