"""MCP client — connect to MCP servers and wrap their tools for the ToolRegistry."""
from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client


def _sanitize_name(name: str) -> str:
    result = []
    for ch in name:
        if ch.isalnum() or ch == "_":
            result.append(ch)
        else:
            result.append("_")
    return "".join(result).strip("_").lower()


def _normalize_schema(schema: dict) -> dict:
    result = {}
    for key, value in schema.items():
        if key == "type" and isinstance(value, list):
            if "null" in value:
                non_null = [t for t in value if t != "null"]
                result["type"] = non_null[0] if len(non_null) == 1 else non_null
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
        try:
            result = asyncio.run(
                asyncio.wait_for(
                    self._session.call_tool(self._original_name, arguments=kwargs),
                    timeout=self._tool_timeout,
                )
            )
        except asyncio.TimeoutError:
            return f"(MCP tool '{self._original_name}' timed out after {self._tool_timeout}s)"
        except Exception as e:
            return f"(MCP tool call failed: {e})"

        parts = []
        for content in (result.content if hasattr(result, 'content') else []):
            if isinstance(content, types.TextContent):
                parts.append(content.text)
        return "\n".join(parts) if parts else "(no result)"


def _connect_single_server(name: str, cfg: dict, tool_registry, stacks: dict) -> None:
    async def _connect():
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
                read, write = await stack.enter_async_context(stdio_client(params))
            elif url:
                import httpx
                client = await stack.enter_async_context(
                    httpx.AsyncClient(headers=headers or None, follow_redirects=True, timeout=None)
                )
                if url.endswith("/sse"):
                    read, write = await stack.enter_async_context(sse_client(url, httpx_client=client))
                else:
                    read, write, _ = await stack.enter_async_context(streamable_http_client(url, http_client=client))
            else:
                return

            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            tools_result = await session.list_tools()
            for tool_def in tools_result.tools:
                wrapper = MCPToolWrapper(session, name, tool_def, tool_timeout=tool_timeout)
                wrapper._stack = stack
                tool_registry.register(wrapper)

            stacks[name] = stack
        except Exception:
            await stack.aclose()
            raise

    asyncio.run(_connect())


def connect_mcp_servers(servers_config: dict, tool_registry) -> dict:
    stacks: dict[str, AsyncExitStack] = {}
    for name, cfg in servers_config.items():
        try:
            _connect_single_server(name, cfg, tool_registry, stacks)
        except Exception as e:
            import sys
            print(f"[MCP] Failed to connect '{name}': {e}", file=sys.stderr)
    return stacks


def close_mcp_servers(stacks: dict[str, AsyncExitStack]):
    for name, stack in stacks.items():
        try:
            asyncio.run(stack.aclose())
        except Exception:
            pass
