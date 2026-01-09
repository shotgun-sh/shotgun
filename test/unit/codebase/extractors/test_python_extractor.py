"""Tests for the Python extractor."""

from __future__ import annotations

import pytest

from shotgun.codebase.core.extractors.python.extractor import PythonExtractor
from shotgun.codebase.core.extractors.types import SupportedLanguage
from shotgun.codebase.core.parser_loader import load_parsers


@pytest.fixture
def extractor():
    """Create a Python extractor."""
    return PythonExtractor()


@pytest.fixture
def parsers():
    """Load tree-sitter parsers."""
    parsers, _ = load_parsers()
    return parsers


def test_python_extractor_has_correct_language(extractor: PythonExtractor):
    """Test that PythonExtractor reports correct language."""
    assert extractor.language == SupportedLanguage.PYTHON


def test_extract_decorators_from_function(extractor: PythonExtractor, parsers: dict):
    """Test extracting decorators from a function."""
    code = b"""
@decorator
def my_function():
    pass
"""
    tree = parsers["python"].parse(code)
    func_node = tree.root_node.children[0]

    decorators = extractor.extract_decorators(func_node)
    assert decorators == ["decorator"]


def test_extract_multiple_decorators(extractor: PythonExtractor, parsers: dict):
    """Test extracting multiple decorators."""
    code = b"""
@first
@second
def my_function():
    pass
"""
    tree = parsers["python"].parse(code)
    func_node = tree.root_node.children[0]

    decorators = extractor.extract_decorators(func_node)
    assert decorators == ["first", "second"]


def test_extract_attribute_decorator(extractor: PythonExtractor, parsers: dict):
    """Test extracting decorator with attribute access."""
    code = b"""
@module.decorator
def my_function():
    pass
"""
    tree = parsers["python"].parse(code)
    func_node = tree.root_node.children[0]

    decorators = extractor.extract_decorators(func_node)
    assert decorators == ["decorator"]


def test_extract_no_decorators(extractor: PythonExtractor, parsers: dict):
    """Test extracting from function without decorators."""
    code = b"""
def my_function():
    pass
"""
    tree = parsers["python"].parse(code)
    func_node = tree.root_node.children[0]

    decorators = extractor.extract_decorators(func_node)
    assert decorators == []


def test_extract_triple_quote_docstring(extractor: PythonExtractor, parsers: dict):
    """Test extracting triple-quote docstring."""
    code = b'''
def my_function():
    """This is a docstring."""
    pass
'''
    tree = parsers["python"].parse(code)
    func_node = tree.root_node.children[0]

    docstring = extractor.extract_docstring(func_node)
    assert docstring == "This is a docstring."


def test_extract_multiline_docstring(extractor: PythonExtractor, parsers: dict):
    """Test extracting multiline docstring."""
    code = b'''
def my_function():
    """
    This is a multiline
    docstring.
    """
    pass
'''
    tree = parsers["python"].parse(code)
    func_node = tree.root_node.children[0]

    docstring = extractor.extract_docstring(func_node)
    assert "multiline" in docstring
    assert "docstring" in docstring


def test_extract_no_docstring(extractor: PythonExtractor, parsers: dict):
    """Test extracting from function without docstring."""
    code = b"""
def my_function():
    pass
"""
    tree = parsers["python"].parse(code)
    func_node = tree.root_node.children[0]

    docstring = extractor.extract_docstring(func_node)
    assert docstring is None


def test_extract_single_inheritance(extractor: PythonExtractor, parsers: dict):
    """Test extracting single parent class."""
    code = b"""
class Child(Parent):
    pass
"""
    tree = parsers["python"].parse(code)
    class_node = tree.root_node.children[0]

    parents = extractor.extract_inheritance(class_node)
    assert parents == ["Parent"]


def test_extract_multiple_inheritance(extractor: PythonExtractor, parsers: dict):
    """Test extracting multiple parent classes."""
    code = b"""
class Child(Parent1, Parent2):
    pass
"""
    tree = parsers["python"].parse(code)
    class_node = tree.root_node.children[0]

    parents = extractor.extract_inheritance(class_node)
    assert parents == ["Parent1", "Parent2"]


def test_extract_qualified_inheritance(extractor: PythonExtractor, parsers: dict):
    """Test extracting qualified parent class name."""
    code = b"""
class Child(module.Parent):
    pass
"""
    tree = parsers["python"].parse(code)
    class_node = tree.root_node.children[0]

    parents = extractor.extract_inheritance(class_node)
    assert parents == ["module.Parent"]


def test_extract_no_inheritance(extractor: PythonExtractor, parsers: dict):
    """Test extracting from class without inheritance."""
    code = b"""
class MyClass:
    pass
"""
    tree = parsers["python"].parse(code)
    class_node = tree.root_node.children[0]

    parents = extractor.extract_inheritance(class_node)
    assert parents == []


def test_parse_simple_call(extractor: PythonExtractor, parsers: dict):
    """Test parsing simple function call."""
    code = b"""
my_function()
"""
    tree = parsers["python"].parse(code)
    expr_stmt = tree.root_node.children[0]
    call_node = expr_stmt.children[0]

    callee, obj = extractor.parse_call_node(call_node)
    assert callee == "my_function"
    assert obj is None


def test_parse_method_call(extractor: PythonExtractor, parsers: dict):
    """Test parsing method call."""
    code = b"""
obj.method()
"""
    tree = parsers["python"].parse(code)
    expr_stmt = tree.root_node.children[0]
    call_node = expr_stmt.children[0]

    callee, obj = extractor.parse_call_node(call_node)
    assert callee == "method"
    assert obj == "obj"


def test_find_parent_class_for_method(extractor: PythonExtractor, parsers: dict):
    """Test finding parent class for a method."""
    code = b"""
class MyClass:
    def my_method(self):
        pass
"""
    tree = parsers["python"].parse(code)
    class_node = tree.root_node.children[0]
    func_node = class_node.child_by_field_name("body").children[0]

    parent = extractor.find_parent_class(func_node, "module")
    assert parent == "module.MyClass"


def test_find_parent_class_for_standalone_function(
    extractor: PythonExtractor, parsers: dict
):
    """Test finding parent class for standalone function (should be None)."""
    code = b"""
def my_function():
    pass
"""
    tree = parsers["python"].parse(code)
    func_node = tree.root_node.children[0]

    parent = extractor.find_parent_class(func_node, "module")
    assert parent is None


def test_find_containing_function(extractor: PythonExtractor, parsers: dict):
    """Test finding containing function for a node."""
    code = b"""
def outer():
    x = 1
"""
    tree = parsers["python"].parse(code)
    func_node = tree.root_node.children[0]
    body = func_node.child_by_field_name("body")
    assignment = body.children[0]

    containing = extractor.find_containing_function(assignment, "module")
    assert containing == "module.outer"


def test_count_ast_nodes(extractor: PythonExtractor, parsers: dict):
    """Test counting AST nodes."""
    code = b"""
def my_function():
    pass
"""
    tree = parsers["python"].parse(code)

    count = extractor.count_ast_nodes(tree.root_node)
    assert count > 0
