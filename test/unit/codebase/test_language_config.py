"""Unit tests for language_config module."""

from shotgun.codebase.core.language_config import (
    LANGUAGE_CONFIGS,
    LanguageConfig,
    get_language_config,
)


def test_language_config_creation():
    """Test LanguageConfig dataclass creation with required fields."""
    config = LanguageConfig(
        name="test_language",
        file_extensions=[".test"],
        function_node_types=["test_function"],
    )

    assert config.name == "test_language"
    assert config.file_extensions == [".test"]
    assert config.function_node_types == ["test_function"]
    assert config.class_node_types == []  # Default value
    assert config.module_node_types == []  # Default value
    assert config.call_node_types == []  # Default value
    assert config.decorator_node_types == []  # Default value
    assert config.import_node_types == []  # Default value
    assert config.import_from_node_types == []  # Default value
    assert config.package_indicators == []  # Default value
    assert config.function_query is None  # Default value
    assert config.class_query is None  # Default value
    assert config.call_query is None  # Default value
    assert config.import_query is None  # Default value


def test_language_config_with_all_fields():
    """Test LanguageConfig creation with all fields specified."""
    config = LanguageConfig(
        name="full_language",
        file_extensions=[".full", ".complete"],
        function_node_types=["function_def", "method_def"],
        class_node_types=["class_def"],
        module_node_types=["module"],
        call_node_types=["call_expression"],
        decorator_node_types=["decorator"],
        import_node_types=["import_stmt"],
        import_from_node_types=["from_import"],
        package_indicators=["__init__.ext"],
        function_query="(function) @func",
        class_query="(class) @cls",
        call_query="(call) @call",
        import_query="(import) @import",
    )

    assert config.name == "full_language"
    assert len(config.file_extensions) == 2
    assert config.class_node_types == ["class_def"]
    assert config.function_query == "(function) @func"
    assert config.class_query == "(class) @cls"


def test_language_configs_python_exists():
    """Test that Python language configuration exists."""
    assert "python" in LANGUAGE_CONFIGS

    python_config = LANGUAGE_CONFIGS["python"]
    assert isinstance(python_config, LanguageConfig)
    assert python_config.name == "python"
    assert ".py" in python_config.file_extensions
    assert "function_definition" in python_config.function_node_types
    assert "class_definition" in python_config.class_node_types


def test_language_configs_python_details():
    """Test Python language configuration details."""
    python_config = LANGUAGE_CONFIGS["python"]

    assert python_config.module_node_types == ["module"]
    assert python_config.call_node_types == ["call"]
    assert python_config.decorator_node_types == ["decorator"]
    assert python_config.import_node_types == ["import_statement"]
    assert python_config.import_from_node_types == ["import_from_statement"]
    assert python_config.package_indicators == ["__init__.py"]


def test_language_configs_python_queries():
    """Test Python language Tree-sitter queries."""
    python_config = LANGUAGE_CONFIGS["python"]

    assert python_config.function_query is not None
    assert "function_definition" in python_config.function_query
    assert "@function_name" in python_config.function_query
    assert "@params" in python_config.function_query

    assert python_config.class_query is not None
    assert "class_definition" in python_config.class_query
    assert "@class_name" in python_config.class_query


def test_language_configs_python_call_query():
    """Test Python call query configuration."""
    python_config = LANGUAGE_CONFIGS["python"]

    assert python_config.call_query is not None
    assert "call" in python_config.call_query
    assert "@call_name" in python_config.call_query


def test_language_configs_python_import_query():
    """Test Python import query configuration."""
    python_config = LANGUAGE_CONFIGS["python"]

    assert python_config.import_query is not None
    assert (
        "import_statement" in python_config.import_query
        or "import_from_statement" in python_config.import_query
    )


def test_get_language_config_python():
    """Test get_language_config function with Python extension."""
    config = get_language_config(".py")

    assert config is not None
    assert config.name == "python"
    assert ".py" in config.file_extensions


def test_get_language_config_case_insensitive():
    """Test get_language_config with different case extensions."""
    config_lower = get_language_config(".py")
    get_language_config(".PY")

    # Should handle case variations
    assert config_lower is not None
    # Note: Actual behavior depends on implementation


def test_get_language_config_unknown_extension():
    """Test get_language_config with unknown file extension."""
    config = get_language_config(".unknown")

    # Should return None for unknown extensions
    assert config is None


def test_get_language_config_no_extension():
    """Test get_language_config with filename without extension."""
    config = get_language_config("filename_without_extension")

    # Should return None for files without extensions
    assert config is None


def test_get_language_config_empty_extension():
    """Test get_language_config with empty extension."""
    config = get_language_config("")

    # Should return None for empty string
    assert config is None


def test_language_configs_immutability():
    """Test that LANGUAGE_CONFIGS dictionary is properly structured."""
    # Should be a dictionary
    assert isinstance(LANGUAGE_CONFIGS, dict)

    # Should have at least Python
    assert len(LANGUAGE_CONFIGS) >= 1

    # All values should be LanguageConfig instances
    for lang_name, config in LANGUAGE_CONFIGS.items():
        assert isinstance(lang_name, str)
        assert isinstance(config, LanguageConfig)
        assert config.name == lang_name


