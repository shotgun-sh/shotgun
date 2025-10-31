"""Tests for tool registry display configuration."""

from shotgun.agents.tools.registry import (
    ToolCategory,
    ToolDisplayConfig,
    get_tool_display_config,
    register_tool_display,
    tool_registry,
)


def test_tool_registry_with_display_config():
    """Test that tool_registry decorator registers both category and display config."""

    @tool_registry(
        ToolCategory.CODEBASE_UNDERSTANDING,
        display_template='Test tool: "{query}"',
        fallback_text="Test tool",
        key_arg="query",
    )
    async def test_tool(query: str) -> str:
        return f"Result for {query}"

    # Verify display config was registered
    config = get_tool_display_config("test_tool")
    assert config is not None
    assert config.display_template == 'Test tool: "{query}"'
    assert config.fallback_text == "Test tool"
    assert config.key_arg == "query"
    assert config.hide is False


def test_tool_registry_without_display_config():
    """Test that tool_registry works without display config (backwards compatibility)."""

    @tool_registry(ToolCategory.ARTIFACT_MANAGEMENT)
    async def legacy_tool() -> str:
        return "result"

    # Verify no display config was registered
    config = get_tool_display_config("legacy_tool")
    assert config is None


def test_register_tool_display_function():
    """Test manually registering a display config for special tools."""
    register_tool_display(
        "special_tool",
        display_template='Special: "{arg}"',
        fallback_text="Special tool",
        key_arg="arg",
    )

    config = get_tool_display_config("special_tool")
    assert config is not None
    assert config.display_template == 'Special: "{arg}"'
    assert config.fallback_text == "Special tool"
    assert config.key_arg == "arg"


def test_hidden_tool():
    """Test that tools can be marked as hidden."""

    @tool_registry(
        ToolCategory.AGENT_RESPONSE,
        display_template="",
        fallback_text="",
        hide=True,
    )
    async def hidden_tool() -> str:
        return "result"

    config = get_tool_display_config("hidden_tool")
    assert config is not None
    assert config.hide is True


def test_display_config_formatting():
    """Test that ToolDisplayConfig format strings work correctly."""
    config = ToolDisplayConfig(
        display_template='Searching: "{query}"',
        fallback_text="Searching",
        key_arg="query",
    )

    # Test successful formatting
    result = config.display_template.format(query="test search")
    assert result == 'Searching: "test search"'

    # Test fallback when key is missing
    assert config.fallback_text == "Searching"


def test_registered_tool_display_configs():
    """Test that actual tools have their display configs registered."""
    # Check codebase tools
    query_graph_config = get_tool_display_config("query_graph")
    assert query_graph_config is not None
    assert "query" in query_graph_config.display_template
    assert query_graph_config.key_arg == "query"

    retrieve_code_config = get_tool_display_config("retrieve_code")
    assert retrieve_code_config is not None
    assert "qualified_name" in retrieve_code_config.display_template
    assert retrieve_code_config.key_arg == "qualified_name"

    file_read_config = get_tool_display_config("file_read")
    assert file_read_config is not None
    assert "file_path" in file_read_config.display_template
    assert file_read_config.key_arg == "file_path"

    # Check file management tools
    read_file_config = get_tool_display_config("read_file")
    assert read_file_config is not None
    assert "filename" in read_file_config.display_template
    assert read_file_config.key_arg == "filename"

    write_file_config = get_tool_display_config("write_file")
    assert write_file_config is not None
    assert "filename" in write_file_config.display_template

    # Check web search tools
    openai_search_config = get_tool_display_config("openai_web_search_tool")
    assert openai_search_config is not None
    assert "query" in openai_search_config.display_template
    assert openai_search_config.key_arg == "query"

    anthropic_search_config = get_tool_display_config("anthropic_web_search_tool")
    assert anthropic_search_config is not None
    assert "query" in anthropic_search_config.display_template

    gemini_search_config = get_tool_display_config("gemini_web_search_tool")
    assert gemini_search_config is not None
    assert "query" in gemini_search_config.display_template


def test_special_tools():
    """Test that special tools are properly registered."""
    # final_result should be hidden
    final_result_config = get_tool_display_config("final_result")
    assert final_result_config is not None
    assert final_result_config.hide is True

    # web_search builtin tool should be registered
    web_search_config = get_tool_display_config("web_search")
    assert web_search_config is not None
    assert "query" in web_search_config.display_template
