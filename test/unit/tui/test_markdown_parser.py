"""Tests for the custom markdown parser factory."""

import pytest

from shotgun.tui.markdown import create_markdown_parser


def test_filenames_not_linkified():
    """Filenames like specification.md should not be converted to links."""
    parser = create_markdown_parser()
    tokens = parser.parse("Check specification.md for details")
    inline_tokens = [t for t in tokens if t.children]
    for token in inline_tokens:
        for child in token.children:
            assert child.markup != "linkify", (
                f"'{child.content}' was incorrectly linkified"
            )


def test_various_filenames_not_linkified():
    """Common filenames with TLD-like extensions should not be linkified."""
    parser = create_markdown_parser()
    filenames = ["tasks.md", "README.md", "config.py", "index.js", "style.css"]
    for filename in filenames:
        tokens = parser.parse(f"Updated {filename} with changes")
        inline_tokens = [t for t in tokens if t.children]
        for token in inline_tokens:
            for child in token.children:
                assert child.markup != "linkify", (
                    f"'{filename}' was incorrectly linkified"
                )


def test_explicit_https_urls_still_linkified():
    """Explicit https:// URLs should still be converted to links."""
    parser = create_markdown_parser()
    tokens = parser.parse("Visit https://example.com for details")
    inline_tokens = [t for t in tokens if t.children]
    linkify_found = any(
        child.markup == "linkify"
        for token in inline_tokens
        for child in token.children
    )
    assert linkify_found, "https://example.com should be linkified"


def test_explicit_http_urls_still_linkified():
    """Explicit http:// URLs should still be converted to links."""
    parser = create_markdown_parser()
    tokens = parser.parse("Visit http://example.com for details")
    inline_tokens = [t for t in tokens if t.children]
    linkify_found = any(
        child.markup == "linkify"
        for token in inline_tokens
        for child in token.children
    )
    assert linkify_found, "http://example.com should be linkified"


def test_markdown_links_still_work():
    """Standard markdown [text](url) links should still be parsed."""
    parser = create_markdown_parser()
    tokens = parser.parse("See [docs](https://example.com) for details")
    inline_tokens = [t for t in tokens if t.children]
    link_found = any(
        child.type == "link_open"
        for token in inline_tokens
        for child in token.children
    )
    assert link_found, "Markdown links should still work"


@pytest.mark.parametrize(
    "text",
    [
        "specification.md",
        "tasks.md",
        "plan.io",
        "config.ai",
    ],
)
def test_bare_domain_like_names_not_linkified(text: str):
    """Bare words with TLD-like extensions should not be linkified."""
    parser = create_markdown_parser()
    tokens = parser.parse(f"See {text} for details")
    inline_tokens = [t for t in tokens if t.children]
    for token in inline_tokens:
        for child in token.children:
            assert child.markup != "linkify", (
                f"'{text}' was incorrectly linkified"
            )
