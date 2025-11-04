"""Screen for submitting user feedback."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, Label, ListItem, ListView, Static, TextArea

from shotgun.posthog_telemetry import Feedback, FeedbackKind

if TYPE_CHECKING:
    from ..app import ShotgunApp


class FeedbackScreen(Screen[Feedback | None]):
    """Collect feedback from users."""

    CSS = """
        FeedbackScreen {
            layout: vertical;
        }

        FeedbackScreen > * {
            height: auto;
        }

        Label {
            padding: 0 1;
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

        #feedback-title {
            padding: 1 0;
            margin-bottom: 2;
            text-style: bold;
            color: $text-accent;
        }

        #feedback-type-list {
            height: auto;
            & > * {
                padding: 1 0;
            }
        }

        #feedback-description {
            margin: 1 0;
            height: 10;
            border: solid $border;
        }

        #feedback-actions {
            padding: 1;
        }

        #feedback-actions > * {
            margin-right: 2;
        }

        #feedback-type-list {
            padding: 1;
        }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    selected_kind: reactive[FeedbackKind] = reactive(FeedbackKind.BUG)

    def compose(self) -> ComposeResult:
        with Vertical(id="titlebox"):
            yield Static("Send us feedback", id="feedback-title")
            yield Static(
                "Select the type of feedback and provide details below.",
                id="feedback-summary",
            )
        yield ListView(*self._build_feedback_type_items(), id="feedback-type-list")
        yield TextArea(
            "",
            id="feedback-description",
        )
        with Horizontal(id="feedback-actions"):
            yield Button("Submit", variant="primary", id="submit")
            yield Button("Cancel \\[ESC]", id="cancel")

    def on_mount(self) -> None:
        list_view = self.query_one(ListView)
        if list_view.children:
            list_view.index = 0
        self.selected_kind = FeedbackKind.BUG
        text_area = self.query_one("#feedback-description", TextArea)
        text_area.focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(ListView.Highlighted)
    def _on_kind_highlighted(self, event: ListView.Highlighted) -> None:
        kind = self._kind_from_item(event.item)
        if kind:
            self.selected_kind = kind

    @on(ListView.Selected)
    def _on_kind_selected(self, event: ListView.Selected) -> None:
        kind = self._kind_from_item(event.item)
        if kind:
            self.selected_kind = kind
            self.set_focus(self.query_one("#feedback-description", TextArea))

    @on(Button.Pressed, "#submit")
    async def _on_submit_pressed(self) -> None:
        await self._submit_feedback()

    @on(Button.Pressed, "#cancel")
    def _on_cancel_pressed(self) -> None:
        self.action_cancel()

    def watch_selected_kind(self, kind: FeedbackKind) -> None:
        if not self.is_mounted:
            return
        # Update the placeholder in text area based on selected kind
        text_area = self.query_one("#feedback-description", TextArea)
        text_area.placeholder = self._placeholder_for_kind(kind)

    def _build_feedback_type_items(self) -> list[ListItem]:
        items: list[ListItem] = []
        for kind in FeedbackKind:
            label = Label(self._kind_label(kind), id=f"label-{kind.value}")
            items.append(ListItem(label, id=f"kind-{kind.value}"))
        return items

    def _kind_from_item(self, item: ListItem | None) -> FeedbackKind | None:
        if item is None or item.id is None:
            return None
        kind_id = item.id.removeprefix("kind-")
        try:
            return FeedbackKind(kind_id)
        except ValueError:
            return None

    def _kind_label(self, kind: FeedbackKind) -> str:
        display_names = {
            FeedbackKind.BUG: "Bug Report",
            FeedbackKind.FEATURE: "Feature Request",
            FeedbackKind.OTHER: "Other",
        }
        return display_names.get(kind, kind.value.title())

    def _placeholder_for_kind(self, kind: FeedbackKind) -> str:
        placeholders = {
            FeedbackKind.BUG: "Describe the bug you encountered...",
            FeedbackKind.FEATURE: "Describe the feature you'd like to see...",
            FeedbackKind.OTHER: "Tell us what's on your mind...",
        }
        return placeholders.get(kind, "Enter your feedback...")

    async def _submit_feedback(self) -> None:
        text_area = self.query_one("#feedback-description", TextArea)
        description = text_area.text.strip()

        if not description:
            self.notify(
                "Please enter a description before submitting.", severity="error"
            )
            return

        app = cast("ShotgunApp", self.app)
        shotgun_instance_id = await app.config_manager.get_shotgun_instance_id()

        feedback = Feedback(
            kind=self.selected_kind,
            description=description,
            shotgun_instance_id=shotgun_instance_id,
        )

        self.dismiss(feedback)
