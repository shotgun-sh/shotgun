"""Screen for selecting AI model."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, Label, ListItem, ListView, Static

from shotgun.agents.config import ConfigManager
from shotgun.agents.config.models import MODEL_SPECS, ModelName

if TYPE_CHECKING:
    from ..app import ShotgunApp


# Available models for selection
AVAILABLE_MODELS = list(ModelName)


def _sanitize_model_name_for_id(model_name: ModelName) -> str:
    """Convert model name to valid Textual ID by replacing dots with hyphens."""
    return model_name.value.replace(".", "-")


class ModelPickerScreen(Screen[None]):
    """Select AI model to use."""

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
        yield ListView(*self._build_model_items(), id="model-list")
        with Horizontal(id="model-actions"):
            yield Button("Select \\[ENTER]", variant="primary", id="select")
            yield Button("Done \\[ESC]", id="done")

    def on_mount(self) -> None:
        # Load current selection
        config_manager = self.config_manager
        config = config_manager.load()
        current_model = config.selected_model or ModelName.CLAUDE_SONNET_4_5
        self.selected_model = current_model

        # Find and highlight current selection (if it's in the filtered list)
        list_view = self.query_one(ListView)
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
        self.refresh_model_labels()

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

    def refresh_model_labels(self) -> None:
        """Update the list view entries to reflect current selection."""
        current_model = (
            self.config_manager.load().selected_model or ModelName.CLAUDE_SONNET_4_5
        )
        # Update labels for available models only
        for model_name in AVAILABLE_MODELS:
            if not self._is_model_available(model_name):
                continue
            label = self.query_one(
                f"#label-{_sanitize_model_name_for_id(model_name)}", Label
            )
            label.update(
                self._model_label(model_name, is_current=model_name == current_model)
            )

    def _build_model_items(self) -> list[ListItem]:
        items: list[ListItem] = []
        current_model = self.selected_model
        for model_name in AVAILABLE_MODELS:
            # Only add models that are available
            if not self._is_model_available(model_name):
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

    def _is_model_available(self, model_name: ModelName) -> bool:
        """Check if a model is available based on provider key configuration.

        A model is available if:
        1. Shotgun Account key is configured (provides access to all models), OR
        2. The model's provider has an API key configured (BYOK mode)

        Args:
            model_name: The model to check availability for

        Returns:
            True if the model can be used, False otherwise
        """
        config = self.config_manager.load()

        # If Shotgun Account is configured, all models are available
        if self.config_manager._provider_has_api_key(config.shotgun):
            return True

        # In BYOK mode, check if the model's provider has a key
        if model_name not in MODEL_SPECS:
            return False

        spec = MODEL_SPECS[model_name]
        return self.config_manager.has_provider_key(spec.provider)

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
        try:
            self.config_manager.update_selected_model(self.selected_model)
            self.refresh_model_labels()
            self.notify(
                f"Selected model: {self._model_display_name(self.selected_model)}"
            )
        except Exception as exc:  # pragma: no cover - defensive; textual path
            self.notify(f"Failed to select model: {exc}", severity="error")
