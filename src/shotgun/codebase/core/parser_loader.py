"""Tree-sitter parser loader for code parsing."""

import sys
from collections.abc import Callable
from typing import Any

from tree_sitter import Language, Parser

from shotgun.codebase.core.language_config import LANGUAGE_CONFIGS
from shotgun.logging_config import get_logger

logger = get_logger(__name__)


def load_parsers() -> tuple[dict[str, Parser], dict[str, Any]]:
    """Load available Tree-sitter parsers and compile their queries.

    Returns:
        Tuple of (parsers dict, queries dict)
    """
    parsers: dict[str, Parser] = {}
    queries: dict[str, Any] = {}
    available_languages = []

    # Try to import available language libraries
    language_loaders: dict[str, Callable[[], Any]] = {}

    # Try individual language imports first
    try:
        import tree_sitter_python

        language_loaders["python"] = lambda: tree_sitter_python.language()
        available_languages.append("python")
    except ImportError as e:
        logger.warning(f"Failed to import tree_sitter_python: {e}")

    try:
        import tree_sitter_javascript

        language_loaders["javascript"] = lambda: tree_sitter_javascript.language()
        available_languages.append("javascript")
    except ImportError as e:
        logger.warning(f"Failed to import tree_sitter_javascript: {e}")

    try:
        import tree_sitter_typescript

        language_loaders["typescript"] = (
            lambda: tree_sitter_typescript.language_typescript()
        )
        available_languages.append("typescript")
    except ImportError as e:
        logger.warning(f"Failed to import tree_sitter_typescript: {e}")

    try:
        import tree_sitter_go

        language_loaders["go"] = lambda: tree_sitter_go.language()
        available_languages.append("go")
    except ImportError as e:
        logger.warning(f"Failed to import tree_sitter_go: {e}")

    try:
        import tree_sitter_rust

        language_loaders["rust"] = lambda: tree_sitter_rust.language()
        available_languages.append("rust")
    except ImportError as e:
        logger.warning(f"Failed to import tree_sitter_rust: {e}")

    logger.info(f"Available languages: {', '.join(available_languages)}")

    # Create parsers for available languages
    for lang_name, lang_loader in language_loaders.items():
        if lang_name in LANGUAGE_CONFIGS:
            try:
                parser = Parser()
                # Handle both function and direct language object
                if callable(lang_loader):
                    lang_obj = lang_loader()
                else:
                    lang_obj = lang_loader

                # Create Language object if needed
                if not isinstance(lang_obj, Language):
                    lang_obj = Language(lang_obj)

                parser.language = lang_obj
                parsers[lang_name] = parser

                # Compile queries for this language
                config = LANGUAGE_CONFIGS[lang_name]
                lang_queries = {}

                # Compile each query type
                for query_type in [
                    "function_query",
                    "class_query",
                    "call_query",
                    "import_query",
                ]:
                    query_text = getattr(config, query_type)
                    if query_text:
                        try:
                            lang_queries[query_type] = lang_obj.query(query_text)
                        except Exception as e:
                            logger.debug(
                                f"Failed to compile {query_type} for {lang_name}: {e}"
                            )

                if lang_queries:
                    queries[lang_name] = lang_queries

                logger.debug(f"Loaded parser for {lang_name}")

            except Exception as e:
                logger.error(f"Failed to load parser for {lang_name}: {e}")

    if not parsers:
        logger.error(
            "No parsers could be loaded. Please install language-specific tree-sitter packages."
        )
        logger.error(
            "Install with: pip install tree-sitter-python tree-sitter-javascript tree-sitter-typescript tree-sitter-go tree-sitter-rust"
        )
        sys.exit(1)

    return parsers, queries
