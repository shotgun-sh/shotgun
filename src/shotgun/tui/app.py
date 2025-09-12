from textual.app import App
from textual.binding import Binding

from .screens.chat import ChatScreen


class ShotgunApp(App[None]):
    SCREENS = {"chat": ChatScreen}
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit the app"),
    ]
    CSS_PATH = "styles.tcss"

    def on_mount(self) -> None:
        self.push_screen("chat")


def run() -> None:
    app = ShotgunApp()
    app.run(inline_no_clear=True)


if __name__ == "__main__":
    run()
