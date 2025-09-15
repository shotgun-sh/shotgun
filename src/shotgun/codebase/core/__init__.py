"""Core components for codebase understanding."""

from shotgun.codebase.core.code_retrieval import (
    CodeSnippet,
    retrieve_code_by_cypher,
    retrieve_code_by_qualified_name,
)
from shotgun.codebase.core.ingestor import (
    CodebaseIngestor,
    Ingestor,
    SimpleGraphBuilder,
)
from shotgun.codebase.core.language_config import (
    LANGUAGE_CONFIGS,
    LanguageConfig,
    get_language_config,
)
from shotgun.codebase.core.manager import CodebaseGraphManager
from shotgun.codebase.core.nl_query import (
    clean_cypher_response,
    generate_cypher,
    generate_cypher_openai_async,
)
from shotgun.codebase.core.parser_loader import load_parsers

__all__ = [
    # Ingestor classes
    "CodebaseIngestor",
    "Ingestor",
    "SimpleGraphBuilder",
    "CodebaseGraphManager",
    # Language configuration
    "LanguageConfig",
    "LANGUAGE_CONFIGS",
    "get_language_config",
    # Parser loading
    "load_parsers",
    # Natural language query
    "generate_cypher",
    "generate_cypher_openai_async",
    "clean_cypher_response",
    # Code retrieval
    "CodeSnippet",
    "retrieve_code_by_qualified_name",
    "retrieve_code_by_cypher",
]
