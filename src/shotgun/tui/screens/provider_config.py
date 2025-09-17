"""Screen for configuring provider API keys before entering chat."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from shotgun.agents.config import ConfigManager, ProviderType

if TYPE_CHECKING:
    from ..app import ShotgunApp


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
    """

    BINDINGS = [
        ("escape", "done", "Back"),
    ]

    selected_provider: reactive[ProviderType] = reactive(ProviderType.OPENAI)

    def compose(self) -> ComposeResult:
        with Vertical(id="titlebox"):
            yield Static("Provider setup", id="provider-config-title")
            yield Static(
                "Select a provider and enter the API key needed to activate it.",
                id="provider-config-summary",
            )
        yield ListView(*self._build_provider_items(), id="provider-list")
        yield Input(
            placeholder=self._input_placeholder(self.selected_provider),
            password=True,
            id="api-key",
        )
        with Horizontal(id="provider-actions"):
            yield Button("Save key \\[ENTER]", variant="primary", id="save")
            yield Button("Clear key", id="clear", variant="warning")
            yield Button("Done \\[ESC]", id="done")

    def on_mount(self) -> None:
        self.refresh_provider_status()
        list_view = self.query_one(ListView)
        if list_view.children:
            list_view.index = 0
        self.selected_provider = ProviderType.OPENAI
        self.set_focus(self.query_one("#api-key", Input))

    def action_done(self) -> None:
        self.dismiss()

    @on(ListView.Highlighted)
    def _on_provider_highlighted(self, event: ListView.Highlighted) -> None:
        provider = self._provider_from_item(event.item)
        if provider:
            self.selected_provider = provider

    @on(ListView.Selected)
    def _on_provider_selected(self, event: ListView.Selected) -> None:
        provider = self._provider_from_item(event.item)
        if provider:
            self.selected_provider = provider
            self.set_focus(self.query_one("#api-key", Input))

    @on(Button.Pressed, "#save")
    def _on_save_pressed(self) -> None:
        self._save_api_key()

    @on(Button.Pressed, "#clear")
    def _on_clear_pressed(self) -> None:
        self._clear_api_key()

    @on(Button.Pressed, "#done")
    def _on_done_pressed(self) -> None:
        self.action_done()

    @on(Input.Submitted, "#api-key")
    def _on_input_submitted(self, event: Input.Submitted) -> None:
        del event  # unused
        self._save_api_key()

    def watch_selected_provider(self, provider: ProviderType) -> None:
        if not self.is_mounted:
            return
        input_widget = self.query_one("#api-key", Input)
        input_widget.placeholder = self._input_placeholder(provider)
        input_widget.value = ""

    @property
    def config_manager(self) -> ConfigManager:
        app = cast("ShotgunApp", self.app)
        return app.config_manager

    def refresh_provider_status(self) -> None:
        """Update the list view entries to reflect configured providers."""
        for provider in ProviderType:
            label = self.query_one(f"#label-{provider.value}", Label)
            label.update(self._provider_label(provider))

    def _build_provider_items(self) -> list[ListItem]:
        items: list[ListItem] = []
        for provider in ProviderType:
            label = Label(self._provider_label(provider), id=f"label-{provider.value}")
            items.append(ListItem(label, id=f"provider-{provider.value}"))
        return items

    def _provider_from_item(self, item: ListItem | None) -> ProviderType | None:
        if item is None or item.id is None:
            return None
        provider_id = item.id.removeprefix("provider-")
        try:
            return ProviderType(provider_id)
        except ValueError:
            return None

    def _provider_label(self, provider: ProviderType) -> str:
        display = self._provider_display_name(provider)
        status = (
            "Configured"
            if self.config_manager.has_provider_key(provider)
            else "Not configured"
        )
        return f"{display} · {status}"

    def _provider_display_name(self, provider: ProviderType) -> str:
        names = {
            ProviderType.OPENAI: "OpenAI",
            ProviderType.ANTHROPIC: "Anthropic",
            ProviderType.GOOGLE: "Google Gemini",
        }
        return names.get(provider, provider.value.title())

    def _input_placeholder(self, provider: ProviderType) -> str:
        return f"{self._provider_display_name(provider)} API key"

    def _save_api_key(self) -> None:
        input_widget = self.query_one("#api-key", Input)
        api_key = input_widget.value.strip()

        if not api_key:
            self.notify("Enter an API key before saving.", severity="error")
            return

        try:
            self.config_manager.update_provider(
                self.selected_provider,
                api_key=api_key,
            )
        except Exception as exc:  # pragma: no cover - defensive; textual path
            self.notify(f"Failed to save key: {exc}", severity="error")
            return

        input_widget.value = ""
        self.refresh_provider_status()
        self.notify(
            f"Saved API key for {self._provider_display_name(self.selected_provider)}."
        )

    def _clear_api_key(self) -> None:
        try:
            self.config_manager.clear_provider_key(self.selected_provider)
        except Exception as exc:  # pragma: no cover - defensive; textual path
            self.notify(f"Failed to clear key: {exc}", severity="error")
            return

        self.refresh_provider_status()
        self.query_one("#api-key", Input).value = ""
        self.notify(
            f"Cleared API key for {self._provider_display_name(self.selected_provider)}."
        )
