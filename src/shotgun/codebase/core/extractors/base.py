"""Base extractor with shared extraction logic."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Node

    from .types import SupportedLanguage


class BaseExtractor(ABC):
    """Abstract base class for language extractors.

    Provides shared extraction logic that works across languages,
    with abstract methods for language-specific operations.
    """

    @property
    @abstractmethod
    def language(self) -> SupportedLanguage:
        """The language this extractor handles."""
        ...

    @abstractmethod
    def extract_decorators(self, node: Node) -> list[str]:
        """Extract decorators/attributes from a function or class node."""
        ...

    @abstractmethod
    def extract_docstring(self, node: Node) -> str | None:
        """Extract documentation string from a function or class node."""
        ...

    @abstractmethod
    def extract_inheritance(self, class_node: Node) -> list[str]:
        """Extract parent class names from a class definition."""
        ...

    @abstractmethod
    def parse_call_node(self, call_node: Node) -> tuple[str | None, str | None]:
        """Parse a call expression node to extract callee information."""
        ...

    @abstractmethod
    def _class_definition_types(self) -> list[str]:
        """Return node types that represent class definitions."""
        ...

    @abstractmethod
    def _function_definition_types(self) -> list[str]:
        """Return node types that represent function definitions."""
        ...

    def find_parent_class(self, func_node: Node, module_qn: str) -> str | None:
        """Find the parent class of a function node.

        Args:
            func_node: The function definition AST node
            module_qn: Module qualified name

        Returns:
            Qualified name of parent class, or None if not in a class
        """
        current = func_node.parent

        while current:
            if current.type in self._class_definition_types():
                for child in current.children:
                    if child.type == "identifier" and child.text:
                        class_name = child.text.decode("utf-8")
                        return f"{module_qn}.{class_name}"

            current = current.parent

        return None

    def find_containing_function(self, node: Node, module_qn: str) -> str | None:
        """Find the containing function/method of a node.

        Args:
            node: The AST node
            module_qn: Module qualified name

        Returns:
            Qualified name of containing function, or None
        """
        current = node.parent

        while current:
            if current.type in self._function_definition_types():
                for child in current.children:
                    if child.type == "identifier" and child.text:
                        func_name = child.text.decode("utf-8")

                        parent_class = self.find_parent_class(current, module_qn)
                        if parent_class:
                            return f"{parent_class}.{func_name}"
                        else:
                            return f"{module_qn}.{func_name}"

            current = current.parent

        return None

    def count_ast_nodes(self, node: Node) -> int:
        """Count total AST nodes for metrics.

        Args:
            node: Root AST node

        Returns:
            Total node count
        """
        count = 1
        for child in node.children:
            count += self.count_ast_nodes(child)
        return count

    def _extract_full_name(self, node: Node, parts: list[str]) -> None:
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
                self._extract_full_name(obj_node, parts)
