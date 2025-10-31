"""Tests for tool registry display configuration."""

from shotgun.agents.tools.registry import (
    ToolCategory,
    ToolDisplayConfig,
    get_tool_display_config,
    register_tool,
    register_tool_display,
)


def test_register_tool_with_display_config():
    """Test that register_tool decorator registers both category and display config."""

    @register_tool(
        category=ToolCategory.CODEBASE_UNDERSTANDING,
        display_text="Test tool",
        key_arg="query",
    )
    async def test_tool(query: str) -> str:
        return f"Result for {query}"

    # Verify display config was registered
    config = get_tool_display_config("test_tool")
    assert config is not None
    assert config.display_text == "Test tool"
    assert config.key_arg == "query"
    assert config.hide is False


def test_register_tool_display_function():
    """Test manually registering a display config for special tools."""
    register_tool_display(
        "special_tool",
        display_text="Special tool",
        key_arg="arg",
    )

    config = get_tool_display_config("special_tool")
    assert config is not None
    assert config.display_text == "Special tool"
    assert config.key_arg == "arg"


def test_hidden_tool():
    """Test that tools can be marked as hidden."""

    @register_tool(
        category=ToolCategory.AGENT_RESPONSE,
        display_text="",
        key_arg="",
        hide=True,
    )
    async def hidden_tool() -> str:
        return "result"

    config = get_tool_display_config("hidden_tool")
    assert config is not None
    assert config.hide is True


def test_display_config_formatting():
    """Test that ToolDisplayConfig stores display configuration correctly."""
    config = ToolDisplayConfig(
        display_text="Searching",
        key_arg="query",
    )

    # Test config attributes
    assert config.display_text == "Searching"
    assert config.key_arg == "query"
    assert config.hide is False


def test_registered_tool_display_configs():
    """Test that actual tools have their display configs registered."""
    # Check codebase tools
    query_graph_config = get_tool_display_config("query_graph")
    assert query_graph_config is not None
    assert query_graph_config.display_text == "Querying code"
    assert query_graph_config.key_arg == "query"

    retrieve_code_config = get_tool_display_config("retrieve_code")
    assert retrieve_code_config is not None
    assert retrieve_code_config.display_text == "Retrieving code"
    assert retrieve_code_config.key_arg == "qualified_name"

    file_read_config = get_tool_display_config("file_read")
    assert file_read_config is not None
    assert file_read_config.display_text == "Reading file"
    assert file_read_config.key_arg == "file_path"

    # Check file management tools
    read_file_config = get_tool_display_config("read_file")
    assert read_file_config is not None
    assert read_file_config.display_text == "Reading file"
    assert read_file_config.key_arg == "filename"

    write_file_config = get_tool_display_config("write_file")
    assert write_file_config is not None
    assert write_file_config.display_text == "Writing file"
    assert write_file_config.key_arg == "filename"

    # Check web search tools
    openai_search_config = get_tool_display_config("openai_web_search_tool")
    assert openai_search_config is not None
    assert openai_search_config.display_text == "Searching web"
    assert openai_search_config.key_arg == "query"

    anthropic_search_config = get_tool_display_config("anthropic_web_search_tool")
    assert anthropic_search_config is not None
    assert anthropic_search_config.display_text == "Searching web"
    assert anthropic_search_config.key_arg == "query"

    gemini_search_config = get_tool_display_config("gemini_web_search_tool")
    assert gemini_search_config is not None
    assert gemini_search_config.display_text == "Searching web"
    assert gemini_search_config.key_arg == "query"


def test_special_tools():
    """Test that special tools are properly registered."""
    # final_result should be hidden
    final_result_config = get_tool_display_config("final_result")
    assert final_result_config is not None
    assert final_result_config.hide is True

    # web_search builtin tool should be registered
    web_search_config = get_tool_display_config("web_search")
    assert web_search_config is not None
    assert web_search_config.display_text == "Searching"
    assert web_search_config.key_arg == "query"
