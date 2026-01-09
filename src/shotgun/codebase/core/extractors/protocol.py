"""Protocol definition for language extractors."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from tree_sitter import Node

    from .types import SupportedLanguage


@runtime_checkable
class LanguageExtractor(Protocol):
    """Protocol for language-specific AST extraction.

    Each language implementation provides methods to extract:
    - Decorators/attributes from function/class nodes
    - Docstrings/documentation
    - Inheritance information from class definitions
    - Call expression parsing
    - Node type information for the language
    """

    @property
    def language(self) -> SupportedLanguage:
        """The language this extractor handles."""
        ...

    def extract_decorators(self, node: Node) -> list[str]:
        """Extract decorators/attributes from a function or class node.

        Args:
            node: The AST node (function or class definition)

        Returns:
            List of decorator/attribute names
        """
        ...

    def extract_docstring(self, node: Node) -> str | None:
        """Extract documentation string from a function or class node.

        Args:
            node: The AST node (function or class definition)

        Returns:
            The docstring content, or None if not present
        """
        ...

    def extract_inheritance(self, class_node: Node) -> list[str]:
        """Extract parent class names from a class definition.

        Args:
            class_node: The class definition AST node

        Returns:
            List of parent class names (simple names, may need resolution)
        """
        ...

    def parse_call_node(self, call_node: Node) -> tuple[str | None, str | None]:
        """Parse a call expression node to extract callee information.

        Args:
            call_node: The call expression AST node

        Returns:
            Tuple of (callee_name, object_name) where:
            - callee_name: The name of the function/method being called
            - object_name: The object the method is called on (for method calls)
        """
        ...

    def find_parent_class(self, func_node: Node, module_qn: str) -> str | None:
        """Find the parent class of a function node.

        Args:
            func_node: The function definition AST node
            module_qn: Module qualified name

        Returns:
            Qualified name of parent class, or None if not in a class
        """
        ...

    def find_containing_function(self, node: Node, module_qn: str) -> str | None:
        """Find the containing function/method of a node.

        Args:
            node: The AST node
            module_qn: Module qualified name

        Returns:
            Qualified name of containing function, or None
        """
        ...

    def count_ast_nodes(self, node: Node) -> int:
        """Count total AST nodes for metrics.

        Args:
            node: Root AST node

        Returns:
            Total node count
        """
        ...
