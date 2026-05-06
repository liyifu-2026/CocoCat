# MCP Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Replace primitive `McpCallTool` (subprocess-per-call) with persistent MCP client connections that auto-register remote tools.

**Architecture:** New `py-agent/mcp/client.py` handles connection management (stdio/SSE/streamableHttp via `mcp` SDK), wraps MCP tools as `Tool` subclasses, and manages lifecycle. Configured via `MCP_SERVERS` env var. Old `McpCallTool` removed.

**Tech Stack:** `mcp>=1.26.0` SDK, Python 3.10+

---

## File Structure

```
Create: py-agent/mcp/client.py        — MCPToolWrapper + connect_mcp_servers + close
Modify: py-agent/tools.py             — remove McpCallTool, wire MCP into create_default_registry()
Modify: py-agent/requirements.txt     — add mcp>=1.26.0
```

---

### Task 1: Install dependency + verify

- [ ] **Step 1: Install mcp SDK**

```bash
pip install "mcp>=1.26.0"
```

- [ ] **Step 2: Verify it works**

```bash
python3 -c "import mcp; from mcp import ClientSession, StdioServerParameters; print(f'mcp {mcp.__version__}')"
```

---

### Task 2: Create `py-agent/mcp/client.py`

**Files:**
- Create: `py-agent/mcp/client.py`

- [ ] **Step 1: Write `py-agent/mcp/client.py`**

```python
"""MCP client — connect to MCP servers and wrap their tools for the ToolRegistry."""
from __future__ import annotations

import json
import os
import sys
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client


def _sanitize_name(name: str) -> str:
    """Sanitize server/tool name for use as a tool identifier."""
    result = []
    for ch in name:
        if ch.isalnum() or ch == "_":
            result.append(ch)
        else:
            result.append("_")
    return "".join(result).strip("_").lower()


def _normalize_schema(schema: dict) -> dict:
    """Normalize MCP JSON Schema for OpenAI compatibility (nullable unions)."""
    result = {}
    for key, value in schema.items():
        if key == "type" and isinstance(value, list):
            if "null" in value:
                result["type"] = [t for t in value if t != "null"][0]
                result["nullable"] = True
            else:
                result["type"] = value[0] if len(value) == 1 else value
        elif key in ("anyOf", "oneOf") and isinstance(value, list):
            non_null = [s for s in value if isinstance(s, dict) and s.get("type") != "null"]
            null_branch = [s for s in value if isinstance(s, dict) and s.get("type") == "null"]
            if len(non_null) == 1:
                merged = dict(non_null[0])
                if null_branch:
                    merged["nullable"] = True
                result.update(_normalize_schema(merged))
            else:
                result[key] = [_normalize_schema(s) for s in value]
        elif isinstance(value, dict):
            result[key] = _normalize_schema(value)
        elif isinstance(value, list):
            result[key] = [_normalize_schema(v) if isinstance(v, dict) else v for v in value]
        else:
            result[key] = value
    return result


class MCPToolWrapper:
    """Wraps an MCP tool as a ToolRegistry-compatible callable."""

    def __init__(self, session: ClientSession, server_name: str, tool_def: types.Tool, tool_timeout: int = 30):
        self._session = session
        self._server_name = server_name
        self._original_name = tool_def.name
        clean_name = _sanitize_name(tool_def.name)
        self.name = f"mcp_{_sanitize_name(server_name)}_{clean_name}"
        self.description = tool_def.description or f"MCP tool: {server_name}/{tool_def.name}"
        self.required_permission = "full_access"
        self._tool_timeout = tool_timeout

        raw_schema = tool_def.inputSchema or {}
        self.parameters = _normalize_schema(dict(raw_schema))

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def execute(self, **kwargs) -> str:
        import asyncio
        try:
            result = asyncio.run(self._call_with_timeout(kwargs))
            return result
        except asyncio.TimeoutError:
            return f"(MCP tool '{self._original_name}' timed out after {self._tool_timeout}s)"
        except Exception as e:
            return f"(MCP tool call failed: {e})"

    async def _call_with_timeout(self, kwargs: dict) -> str:
        result = await asyncio.wait_for(
            self._session.call_tool(self._original_name, arguments=kwargs),
            timeout=self._tool_timeout,
        )
        parts = []
        for content in result.content:
            if isinstance(content, types.TextContent):
                parts.append(content.text)
        return "\n".join(parts) if parts else "(no result)"


def connect_mcp_servers(servers_config: dict, tool_registry, close_stacks: dict | None = None) -> dict:
    """Connect to MCP servers and register their tools.

    Args:
        servers_config: Dict of {name: config} where config has 'command'/'args' (stdio)
                       or 'url'/'headers' (SSE/streamableHttp).
        tool_registry: ToolRegistry instance to register tools into.
        close_stacks: Optional dict to populate with {name: AsyncExitStack} for cleanup.

    Returns:
        Dict of {name: AsyncExitStack} for lifecycle management.
    """
    import asyncio
    import traceback

    stacks: dict[str, AsyncExitStack] = {}

    for name, cfg in servers_config.items():
        stack = AsyncExitStack()
        try:
            command = cfg.get("command", "")
            url = cfg.get("url", "")
            headers = cfg.get("headers", {})
            tool_timeout = cfg.get("tool_timeout", 30)

            if command:
                args = cfg.get("args", [])
                env = cfg.get("env", None)
                params = StdioServerParameters(command=command, args=args, env=env)
                read, write = asyncio.run(stack.enter_async_context(stdio_client(params)))
            elif url:
                if url.endswith("/sse"):
                    http_client = stack.enter_context(
                        __import__("httpx").Client(
                            headers=headers or None, follow_redirects=True, timeout=None,
                        )
                    ) if headers else None
                    read, write = asyncio.run(stack.enter_async_context(
                        sse_client(url, httpx_client=http_client)
                    ))
                else:
                    http_client = stack.enter_context(
                        __import__("httpx").Client(
                            headers=headers or None, follow_redirects=True, timeout=None,
                        )
                    ) if headers else None
                    read, write, _ = asyncio.run(stack.enter_async_context(
                        streamable_http_client(url, http_client=http_client)
                    ))
            else:
                continue

            session = asyncio.run(stack.enter_async_context(ClientSession(read, write)))
            asyncio.run(session.initialize())

            tools_result = asyncio.run(session.list_tools())
            for tool_def in tools_result.tools:
                wrapper = MCPToolWrapper(session, name, tool_def, tool_timeout=tool_timeout)
                tool_registry.register(wrapper)

            stacks[name] = stack
            if close_stacks is not None:
                close_stacks[name] = stack
        except Exception:
            asyncio.run(stack.aclose())

    return stacks


def close_mcp_servers(stacks: dict[str, AsyncExitStack]):
    """Close all MCP server connections."""
    import asyncio
    for name, stack in stacks.items():
        try:
            asyncio.run(stack.aclose())
        except Exception:
            pass
```

