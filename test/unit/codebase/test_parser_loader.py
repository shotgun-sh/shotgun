"""Unit tests for parser_loader module."""

from unittest.mock import patch

from shotgun.codebase.core.parser_loader import load_parsers


def test_load_parsers_returns_tuple():
    """Test that load_parsers returns a tuple structure."""
    result = load_parsers()

    assert isinstance(result, tuple)
    assert len(result) == 2

    parsers, queries = result
    assert isinstance(parsers, dict)
    assert isinstance(queries, dict)


def test_load_parsers_empty_config_exits():
    """Test that empty language config causes exit."""
    with (
        patch("shotgun.codebase.core.parser_loader.LANGUAGE_CONFIGS", {}),
        patch("sys.exit") as mock_exit,
    ):
        load_parsers()
        mock_exit.assert_called_once_with(1)


def test_load_parsers_handles_missing_tree_sitter_modules():
    """Test graceful handling when tree-sitter modules are missing."""
    # Mock missing all tree-sitter modules
    with (
        patch.dict(
            "sys.modules",
            {
                "tree_sitter_python": None,
                "tree_sitter_javascript": None,
                "tree_sitter_typescript": None,
                "tree_sitter_go": None,
                "tree_sitter_rust": None,
                "tree_sitter_languages": None,
            },
            clear=False,
        ),
        patch("sys.exit") as mock_exit,
    ):
        load_parsers()
        # Should exit when no parsers can be loaded
        mock_exit.assert_called_once_with(1)


def test_load_parsers_with_real_config():
    """Test load_parsers with actual language configuration."""
    # This test uses the real implementation
    parsers, queries = load_parsers()

    # Should have loaded some languages
    assert isinstance(parsers, dict)
    assert isinstance(queries, dict)

    # If any parsers were loaded, they should be valid
    for lang, parser in parsers.items():
        assert lang is not None
        assert parser is not None

    # If any queries were loaded, they should be dictionaries
    for lang, lang_queries in queries.items():
        assert lang is not None
        assert isinstance(lang_queries, dict)


def test_load_parsers_consistent_languages():
    """Test that parsers and queries have consistent language keys."""
    parsers, queries = load_parsers()

    # All languages in parsers should have corresponding queries
    for lang in parsers.keys():
        assert lang in queries

    # All languages in queries should have corresponding parsers
    for lang in queries.keys():
        assert lang in parsers
