"""Tool executor — static helpers for tool call dispatch and message building."""
from __future__ import annotations

import json
import logging
import time
import traceback
from typing import Callable

from cococat.core.types import ToolContext

logger = logging.getLogger("cococat.tool_executor")


def make_assistant_msg(content: str, tool_calls: list, reasoning_content: str | None = None) -> dict:
    """Build the assistant message with tool_calls in OpenAI format."""
    msg: dict = {"role": "assistant", "content": content}
    if reasoning_content:
        msg["reasoning_content"] = reasoning_content
    msg["tool_calls"] = []
    for tc in tool_calls:
        tid = tc.id if hasattr(tc, "id") else tc["id"]
        tname = tc.name if hasattr(tc, "name") else tc["name"]
        targs = tc.arguments if hasattr(tc, "arguments") else tc["arguments"]
        msg["tool_calls"].append({
            "id": tid,
            "type": "function",
            "function": {"name": tname, "arguments": targs},
        })
    return msg


async def execute_tool_calls(
    tool_calls: list,
    messages: list[dict],
    tools: list[dict],
    context: ToolContext,
    on_tool: Callable | None = None,
) -> None:
    """Execute a batch of tool calls and append results to messages."""
    for tc in tool_calls:
        start_time = time.time()
        tid = tc.id if hasattr(tc, "id") else tc["id"]
        tname = tc.name if hasattr(tc, "name") else tc["name"]
        targs = tc.arguments if hasattr(tc, "arguments") else tc["arguments"]
        if on_tool:
            await on_tool(tname, "start", {"tool_call_id": tid, "arguments": targs})
        try:
            params = json.loads(targs) if isinstance(targs, str) else targs
            tool = next((t for t in tools if t["name"] == tname), None)
            if tool:
                result = tool["execute"](params, context)
                if callable(getattr(result, "__await__", None)):
                    result = await result
                result_str = str(result)
            else:
                result_str = f"Unknown tool: {tname}"
        except Exception as e:
            logger.error("Tool '%s' execution failed:\n%s", tname, traceback.format_exc())
            result_str = f"Tool error: {e}"

        elapsed = round(time.time() - start_time, 2)

        messages.append({
            "role": "tool",
            "tool_call_id": tid,
            "content": result_str,
        })
        if on_tool:
            await on_tool(tname, "done", {"tool_call_id": tid, "result": result_str[:200], "elapsed": elapsed})
