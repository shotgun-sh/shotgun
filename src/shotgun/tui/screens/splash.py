from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen

from ..components.splash import SplashWidget


class SplashScreen(Screen[None]):
    CSS = """
        #splash-container {
            align: center middle;
            width: 100%;
            height: 100%;

        }

        SplashWidget {
            color: $text-accent;
        }
    """
    """Splash screen for the app."""

    def on_mount(self) -> None:
        self.set_timer(2, self.on_timer_tick)

    def on_timer_tick(self) -> None:
        self.dismiss()

    def compose(self) -> ComposeResult:
        with Container(id="splash-container"):
            yield SplashWidget()
