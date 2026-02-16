"""Custom markdown widget for the TUI.

Provides a Markdown subclass that disables fuzzy link detection, preventing
filenames like 'specification.md' from being rendered as clickable URLs.
"""

from markdown_it import MarkdownIt
from textual.widgets import Markdown as _TextualMarkdown


def _create_markdown_parser() -> MarkdownIt:
    """Create a MarkdownIt parser with fuzzy link detection disabled.

    The default 'gfm-like' parser uses linkify with fuzzy matching enabled,
    which incorrectly converts bare filenames (e.g., 'specification.md',
    'tasks.md') into clickable links by treating the file extension as a
    top-level domain.

    This factory disables fuzzy_link and fuzzy_email while keeping linkify
    active for explicit URLs (https://..., http://...).
    """
    parser = MarkdownIt("gfm-like")
    if parser.linkify is not None:
        parser.linkify.set({"fuzzy_link": False, "fuzzy_email": False})
    return parser


class Markdown(_TextualMarkdown):
    """Markdown widget with fuzzy link detection disabled.

    Drop-in replacement for textual's Markdown that prevents bare filenames
    (e.g., 'specification.md') from being rendered as clickable URLs.
    """

    def __init__(
        self,
        markdown: str | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        open_links: bool = True,
    ) -> None:
        super().__init__(
            markdown,
            name=name,
            id=id,
            classes=classes,
            parser_factory=_create_markdown_parser,
            open_links=open_links,
        )
