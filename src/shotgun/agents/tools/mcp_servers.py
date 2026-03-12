"""User-configured MCP server loading."""

from pydantic_ai.mcp import MCPServer, MCPServerStdio, MCPServerStreamableHTTP

from shotgun.agents.config import get_config_manager
from shotgun.agents.config.models import MCPServerEntry, MCPTransport
from shotgun.logging_config import get_logger

logger = get_logger(__name__)


def _create_mcp_server(entry: MCPServerEntry) -> MCPServer:
    """Create a pydantic-ai MCPServer from a config entry.

    Args:
        entry: MCP server configuration entry

    Returns:
        Configured MCPServer instance
    """
    if entry.transport == MCPTransport.STDIO:
        if not entry.command:
            raise ValueError(
                f"MCP server '{entry.name}' has stdio transport but no command"
            )
        return MCPServerStdio(
            entry.command,
            args=entry.args,
            env=entry.env if entry.env else None,
            tool_prefix=entry.name,
        )
    else:
        if not entry.url:
            raise ValueError(f"MCP server '{entry.name}' has http transport but no url")
        return MCPServerStreamableHTTP(
            entry.url,
            headers=entry.headers if entry.headers else None,
            tool_prefix=entry.name,
        )


async def get_user_mcp_servers() -> list[MCPServer]:
    """Load user-configured MCP servers from config.

    Returns:
        List of MCPServer instances ready for use with pydantic-ai agents
    """
    config_manager = get_config_manager()
    entries = await config_manager.get_mcp_servers()

    servers: list[MCPServer] = []
    for entry in entries:
        try:
            server = _create_mcp_server(entry)
            servers.append(server)
            logger.info("Loaded user MCP server: %s (%s)", entry.name, entry.transport)
        except Exception as e:
            logger.warning("Failed to create MCP server '%s': %s", entry.name, e)

    return servers


def get_user_mcp_server_names() -> list[str]:
    """Get names of configured MCP servers (sync, for prompt context).

    Returns:
        List of MCP server names
    """
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're inside an event loop - use the config manager's cached config
        config_manager = get_config_manager()
        if config_manager._config is not None:
            return [s.name for s in config_manager._config.mcp_servers]
        return []
    else:
        config_manager = get_config_manager()
        entries = asyncio.run(config_manager.get_mcp_servers())
        return [e.name for e in entries]
