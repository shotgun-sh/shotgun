"""Hint widget with inline email copy button."""

from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button, Label, Markdown, Static

from shotgun.logging_config import get_logger

logger = get_logger(__name__)


class HintWithEmailCopyWidget(Container):
    """Widget that displays markdown with an inline email copy button.

    The email address and copy button appear on the same line, allowing
    users to easily copy the contact email to their clipboard.
    """

    DEFAULT_CSS = """
        HintWithEmailCopyWidget {
            width: 100%;
            height: auto;
            background: $panel;
            border: tall $primary;
            padding: 1 2;
            margin: 1 0;
        }

        HintWithEmailCopyWidget .email-copy-row {
            width: auto;
            height: auto;
            margin: 1 0;
        }

        HintWithEmailCopyWidget .email-text {
            width: auto;
            margin-right: 1;
            content-align: left middle;
        }

        HintWithEmailCopyWidget .copy-btn {
            width: auto;
            min-width: 12;
        }

        HintWithEmailCopyWidget #copy-status {
            height: 1;
            width: 100%;
            margin-top: 1;
            content-align: left middle;
        }
    """

    def __init__(
        self,
        markdown_before: str,
        email: str,
        markdown_after: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialize the hint with email copy widget.

        Args:
            markdown_before: Markdown content to display before the email line
            email: Email address to display and copy
            markdown_after: Optional markdown content to display after the email line
            **kwargs: Additional keyword arguments for Container
        """
        super().__init__(**kwargs)
        self.markdown_before = markdown_before
        self.email = email
        self.markdown_after = markdown_after

    def compose(self) -> ComposeResult:
        """Compose the widget with markdown and inline email copy button."""
        # Markdown before email
        if self.markdown_before:
            yield Markdown(self.markdown_before)

        # Email + copy button on same line
        with Horizontal(classes="email-copy-row"):
            yield Static(f"Contact: {self.email}", classes="email-text")
            yield Button("Copy email", id="copy-email-btn", classes="copy-btn")

        # Status feedback label
        yield Label("", id="copy-status")

        # Markdown after email
        if self.markdown_after:
            yield Markdown(self.markdown_after)

    @on(Button.Pressed, "#copy-email-btn")
    def _copy_email(self) -> None:
        """Copy email address to clipboard when button is pressed."""
        status_label = self.query_one("#copy-status", Label)

        try:
            import pyperclip  # type: ignore[import-untyped]  # noqa: PGH003

            pyperclip.copy(self.email)
            status_label.update("✓ Copied to clipboard!")
            logger.debug(f"Successfully copied email to clipboard: {self.email}")

        except ImportError:
            status_label.update(
                f"⚠️ Clipboard unavailable. Please manually copy: {self.email}"
            )
            logger.warning("pyperclip not available for clipboard operations")

        except Exception as e:
            status_label.update(f"⚠️ Copy failed: {e}")
            logger.error(f"Failed to copy email to clipboard: {e}", exc_info=True)