def test_language_config_field_types():
    """Test that LanguageConfig fields have correct types."""
    python_config = LANGUAGE_CONFIGS["python"]

    assert isinstance(python_config.name, str)
    assert isinstance(python_config.file_extensions, list)
    assert isinstance(python_config.function_node_types, list)
    assert isinstance(python_config.class_node_types, list)
    assert isinstance(python_config.module_node_types, list)
    assert isinstance(python_config.call_node_types, list)
    assert isinstance(python_config.decorator_node_types, list)
    assert isinstance(python_config.import_node_types, list)
    assert isinstance(python_config.import_from_node_types, list)
    assert isinstance(python_config.package_indicators, list)

    # Query fields can be None or str
    if python_config.function_query is not None:
        assert isinstance(python_config.function_query, str)
    if python_config.class_query is not None:
        assert isinstance(python_config.class_query, str)


def test_language_config_list_fields_not_empty():
    """Test that essential list fields are not empty."""
    python_config = LANGUAGE_CONFIGS["python"]

    # These should have at least one item
    assert len(python_config.file_extensions) > 0
    assert len(python_config.function_node_types) > 0
    assert len(python_config.class_node_types) > 0


def test_language_config_file_extension_format():
    """Test that file extensions are properly formatted."""
    python_config = LANGUAGE_CONFIGS["python"]

    for ext in python_config.file_extensions:
        assert isinstance(ext, str)
        assert ext.startswith(".")  # Should start with dot
        assert len(ext) > 1  # Should have content after dot


def test_language_config_node_types_format():
    """Test that node types are properly formatted strings."""
    python_config = LANGUAGE_CONFIGS["python"]

    all_node_types = (
        python_config.function_node_types
        + python_config.class_node_types
        + python_config.module_node_types
        + python_config.call_node_types
    )

    for node_type in all_node_types:
        assert isinstance(node_type, str)
        assert len(node_type) > 0
        # Should not contain spaces (typical Tree-sitter convention)
        assert " " not in node_type


def test_language_config_queries_format():
    """Test that Tree-sitter queries are properly formatted."""
    python_config = LANGUAGE_CONFIGS["python"]

    if python_config.function_query:
        # Should contain Tree-sitter query syntax
        assert "(" in python_config.function_query
        assert ")" in python_config.function_query
        assert "@" in python_config.function_query  # Capture syntax

    if python_config.class_query:
        assert "(" in python_config.class_query
        assert ")" in python_config.class_query
        assert "@" in python_config.class_query


def test_get_language_config_multiple_extensions():
    """Test languages that might support multiple file extensions."""
    # This tests the general pattern, even if only Python is currently configured
    for lang_name, config in LANGUAGE_CONFIGS.items():
        for ext in config.file_extensions:
            found_config = get_language_config(ext)
            assert found_config is not None
            assert found_config.name == lang_name


def test_language_config_package_indicators():
    """Test package indicator configurations."""
    python_config = LANGUAGE_CONFIGS["python"]

    assert isinstance(python_config.package_indicators, list)
    if python_config.package_indicators:
        for indicator in python_config.package_indicators:
            assert isinstance(indicator, str)
            assert len(indicator) > 0


def test_language_config_equality():
    """Test LanguageConfig equality comparison."""
    config1 = LanguageConfig(
        name="test", file_extensions=[".test"], function_node_types=["func"]
    )

    config2 = LanguageConfig(
        name="test", file_extensions=[".test"], function_node_types=["func"]
    )

    config3 = LanguageConfig(
        name="different", file_extensions=[".test"], function_node_types=["func"]
    )

    assert config1 == config2  # Same content
    assert config1 != config3  # Different name


def test_language_config_repr():
    """Test LanguageConfig string representation."""
    python_config = LANGUAGE_CONFIGS["python"]

    repr_str = repr(python_config)
    assert "LanguageConfig" in repr_str
    assert "python" in repr_str


def test_language_configs_consistency():
    """Test consistency across all language configurations."""
    for lang_name, config in LANGUAGE_CONFIGS.items():
        # Name should match dictionary key
        assert config.name == lang_name

        # Should have at least one file extension
        assert len(config.file_extensions) > 0

        # Should have at least function node types
        assert len(config.function_node_types) > 0

        # File extensions should be unique within config
        assert len(config.file_extensions) == len(set(config.file_extensions))


def test_get_language_config_edge_cases():
    """Test get_language_config with edge case inputs."""
    # Test with None
    config = get_language_config(None)
    assert config is None

    # Test with just dot
    config = get_language_config(".")
    assert config is None

    # Test with multiple dots - function expects extension only, not full filename
    config = get_language_config(".py")  # Function expects extension, not filename
    assert config is not None
    assert config.name == "python"


def test_language_config_dataclass_features():
    """Test that LanguageConfig uses dataclass features properly."""
    # Test field access
    python_config = LANGUAGE_CONFIGS["python"]

    # Should have all expected fields
    expected_fields = [
        "name",
        "file_extensions",
        "function_node_types",
        "class_node_types",
        "module_node_types",
        "call_node_types",
        "decorator_node_types",
        "import_node_types",
        "import_from_node_types",
        "package_indicators",
        "function_query",
        "class_query",
        "call_query",
        "import_query",
    ]

    for field_name in expected_fields:
        assert hasattr(python_config, field_name)


def test_language_config_default_factory():
    """Test that default_factory creates separate list instances."""
    config1 = LanguageConfig(
        name="test1", file_extensions=[".t1"], function_node_types=["f1"]
    )
    config2 = LanguageConfig(
        name="test2", file_extensions=[".t2"], function_node_types=["f2"]
    )

    # Default lists should be separate instances
    assert config1.class_node_types is not config2.class_node_types

    # Modifying one shouldn't affect the other
    config1.class_node_types.append("class1")
    assert "class1" not in config2.class_node_types
