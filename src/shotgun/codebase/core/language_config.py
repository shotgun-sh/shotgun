"""Language configuration for Tree-sitter parsing."""

from dataclasses import dataclass, field


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
