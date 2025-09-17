from textual.app import RenderResult
from textual.widgets import Static

ART = """

███████╗██╗  ██╗ ██████╗ ████████╗ ██████╗ ██╗   ██╗███╗   ██╗
██╔════╝██║  ██║██╔═══██╗╚══██╔══╝██╔════╝ ██║   ██║████╗  ██║
███████╗███████║██║   ██║   ██║   ██║  ███╗██║   ██║██╔██╗ ██║
╚════██║██╔══██║██║   ██║   ██║   ██║   ██║██║   ██║██║╚██╗██║
███████║██║  ██║╚██████╔╝   ██║   ╚██████╔╝╚██████╔╝██║ ╚████║
╚══════╝╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝

"""


class SplashWidget(Static):
    DEFAULT_CSS = """
        SplashWidget {
            text-align: center;
            width: 64;
        }
    """

    def render(self) -> RenderResult:
        return ART
