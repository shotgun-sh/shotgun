"""Language configuration for Tree-sitter parsing."""

from dataclasses import dataclass, field
from pathlib import Path

# =============================================================================
# COMMON EXCLUSIONS (applied to all languages)
# =============================================================================

# Version control
VCS_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
}

# Editor and IDE directories
EDITOR_DIRECTORIES = {
    ".idea",
    ".vscode",
    ".vs",
    ".eclipse",
    ".settings",
}

# AI assistant directories
AI_ASSISTANT_DIRECTORIES = {
    ".claude",
    ".cursor",
    ".copilot",
}

# Generic build/output directories (language-agnostic)
GENERIC_BUILD_DIRECTORIES = {
    "build",
    "dist",
    "out",
    "tmp",
    "temp",
    "coverage",
}

# All common directories to ignore (union of above)
COMMON_IGNORE_DIRECTORIES = (
    VCS_DIRECTORIES
    | EDITOR_DIRECTORIES
    | AI_ASSISTANT_DIRECTORIES
    | GENERIC_BUILD_DIRECTORIES
)


# =============================================================================
# LANGUAGE-SPECIFIC EXCLUSIONS
# =============================================================================

PYTHON_IGNORE_DIRECTORIES = {
    # Virtual environments
    "venv",
    ".venv",
    "env",
    ".env",
    "virtualenv",
    ".virtualenv",
    # Package/build artifacts
    "__pycache__",
    ".eggs",
    "*.egg-info",
    ".tox",
    ".nox",
    # Tool caches
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".coverage",
    ".hypothesis",
    # Build outputs
    "site-packages",
}

JAVASCRIPT_IGNORE_DIRECTORIES = {
    # Dependencies
    "node_modules",
    "bower_components",
    # Framework build outputs
    ".next",
    ".nuxt",
    ".vite",
    ".svelte-kit",
    ".output",
    # Package managers
    ".yarn",
    ".pnpm-store",
    # Build tools
    ".turbo",
    ".parcel-cache",
    ".cache",
    # Deployment
    ".vercel",
    ".netlify",
    ".serverless",
}

TYPESCRIPT_IGNORE_DIRECTORIES = JAVASCRIPT_IGNORE_DIRECTORIES | {
    # TypeScript-specific
    ".tsbuildinfo",
}

GO_IGNORE_DIRECTORIES = {
    # Vendored dependencies
    "vendor",
    # Build output (common convention)
    "bin",
}

RUST_IGNORE_DIRECTORIES = {
    # Cargo build output
    "target",
}

RUBY_IGNORE_DIRECTORIES = {
    # Bundler
    ".bundle",
    "vendor/bundle",
}

JAVA_IGNORE_DIRECTORIES = {
    # Gradle
    ".gradle",
    "gradle",
    # Maven
    ".m2",
    "target",
    # IDE
    ".apt_generated",
}

CSHARP_IGNORE_DIRECTORIES = {
    # Build outputs
    "bin",
    "obj",
    # NuGet
    "packages",
    ".nuget",
}

PHP_IGNORE_DIRECTORIES = {
    # Composer
    "vendor",
}


@dataclass
class LanguageConfig:
    """Configuration for language-specific Tree-sitter parsing."""

    name: str
    file_extensions: list[str]
    function_node_types: list[str]
    class_node_types: list[str] = field(default_factory=list)
    module_node_types: list[str] = field(default_factory=list)
    call_node_types: list[str] = field(default_factory=list)
    decorator_node_types: list[str] = field(default_factory=list)
    import_node_types: list[str] = field(default_factory=list)
    import_from_node_types: list[str] = field(default_factory=list)
    package_indicators: list[str] = field(default_factory=list)
    ignore_directories: set[str] = field(default_factory=set)
    function_query: str | None = None
    class_query: str | None = None
    call_query: str | None = None
    import_query: str | None = None


