"""Custom markdown parser configuration for the TUI.

Provides a parser factory that disables fuzzy link detection, preventing
filenames like 'specification.md' from being rendered as clickable URLs.
"""

from markdown_it import MarkdownIt


def create_markdown_parser() -> MarkdownIt:
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
