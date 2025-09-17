from textual.app import App
from textual.binding import Binding

from shotgun.agents.config import ConfigManager, get_config_manager
from shotgun.tui.screens.splash import SplashScreen

from .screens.chat import ChatScreen
from .screens.provider_config import ProviderConfigScreen


class ShotgunApp(App[None]):
    SCREENS = {"chat": ChatScreen, "provider_config": ProviderConfigScreen}
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit the app"),
    ]
    CSS_PATH = "styles.tcss"

    def __init__(self) -> None:
        super().__init__()
        self.config_manager: ConfigManager = get_config_manager()

    def on_mount(self) -> None:
        self.push_screen(
            SplashScreen(), callback=lambda _arg: self.refresh_startup_screen()
        )
        # self.refresh_startup_screen()

    def refresh_startup_screen(self) -> None:
        """Push the appropriate screen based on configured providers."""
        if self.config_manager.has_any_provider_key():
            if isinstance(self.screen, ChatScreen):
                return
            self.push_screen("chat")
        else:
            if isinstance(self.screen, ProviderConfigScreen):
                return

            self.push_screen(
                "provider_config", callback=lambda _arg: self.refresh_startup_screen()
            )


def run() -> None:
    app = ShotgunApp()
    app.run(inline_no_clear=True)


if __name__ == "__main__":
    run()
