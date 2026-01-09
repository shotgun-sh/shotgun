"""Python language extractor implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from shotgun.codebase.core.extractors.base import BaseExtractor
from shotgun.codebase.core.extractors.types import SupportedLanguage

if TYPE_CHECKING:
    from tree_sitter import Node


class PythonExtractor(BaseExtractor):
    """Extractor for Python source code."""

    @property
    def language(self) -> SupportedLanguage:
        """The language this extractor handles."""
        return SupportedLanguage.PYTHON

    def _class_definition_types(self) -> list[str]:
        """Return node types that represent class definitions."""
        return ["class_definition"]

    def _function_definition_types(self) -> list[str]:
        """Return node types that represent function definitions."""
        return ["function_definition"]

    def extract_decorators(self, node: Node) -> list[str]:
        """Extract decorators from a function or class node.

        Args:
            node: The AST node (function or class definition)

        Returns:
            List of decorator names
        """
        decorators: list[str] = []

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

    def extract_docstring(self, node: Node) -> str | None:
        """Extract docstring from a function or class node.

        Args:
            node: The AST node (function or class definition)

        Returns:
            The docstring content, or None if not present
        """
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

        return None

    def extract_inheritance(self, class_node: Node) -> list[str]:
        """Extract parent class names from a class definition.

        Args:
            class_node: The class definition AST node

        Returns:
            List of parent class names (simple names, may need resolution)
        """
        parent_names: list[str] = []

        for child in class_node.children:
            if child.type == "argument_list":
                for arg in child.children:
                    if arg.type == "identifier" and arg.text:
                        parent_names.append(arg.text.decode("utf-8"))
                    elif arg.type == "attribute":
                        full_name_parts: list[str] = []
                        self._extract_full_name(arg, full_name_parts)
                        if full_name_parts:
                            parent_names.append(".".join(full_name_parts))

        return parent_names

    def parse_call_node(self, call_node: Node) -> tuple[str | None, str | None]:
        """Parse a call expression node to extract callee information.

        Args:
            call_node: The call expression AST node

        Returns:
            Tuple of (callee_name, object_name)
        """
        callee_name = None
        object_name = None

        for child in call_node.children:
            if child.type == "identifier" and child.text:
                callee_name = child.text.decode("utf-8")
                break
            elif child.type == "attribute":
                obj_node = child.child_by_field_name("object")
                attr_node = child.child_by_field_name("attribute")
                if obj_node and obj_node.text:
                    object_name = obj_node.text.decode("utf-8")
                if attr_node and attr_node.text:
                    callee_name = attr_node.text.decode("utf-8")
                    break

        return callee_name, object_name