# Language configurations
LANGUAGE_CONFIGS = {
    "python": LanguageConfig(
        name="python",
        file_extensions=[".py"],
        function_node_types=["function_definition"],
        class_node_types=["class_definition"],
        module_node_types=["module"],
        call_node_types=["call"],
        decorator_node_types=["decorator"],
        import_node_types=["import_statement"],
        import_from_node_types=["import_from_statement"],
        package_indicators=["__init__.py"],
        ignore_directories=PYTHON_IGNORE_DIRECTORIES,
        function_query="""
    (function_definition
      name: (identifier) @function_name
      parameters: (parameters) @params
      body: (block) @body
    ) @function
    """,
        class_query="""
    (class_definition
      name: (identifier) @class_name
      body: (block) @body
    ) @class
    """,
        call_query="""
    (call
      function: [
        (identifier) @call_name
        (attribute
          object: (identifier)? @object
          attribute: (identifier) @method
        )
      ]
    ) @call
    """,
        import_query="""
    [
      (import_statement
        name: (dotted_name) @import_name
      ) @import
      (import_from_statement
        module_name: (dotted_name)? @module_name
        name: (dotted_name)? @import_name
      ) @import_from
      (import_from_statement
        module_name: (dotted_name)? @module_name
        name: (aliased_import
          name: (dotted_name) @import_name
          alias: (identifier) @alias
        )
      ) @import_from_alias
    ]
    """,
    ),
    "javascript": LanguageConfig(
        name="javascript",
        file_extensions=[".js", ".jsx", ".mjs", ".cjs"],
        function_node_types=[
            "function_declaration",
            "function_expression",
            "arrow_function",
            "method_definition",
            "generator_function_declaration",
            "generator_function",
        ],
        class_node_types=["class_declaration", "class_expression"],
        module_node_types=["program"],
        call_node_types=["call_expression"],
        import_node_types=["import_statement"],
        import_from_node_types=["import_statement"],
        package_indicators=["package.json"],
        ignore_directories=JAVASCRIPT_IGNORE_DIRECTORIES,
        function_query="""
    [
      (function_declaration name: (identifier) @function_name) @function
      (function_expression name: (identifier)? @function_name) @function
      (arrow_function) @function
      (method_definition
        name: (property_identifier) @function_name
      ) @function
      (variable_declarator
        name: (identifier) @function_name
        value: [(arrow_function) (function_expression)]
      ) @function
    ]
    """,
        class_query="""
    [
      (class_declaration name: (identifier) @class_name) @class
      (class_expression name: (identifier)? @class_name) @class
    ]
    """,
        call_query="""
    (call_expression
      function: [
        (identifier) @call_name
        (member_expression
          object: (identifier)? @object
          property: (property_identifier) @method
        )
      ]
    ) @call
    """,
    ),
    "typescript": LanguageConfig(
        name="typescript",
        file_extensions=[".ts", ".tsx"],
        function_node_types=[
            "function_declaration",
            "function_expression",
            "arrow_function",
            "method_definition",
            "method_signature",
            "generator_function_declaration",
            "generator_function",
        ],
        class_node_types=[
            "class_declaration",
            "class_expression",
            "interface_declaration",
            "type_alias_declaration",
        ],
        module_node_types=["program"],
        call_node_types=["call_expression"],
        import_node_types=["import_statement"],
        import_from_node_types=["import_statement"],
        package_indicators=["package.json", "tsconfig.json"],
        ignore_directories=TYPESCRIPT_IGNORE_DIRECTORIES,
        function_query="""
    [
      (function_declaration name: (identifier) @function_name) @function
      (function_expression name: (identifier)? @function_name) @function
      (arrow_function) @function
      (method_definition
        name: (property_identifier) @function_name
      ) @function
      (method_signature
        name: (property_identifier) @function_name
      ) @function
      (variable_declarator
        name: (identifier) @function_name
        value: [(arrow_function) (function_expression)]
      ) @function
    ]
    """,
        class_query="""
    [
      (class_declaration name: (type_identifier) @class_name) @class
      (interface_declaration name: (type_identifier) @class_name) @interface
      (type_alias_declaration name: (type_identifier) @class_name) @type_alias
    ]
    """,
        call_query="""
    (call_expression
      function: [
        (identifier) @call_name
        (member_expression
          object: (identifier)? @object
          property: (property_identifier) @method
        )
      ]
    ) @call
    """,
    ),
    "go": LanguageConfig(
        name="go",
        file_extensions=[".go"],
        function_node_types=["function_declaration", "method_declaration"],
        class_node_types=["type_declaration"],
        module_node_types=["source_file"],
        call_node_types=["call_expression"],
        import_node_types=["import_declaration"],
        import_from_node_types=["import_spec"],
        package_indicators=["go.mod", "go.sum"],
        ignore_directories=GO_IGNORE_DIRECTORIES,
        function_query="""
    [
      (function_declaration
        name: (identifier) @function_name
      ) @function
      (method_declaration
        receiver: (parameter_list
          (parameter_declaration
            type: [
              (type_identifier) @receiver_type
              (pointer_type (type_identifier) @receiver_type)
            ]
          )
        )
        name: (field_identifier) @function_name
      ) @method
    ]
    """,
        class_query="""
    (type_declaration
      (type_spec
        name: (type_identifier) @class_name
        type: [
          (struct_type) @struct
          (interface_type) @interface
        ]
      )
    ) @type
    """,
        call_query="""
    (call_expression
      function: [
        (identifier) @call_name
        (selector_expression
          operand: (identifier)? @object
          field: (field_identifier) @method
        )
      ]
    ) @call
    """,
    ),
    "rust": LanguageConfig(
        name="rust",
        file_extensions=[".rs"],
        function_node_types=["function_item", "closure_expression"],
        class_node_types=["struct_item", "enum_item", "trait_item", "impl_item"],
        module_node_types=["source_file", "mod_item"],
        call_node_types=["call_expression"],
        import_node_types=["use_declaration"],
        import_from_node_types=["use_as_clause", "use_list"],
        package_indicators=["Cargo.toml"],
        ignore_directories=RUST_IGNORE_DIRECTORIES,
        function_query="""
    [
      (function_item
        name: (identifier) @function_name
      ) @function
      (impl_item
        type: (type_identifier) @impl_type
        body: (declaration_list
          (function_item
            name: (identifier) @method_name
          ) @method
        )
      )
    ]
    """,
        class_query="""
    [
      (struct_item name: (type_identifier) @class_name) @struct
      (enum_item name: (type_identifier) @class_name) @enum
      (trait_item name: (type_identifier) @class_name) @trait
    ]
    """,
        call_query="""
    (call_expression
      function: [
        (identifier) @call_name
        (field_expression
          value: (identifier)? @object
          field: (field_identifier) @method
        )
        (scoped_identifier
          path: (identifier)? @module
          name: (identifier) @call_name
        )
      ]
    ) @call
    """,
    ),
}


