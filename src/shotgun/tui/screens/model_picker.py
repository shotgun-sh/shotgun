"""Screen for selecting AI model."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, Label, ListItem, ListView, Static

from shotgun.agents.agent_manager import ModelConfigUpdated
from shotgun.agents.config import ConfigManager
from shotgun.agents.config.models import MODEL_SPECS, ModelName, ShotgunConfig
from shotgun.agents.config.provider import (
    get_default_model_for_provider,
    get_provider_model,
)
from shotgun.logging_config import get_logger

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

        #model-list {
            margin: 2 0;
            height: auto;
            padding: 1;
            & > * {
            padding: 1 0;
            }
        }
        #model-actions {
            padding: 1;
        }
        #model-actions > * {
        margin-right: 2;
        }
    """

    BINDINGS = [
        ("escape", "done", "Back"),
    ]

    selected_model: reactive[ModelName] = reactive(ModelName.GPT_5)

    def compose(self) -> ComposeResult:
        with Vertical(id="titlebox"):
            yield Static("Model selection", id="model-picker-title")
            yield Static(
                "Select the AI model you want to use for your tasks.",
                id="model-picker-summary",
            )
        yield ListView(id="model-list")
        with Horizontal(id="model-actions"):
            yield Button("Select \\[ENTER]", variant="primary", id="select")
            yield Button("Done \\[ESC]", id="done")

    async def _rebuild_model_list(self) -> None:
        """Rebuild the model list from current config.

        This method is called both on first show and when screen is resumed
        to ensure the list always reflects the current configuration.
        """
        logger.debug("Rebuilding model list from current config")

        # Load current config with force_reload to get latest API keys
        config_manager = self.config_manager
        config = await config_manager.load(force_reload=True)

        # Log provider key status
        logger.debug(
            "Provider keys: openai=%s, anthropic=%s, google=%s, shotgun=%s",
            config_manager._provider_has_api_key(config.openai),
            config_manager._provider_has_api_key(config.anthropic),
            config_manager._provider_has_api_key(config.google),
            config_manager._provider_has_api_key(config.shotgun),
        )

        current_model = config.selected_model or get_default_model_for_provider(config)
        self.selected_model = current_model
        logger.debug("Current selected model: %s", current_model)

        # Rebuild the model list with current available models
        list_view = self.query_one(ListView)

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

    def on_show(self) -> None:
        """Rebuild model list when screen is first shown."""
        logger.debug("ModelPickerScreen.on_show() called")
        self.run_worker(self._rebuild_model_list(), exclusive=False)

    def on_screenresume(self) -> None:
        """Rebuild model list when screen is resumed (subsequent visits).

        This is called when returning to the screen after it was suspended,
        ensuring the model list reflects any config changes made while away.
        """
        logger.debug("ModelPickerScreen.on_screenresume() called")
        self.run_worker(self._rebuild_model_list(), exclusive=False)

    def action_done(self) -> None:
        self.dismiss()

    @on(ListView.Highlighted)
    def _on_model_highlighted(self, event: ListView.Highlighted) -> None:
        model_name = self._model_from_item(event.item)
        if model_name:
            self.selected_model = model_name

    @on(ListView.Selected)
    def _on_model_selected(self, event: ListView.Selected) -> None:
        model_name = self._model_from_item(event.item)
        if model_name:
            self.selected_model = model_name
            self._select_model()

    @on(Button.Pressed, "#select")
    def _on_select_pressed(self) -> None:
        self._select_model()

    @on(Button.Pressed, "#done")
    def _on_done_pressed(self) -> None:
        self.action_done()

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

        # Update labels for available models only
        for model_name in AVAILABLE_MODELS:
            # Pass config to avoid multiple force reloads
            if not self._is_model_available(model_name, config):
                continue
            label = self.query_one(
                f"#label-{_sanitize_model_name_for_id(model_name)}", Label
            )
            label.update(
                self._model_label(model_name, is_current=model_name == current_model)
            )

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

    def _model_label(self, model_name: ModelName, is_current: bool) -> str:
        """Generate label for model with specs and current indicator."""
        if model_name not in MODEL_SPECS:
            return model_name.value

        spec = MODEL_SPECS[model_name]
        display_name = self._model_display_name(model_name)

        # Format context/output tokens in readable format
        input_k = spec.max_input_tokens // 1000
        output_k = spec.max_output_tokens // 1000

        label = f"{display_name} · {input_k}K context · {output_k}K output"

        # Add cost indicator for expensive models
        if model_name == ModelName.CLAUDE_OPUS_4_1:
            label += " · Expensive"

        if is_current:
            label += " · Current"

        return label

    def _model_display_name(self, model_name: ModelName) -> str:
        """Get human-readable model name."""
        names = {
            ModelName.GPT_5: "GPT-5 (OpenAI)",
            ModelName.CLAUDE_OPUS_4_1: "Claude Opus 4.1 (Anthropic)",
            ModelName.CLAUDE_SONNET_4_5: "Claude Sonnet 4.5 (Anthropic)",
            ModelName.GEMINI_2_5_PRO: "Gemini 2.5 Pro (Google)",
        }
        return names.get(model_name, model_name.value)

    def _select_model(self) -> None:
        """Save the selected model."""
        self.run_worker(self._do_select_model(), exclusive=True)

    async def _do_select_model(self) -> None:
        """Async implementation of model selection."""
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
            self.notify(f"Failed to select model: {exc}", severity="error")
