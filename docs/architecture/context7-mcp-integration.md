# Context7 MCP Integration Architecture

This document describes how Shotgun integrates with Context7 via the Model Context Protocol (MCP) to provide up-to-date library documentation to the Research agent.

## Overview

Context7 is a remote MCP server that provides version-specific documentation for popular libraries. When a user configures a Context7 API key, the Research agent gains access to two documentation lookup tools that fetch real-time docs directly into the LLM context. This is an experimental feature.

## How MCP Works in Pydantic AI

Pydantic AI supports MCP servers via its `toolsets` parameter on the `Agent` class. MCP servers expose tools that the LLM can call just like regular function tools. The key classes are:

- `MCPServer` - Abstract base class for all MCP server connections
- `MCPServerStreamableHTTP` - Connects to remote MCP servers over HTTP using the Streamable HTTP transport protocol
- `MCPServerStdio` - Connects to local MCP servers via stdio
- `MCPServerSSE` - Legacy SSE transport (deprecated)

MCP servers require lifecycle management via async context managers. When entering the context (`async with agent:`), the server connection is established and tool schemas are fetched. When exiting, connections are cleaned up.

## Key Components

### 1. Context7 MCP Server Factory (`src/shotgun/agents/tools/context7.py`)

Factory function that returns an `MCPServerStreamableHTTP` instance when a Context7 API key is configured.

```python
CONTEXT7_MCP_URL = "https://mcp.context7.com/mcp"

async def get_context7_mcp_server() -> MCPServerStreamableHTTP | None:
    config_manager = get_config_manager()
    api_key = await config_manager.get_context7_api_key()
    if not api_key:
        return None
    return MCPServerStreamableHTTP(
        CONTEXT7_MCP_URL,
        headers={"CONTEXT7_API_KEY": api_key},
        tool_prefix="context7",
    )
```

The `tool_prefix="context7"` ensures all tools from this server are namespaced (e.g., `context7_resolve-library-id`).

### 2. Configuration (`src/shotgun/agents/config/`)

**Context7Config** (in `models.py`):
```python
class Context7Config(BaseModel):
    api_key: SecretStr | None = None
```

Added to `ShotgunConfig` as `context7: Context7Config`. Config version bumped from 8 to 9 with migration adding the `context7: {}` section.

**ConfigManager methods** (in `manager.py`):
- `update_context7(api_key)` - Set or clear the API key
- `get_context7_api_key()` - Retrieve the key (returns `None` for empty/whitespace values)

**CLI commands** (in `cli/config.py`):
- `shotgun config set-context7 --api-key <key>` - Store the API key
- `shotgun config clear-context7` - Remove the API key

### 3. Research Agent Integration (`src/shotgun/agents/research.py`)

The Research agent is the only agent that connects to Context7. During agent creation:

```python
context7_server = await get_context7_mcp_server()
mcp_servers = [context7_server] if context7_server else None

agent, deps = await create_base_agent(
    ...,
    mcp_servers=mcp_servers,
)
```

During execution, the agent run is wrapped in `async with agent:` to manage the MCP server lifecycle:

```python
async with agent:
    result = await run_agent(agent=agent, ...)
```

### 4. Base Agent Support (`src/shotgun/agents/common.py`)

The `create_base_agent` function accepts an optional `mcp_servers: list[MCPServer]` parameter. When present:
- MCP servers are passed to the `Agent()` constructor via `toolsets=mcp_servers`
- `deps.has_context7` is set to `True` for use in system prompt rendering

### 5. System Prompt (`src/shotgun/prompts/agents/research.j2`)

When `has_context7` is `True`, the research agent system prompt includes instructions for using Context7 tools:

```jinja2
{% if has_context7 %}
## DOCUMENTATION LOOKUP
You have access to Context7 MCP tools for fetching up-to-date library documentation:
- `context7_resolve-library-id` - Resolve a library name to a Context7 library ID
- `context7_get-library-docs` - Fetch documentation for a library using its Context7 ID
{% endif %}
```

## Context7 Tools

The Context7 MCP server exposes two tools:

| Tool | Parameters | Description |
|------|-----------|-------------|
| `resolve-library-id` | `libraryName` (required) | Resolves a library name (e.g., "pydantic-ai") to a Context7 library ID (e.g., `/pydantic/pydantic-ai`) |
| `get-library-docs` | `context7CompatibleLibraryID` (required), `topic` (optional), `tokens` (optional, default 5000) | Fetches documentation for a library, optionally filtered by topic |

The agent calls `resolve-library-id` first to get the library ID, then `get-library-docs` with specific topics to fetch relevant documentation.

## Data Flow

```
User prompt
  -> Router delegates to Research agent
    -> Research agent created with Context7 MCP server
      -> `async with agent:` establishes HTTP connection to mcp.context7.com
        -> LLM calls context7_resolve-library-id
        -> LLM calls context7_get-library-docs (one or more times)
        -> LLM synthesizes research from docs
      -> MCP connection closed
    -> Research results written to .shotgun/ files
  -> Router returns summary to user
```

## Transport Protocol

Context7 uses the **Streamable HTTP** transport (not SSE). This is important because:
- `MCPServerHTTP` / `MCPServerSSE` use the legacy SSE transport which hangs when connecting to Context7
- `MCPServerStreamableHTTP` uses HTTP POST with optional SSE response streaming, which Context7 supports
- The Streamable HTTP protocol supports session management, reconnection, and resumption

## Adding MCP Servers to Other Agents

To add MCP support to another agent (e.g., Plan agent):

1. In the agent's `create_*_agent` function, call `get_context7_mcp_server()` and pass the result as `mcp_servers` to `create_base_agent`
2. In the agent's `run_*_agent` function, wrap the agent run in `async with agent:`
3. Optionally update the agent's Jinja2 template to include Context7 tool instructions when `has_context7` is `True`
