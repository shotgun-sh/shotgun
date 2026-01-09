"""Tests for the JavaScript extractor."""

from __future__ import annotations

import pytest

from shotgun.codebase.core.extractors.javascript.extractor import JavaScriptExtractor
from shotgun.codebase.core.extractors.types import SupportedLanguage
from shotgun.codebase.core.parser_loader import load_parsers


@pytest.fixture
def extractor():
    """Create a JavaScript extractor."""
    return JavaScriptExtractor()


@pytest.fixture
def parsers():
    """Load tree-sitter parsers."""
    parsers, _ = load_parsers()
    return parsers


def test_javascript_extractor_has_correct_language(extractor: JavaScriptExtractor):
    """Test that JavaScriptExtractor reports correct language."""
    assert extractor.language == SupportedLanguage.JAVASCRIPT


def test_extract_no_decorators(extractor: JavaScriptExtractor, parsers: dict):
    """Test that JavaScript returns empty decorators (no native decorator support)."""
    code = b"""
function myFunction() {
    return 1;
}
"""
    tree = parsers["javascript"].parse(code)
    func_node = tree.root_node.children[0]

    decorators = extractor.extract_decorators(func_node)
    assert decorators == []


def test_extract_jsdoc_comment(extractor: JavaScriptExtractor, parsers: dict):
    """Test extracting JSDoc comment as docstring."""
    code = b"""
/** This is a JSDoc comment */
function myFunction() {
    return 1;
}
"""
    tree = parsers["javascript"].parse(code)
    func_node = tree.root_node.children[1]

    docstring = extractor.extract_docstring(func_node)
    assert docstring is not None
    assert "JSDoc comment" in docstring


def test_extract_no_docstring(extractor: JavaScriptExtractor, parsers: dict):
    """Test extracting from function without JSDoc."""
    code = b"""
function myFunction() {
    return 1;
}
"""
    tree = parsers["javascript"].parse(code)
    func_node = tree.root_node.children[0]

    docstring = extractor.extract_docstring(func_node)
    assert docstring is None


def test_parse_simple_call(extractor: JavaScriptExtractor, parsers: dict):
    """Test parsing simple function call."""
    code = b"""
myFunction();
"""
    tree = parsers["javascript"].parse(code)
    expr_stmt = tree.root_node.children[0]
    call_node = expr_stmt.children[0]

    callee, obj = extractor.parse_call_node(call_node)
    assert callee == "myFunction"
    assert obj is None


def test_parse_method_call(extractor: JavaScriptExtractor, parsers: dict):
    """Test parsing method call."""
    code = b"""
obj.method();
"""
    tree = parsers["javascript"].parse(code)
    expr_stmt = tree.root_node.children[0]
    call_node = expr_stmt.children[0]

    callee, obj = extractor.parse_call_node(call_node)
    assert callee == "method"
    assert obj == "obj"


def test_count_ast_nodes(extractor: JavaScriptExtractor, parsers: dict):
    """Test counting AST nodes."""
    code = b"""
function myFunction() {
    return 1;
}
"""
    tree = parsers["javascript"].parse(code)

    count = extractor.count_ast_nodes(tree.root_node)
    assert count > 0
