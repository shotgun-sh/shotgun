"""Tests for the Go extractor."""

from __future__ import annotations

import pytest

from shotgun.codebase.core.extractors.go.extractor import GoExtractor
from shotgun.codebase.core.extractors.types import SupportedLanguage
from shotgun.codebase.core.parser_loader import load_parsers


@pytest.fixture
def extractor():
    """Create a Go extractor."""
    return GoExtractor()


@pytest.fixture
def parsers():
    """Load tree-sitter parsers."""
    parsers, _ = load_parsers()
    return parsers


def test_go_extractor_has_correct_language(extractor: GoExtractor):
    """Test that GoExtractor reports correct language."""
    assert extractor.language == SupportedLanguage.GO


def test_class_definition_types(extractor: GoExtractor):
    """Test that class definition types include Go type definitions."""
    types = extractor._class_definition_types()
    assert "type_declaration" in types
    assert "type_spec" in types


def test_function_definition_types(extractor: GoExtractor):
    """Test that function definition types include Go function types."""
    types = extractor._function_definition_types()
    assert "function_declaration" in types
    assert "method_declaration" in types


def test_extract_no_decorators(extractor: GoExtractor, parsers: dict):
    """Test that Go returns empty decorators (Go has no decorators)."""
    code = b"""
package main

func myFunction() {
}
"""
    tree = parsers["go"].parse(code)
    func_node = tree.root_node.children[1]

    decorators = extractor.extract_decorators(func_node)
    assert decorators == []


def test_count_ast_nodes(extractor: GoExtractor, parsers: dict):
    """Test counting AST nodes."""
    code = b"""
package main

func main() {
    x := 1
}
"""
    tree = parsers["go"].parse(code)

    count = extractor.count_ast_nodes(tree.root_node)
    assert count > 0
