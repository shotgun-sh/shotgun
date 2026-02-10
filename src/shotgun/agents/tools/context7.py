"""Context7 MCP server integration for documentation lookup."""

from pydantic_ai.mcp import MCPServerStreamableHTTP

from shotgun.agents.config import get_config_manager
from shotgun.logging_config import get_logger

logger = get_logger(__name__)

CONTEXT7_MCP_URL = "https://mcp.context7.com/mcp"


async def get_context7_mcp_server() -> MCPServerStreamableHTTP | None:
    """Get Context7 MCP server if API key is configured.

    Returns:
        MCPServerStreamableHTTP instance if Context7 API key is set, None otherwise.
    """
    config_manager = get_config_manager()
    api_key = await config_manager.get_context7_api_key()

    if not api_key:
        return None

    logger.info("Context7 MCP server configured for documentation lookup")
    return MCPServerStreamableHTTP(
        CONTEXT7_MCP_URL,
        headers={"CONTEXT7_API_KEY": api_key},
        tool_prefix="context7",
    )
