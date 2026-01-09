"""AST extraction utilities for parsing source code.

This module provides shared extraction logic for definitions, decorators,
docstrings, inheritance, and calls from tree-sitter AST nodes.
"""

from __future__ import annotations

from tree_sitter import Node


def extract_decorators(node: Node, language: str) -> list[str]:
    """Extract decorators from a function/class node.

    Args:
        node: The AST node (function or class definition)
        language: Programming language

    Returns:
        List of decorator names
    """
    decorators: list[str] = []

    if language == "python":
        for child in node.children:
            if child.type == "decorator":
                for grandchild in child.children:
                    if grandchild.type == "identifier" and grandchild.text:
                        decorators.append(grandchild.text.decode("utf-8"))
                        break
                    elif grandchild.type == "attribute":
                        attr_node = grandchild.child_by_field_name("attribute")
                        if attr_node and attr_node.text:
                            decorators.append(attr_node.text.decode("utf-8"))
                            break

    return decorators


def extract_docstring(node: Node, language: str) -> str | None:
    """Extract docstring from function/class node.

    Args:
        node: The AST node (function or class definition)
        language: Programming language

    Returns:
        Extracted docstring or None
    """
    if language == "python":
        body_node = node.child_by_field_name("body")
        if not body_node or not body_node.children:
            return None

        first_statement = body_node.children[0]
        if first_statement.type == "expression_statement":
            for child in first_statement.children:
                if child.type == "string" and child.text:
                    docstring = child.text.decode("utf-8")
                    docstring = docstring.strip()
                    if (
                        docstring.startswith('"""')
                        and docstring.endswith('"""')
                        or docstring.startswith("'''")
                        and docstring.endswith("'''")
                    ):
                        docstring = docstring[3:-3]
                    elif (
                        docstring.startswith('"')
                        and docstring.endswith('"')
                        or docstring.startswith("'")
                        and docstring.endswith("'")
                    ):
                        docstring = docstring[1:-1]
                    return docstring.strip()

    # JavaScript/TypeScript JSDoc support could be added here
    # Go doc comments could be added here

    return None


def extract_inheritance(class_node: Node, language: str) -> list[str]:
    """Extract parent class names from class definition.

    Args:
        class_node: The class definition AST node
        language: Programming language

    Returns:
        List of parent class names (simple names, need resolution)
    """
    parent_names: list[str] = []

    if language == "python":
        for child in class_node.children:
            if child.type == "argument_list":
                for arg in child.children:
                    if arg.type == "identifier" and arg.text:
                        parent_names.append(arg.text.decode("utf-8"))
                    elif arg.type == "attribute":
                        full_name_parts: list[str] = []
                        _extract_full_name(arg, full_name_parts)
                        if full_name_parts:
                            parent_names.append(".".join(full_name_parts))

    # JavaScript/TypeScript extends support could be added here
    # Go embedding support could be added here

    return parent_names


def _extract_full_name(node: Node, parts: list[str]) -> None:
    """Recursively extract full qualified name from attribute access.

    Args:
        node: The AST node
        parts: List to accumulate name parts (modified in place)
    """
    if node.type == "identifier" and node.text:
        parts.insert(0, node.text.decode("utf-8"))
    elif node.type == "attribute":
        attr_node = node.child_by_field_name("attribute")
        if attr_node and attr_node.text:
            parts.insert(0, attr_node.text.decode("utf-8"))

        obj_node = node.child_by_field_name("object")
        if obj_node:
            _extract_full_name(obj_node, parts)


def find_parent_class(func_node: Node, module_qn: str) -> str | None:
    """Find the parent class of a function node.

    Args:
        func_node: The function definition AST node
        module_qn: Module qualified name

    Returns:
        Qualified name of parent class, or None if not in a class
    """
    current = func_node.parent

    while current:
        if current.type in ["class_definition", "class_declaration"]:
            for child in current.children:
                if child.type == "identifier" and child.text:
                    class_name = child.text.decode("utf-8")
                    return f"{module_qn}.{class_name}"

        current = current.parent

    return None


def find_containing_function(node: Node, module_qn: str) -> str | None:
    """Find the containing function/method of a node.

    Args:
        node: The AST node
        module_qn: Module qualified name

    Returns:
        Qualified name of containing function, or None
    """
    current = node.parent

    while current:
        if current.type in [
            "function_definition",
            "method_definition",
            "arrow_function",
        ]:
            for child in current.children:
                if child.type == "identifier" and child.text:
                    func_name = child.text.decode("utf-8")

                    parent_class = find_parent_class(current, module_qn)
                    if parent_class:
                        return f"{parent_class}.{func_name}"
                    else:
                        return f"{module_qn}.{func_name}"

        current = current.parent

    return None


def count_ast_nodes(node: Node) -> int:
    """Count total AST nodes for metrics.

    Args:
        node: Root AST node

    Returns:
        Total node count
    """
    count = 1
    for child in node.children:
        count += count_ast_nodes(child)
    return count
