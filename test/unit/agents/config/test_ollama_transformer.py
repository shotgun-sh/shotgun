"""Tests for OllamaCompatibleJsonSchemaTransformer."""

from shotgun.agents.config.provider import OllamaCompatibleJsonSchemaTransformer


def test_simplifies_anyof_nullable_to_non_null_type():
    """Test that anyOf with null is simplified to just the non-null type."""
    schema = {
        "type": "object",
        "properties": {
            "items": {
                "anyOf": [
                    {"type": "array", "items": {"type": "string"}},
                    {"type": "null"},
                ]
            }
        },
    }

    transformer = OllamaCompatibleJsonSchemaTransformer(schema)
    result = transformer.walk()

    # anyOf should be removed
    assert "anyOf" not in result["properties"]["items"]
    # The non-null type should be used
    assert result["properties"]["items"]["type"] == "array"
    assert result["properties"]["items"]["items"]["type"] == "string"


def test_preserves_default_value_when_simplifying():
    """Test that default value is preserved when simplifying anyOf."""
    schema = {
        "type": "object",
        "properties": {
            "items": {
                "default": None,
                "anyOf": [
                    {"type": "array", "items": {"type": "string"}},
                    {"type": "null"},
                ],
            }
        },
    }

    transformer = OllamaCompatibleJsonSchemaTransformer(schema)
    result = transformer.walk()

    # default should be preserved
    assert result["properties"]["items"]["default"] is None


def test_simplifies_oneof_nullable_to_non_null_type():
    """Test that oneOf with null is simplified to just the non-null type."""
    schema = {
        "type": "object",
        "properties": {
            "value": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ]
            }
        },
    }

    transformer = OllamaCompatibleJsonSchemaTransformer(schema)
    result = transformer.walk()

    # oneOf should be removed
    assert "oneOf" not in result["properties"]["value"]
    assert result["properties"]["value"]["type"] == "string"


def test_handles_complex_nested_anyof():
    """Test handling of nested anyOf structures."""
    schema = {
        "type": "object",
        "properties": {
            "questions": {
                "anyOf": [
                    {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    {"type": "null"},
                ],
            },
            "response": {"type": "string"},
        },
    }

    transformer = OllamaCompatibleJsonSchemaTransformer(schema)
    result = transformer.walk()

    # questions should be simplified
    assert "anyOf" not in result["properties"]["questions"]
    assert result["properties"]["questions"]["type"] == "array"
    # response should be unchanged
    assert result["properties"]["response"]["type"] == "string"


def test_keeps_non_nullable_anyof_unchanged():
    """Test that anyOf without null type is kept unchanged."""
    schema = {
        "type": "object",
        "properties": {
            "value": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "integer"},
                ]
            }
        },
    }

    transformer = OllamaCompatibleJsonSchemaTransformer(schema)
    result = transformer.walk()

    # anyOf should be kept since it's not a simple nullable union
    assert "anyOf" in result["properties"]["value"]


def test_inlines_defs_references():
    """Test that $defs references are inlined."""
    schema = {
        "$defs": {"StringArray": {"type": "array", "items": {"type": "string"}}},
        "type": "object",
        "properties": {"items": {"$ref": "#/$defs/StringArray"}},
    }

    transformer = OllamaCompatibleJsonSchemaTransformer(schema)
    result = transformer.walk()

    # $defs and $ref should be inlined
    assert "$defs" not in result
    assert "$ref" not in result["properties"]["items"]
    assert result["properties"]["items"]["type"] == "array"