- [ ] **Step 2: Verify import**

```bash
PYTHONPATH=py-agent python3 -c "from mcp.client import MCPToolWrapper, connect_mcp_servers, close_mcp_servers; print('mcp/client OK')"
```

---

### Task 3: Remove old `McpCallTool`, wire MCP into `create_default_registry()`

**Files:**
- Modify: `py-agent/tools.py`
- Modify: `py-agent/requirements.txt`

- [ ] **Step 1: Remove `McpCallTool` class and its registration**

In `py-agent/tools.py`:
1. Delete the entire `McpCallTool` class (lines ~667-724)
2. In `create_default_registry()`, remove `registry.register(McpCallTool())`
3. Add MCP connection logic at the end of `create_default_registry()`:

```python
    # Connect to MCP servers if configured
    try:
        mcp_env = os.environ.get("MCP_SERVERS", "")
        if mcp_env:
            from mcp.client import connect_mcp_servers
            connect_mcp_servers(json.loads(mcp_env), registry)
    except Exception as e:
        print(f"[MCP] Failed to connect: {e}", file=sys.stderr)

    return registry
```

- [ ] **Step 2: Add dependency to `py-agent/requirements.txt`**

```
mcp>=1.26.0
```

- [ ] **Step 3: Verify the module still works**

```bash
PYTHONPATH=py-agent python3 -c "from tools import create_default_registry; r = create_default_registry(); tools = r.list_tools(); print(f'{len(tools)} tools registered')"
```

---

### Task 4: Run full test suite

- [ ] **Step 1: Run all tests**

```bash
python3 -m pytest tests/ -v --ignore=tests/test_agent_loop.py --ignore=tests/test_memory_hierarchy.py --ignore=tests/test_per_user_dream.py --ignore=tests/test_web_auth.py
```

Expected: all passing (excluding pre-existing failures).

- [ ] **Step 2: Commit**

```bash
git add py-agent/mcp/ py-agent/tools.py py-agent/requirements.txt docs/superpowers/specs/2026-05-06-mcp-integration-design.md docs/superpowers/plans/2026-05-06-mcp-integration.md
git commit -m "feat: MCP client integration with persistent connections and auto-registered tools"
```
