# MCP Integration Design

**Goal:** Replace the primitive `McpCallTool` (spawns subprocess per call) with persistent MCP client connections that auto-register remote tools as `mcp_<server>_<tool>` in the ToolRegistry.

**Architecture:** A new `py-agent/mcp/client.py` module handles connection management (stdio/SSE/streamableHttp via the `mcp` SDK), tool wrapping (each MCP tool becomes a `Tool` subclass), and lifecycle (connect on startup, clean close on shutdown). Configured via `MCP_SERVERS` env var (JSON, Claude Desktop compatible format). The old `McpCallTool` is removed.

**Tech Stack:** `mcp>=1.26.0` SDK, Python 3.10+

---

## Files

| File | Action |
|------|--------|
| `py-agent/mcp/client.py` | **Create** — MCP connection + tool wrapping + lifecycle |
| `py-agent/tools.py` | **Modify** — remove `McpCallTool`, don't register it in `create_default_registry()` |
| `py-agent/tools.py:create_default_registry()` | **Modify** — call `connect_mcp_servers()` if `MCP_SERVERS` is set |
| `py-agent/requirements.txt` | **Modify** — add `mcp>=1.26.0` |

---

## Configuration

```bash
MCP_SERVERS='{
  "filesystem": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
  },
  "web-search": {
    "url": "https://mcp.example.com/sse",
    "headers": {"Authorization": "Bearer xxx"}
  }
}'
```

Transport auto-detection:
- Has `command` → stdio
- URL ends with `/sse` → SSE
- URL doesn't end with `/sse` → streamableHttp

---

## Data Flow

```
LLM calls "mcp_filesystem_read_file"
  → ToolRegistry.execute("mcp_filesystem_read_file", {"path": "/tmp/foo"})
    → MCPToolWrapper.execute(path="/tmp/foo")
      → session.call_tool("read_file", arguments={"path": "/tmp/foo"})
        → JSON-RPC over stdio/SSE/HTTP to MCP server
      → extract TextContent blocks → joined string
    → return string to LLM
```

## Lifecycle

- **Connect**: In `create_default_registry()`, if `MCP_SERVERS` is set, call `connect_mcp_servers()`. Errors are logged but don't block registry creation.
- **Close**: Add `close_mcp_servers()` call in `agent_loop.py` agent loop shutdown path.
- **Reconnect**: Not implemented in v1 (server stays connected until agent shutdown).
