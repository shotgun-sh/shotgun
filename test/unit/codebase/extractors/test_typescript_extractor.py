"""Tests for the TypeScript extractor."""

from __future__ import annotations

import pytest

from shotgun.codebase.core.extractors.javascript.extractor import JavaScriptExtractor
from shotgun.codebase.core.extractors.types import SupportedLanguage
from shotgun.codebase.core.extractors.typescript.extractor import TypeScriptExtractor
from shotgun.codebase.core.parser_loader import load_parsers


@pytest.fixture
def extractor():
    """Create a TypeScript extractor."""
    return TypeScriptExtractor()


@pytest.fixture
def parsers():
    """Load tree-sitter parsers."""
    parsers, _ = load_parsers()
    return parsers


def test_typescript_extractor_has_correct_language(extractor: TypeScriptExtractor):
    """Test that TypeScriptExtractor reports correct language."""
    assert extractor.language == SupportedLanguage.TYPESCRIPT


def test_typescript_extractor_extends_javascript(extractor: TypeScriptExtractor):
    """Test that TypeScriptExtractor extends JavaScriptExtractor."""
    assert isinstance(extractor, JavaScriptExtractor)


def test_class_definition_types_include_typescript_specific(
    extractor: TypeScriptExtractor,
):
    """Test that class definition types include TypeScript-specific types."""
    types = extractor._class_definition_types()
    assert "interface_declaration" in types
    assert "type_alias_declaration" in types
    assert "class_declaration" in types


def test_parse_simple_call(extractor: TypeScriptExtractor, parsers: dict):
    """Test parsing simple function call."""
    code = b"""
myFunction();
"""
    tree = parsers["typescript"].parse(code)
    expr_stmt = tree.root_node.children[0]
    call_node = expr_stmt.children[0]

    callee, obj = extractor.parse_call_node(call_node)
    assert callee == "myFunction"
    assert obj is None


def test_parse_method_call(extractor: TypeScriptExtractor, parsers: dict):
    """Test parsing method call."""
    code = b"""
obj.method();
"""
    tree = parsers["typescript"].parse(code)
    expr_stmt = tree.root_node.children[0]
    call_node = expr_stmt.children[0]

    callee, obj = extractor.parse_call_node(call_node)
    assert callee == "method"
    assert obj == "obj"


def test_count_ast_nodes(extractor: TypeScriptExtractor, parsers: dict):
    """Test counting AST nodes."""
    code = b"""
function myFunction(): void {
    return;
}
"""
    tree = parsers["typescript"].parse(code)

    count = extractor.count_ast_nodes(tree.root_node)
    assert count > 0