def get_language_config(file_extension: str) -> LanguageConfig | None:
    """Get language configuration based on file extension."""
    for config in LANGUAGE_CONFIGS.values():
        if file_extension in config.file_extensions:
            return config
    return None


def get_all_ignore_directories() -> set[str]:
    """Get all ignore directories (common + all language-specific).

    This is useful when indexing a codebase with multiple languages
    or when you don't know what languages are present.
    """
    all_ignores = COMMON_IGNORE_DIRECTORIES.copy()
    for config in LANGUAGE_CONFIGS.values():
        all_ignores |= config.ignore_directories
    return all_ignores


def get_ignore_directories_for_languages(languages: list[str]) -> set[str]:
    """Get ignore directories for specific languages.

    Args:
        languages: List of language names (e.g., ["python", "typescript"])

    Returns:
        Common ignores + language-specific ignores for the given languages
    """
    ignores = COMMON_IGNORE_DIRECTORIES.copy()
    for lang in languages:
        if lang in LANGUAGE_CONFIGS:
            ignores |= LANGUAGE_CONFIGS[lang].ignore_directories
    return ignores


def should_ignore_directory(name: str, ignore_patterns: set[str] | None = None) -> bool:
    """Check if a directory should be ignored.

    Args:
        name: Directory name (not full path)
        ignore_patterns: Optional custom ignore patterns. If None, uses all patterns.

    Returns:
        True if directory should be ignored
    """
    patterns = (
        ignore_patterns if ignore_patterns is not None else get_all_ignore_directories()
    )

    # Check explicit patterns
    if name in patterns:
        return True

    # Check for glob patterns like "*.egg-info"
    for pattern in patterns:
        if pattern.startswith("*") and name.endswith(pattern[1:]):
            return True

    # Hidden directories (starting with .) are always ignored
    if name.startswith("."):
        return True

    return False


def should_ignore_file(name: str) -> bool:
    """Check if a file should be ignored.

    Args:
        name: File name (not full path)

    Returns:
        True if file should be ignored (hidden files starting with .)
    """
    return name.startswith(".")


def is_path_ignored(path: str | Path, ignore_patterns: set[str] | None = None) -> bool:
    """Check if any part of a path should be ignored.

    Args:
        path: File or directory path (can be relative or absolute)
        ignore_patterns: Optional custom ignore patterns

    Returns:
        True if any path component should be ignored
    """
    path_obj = Path(path) if isinstance(path, str) else path
    for part in path_obj.parts:
        if should_ignore_directory(part, ignore_patterns):
            return True
    return False
