"""CubeSandboxExecutor — KVM MicroVM via e2b_code_interpreter SDK.

CubeSandbox 兼容 E2B SDK 协议，只需设置 E2B_API_URL 即可使用。
每个沙箱是独立 Guest OS 内核，硬件级隔离。冷启动 < 60ms，单实例 < 5MB。

配置环境变量:
    E2B_API_URL                — CubeSandbox API 地址 (默认 http://127.0.0.1:3000)
    E2B_API_KEY                — API Key (默认 "dummy")
    CUBESANDBOX_TEMPLATE_ID    — 沙箱模板 ID (默认 "default")
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Callable

try:
    from e2b_code_interpreter import AsyncSandbox
except ImportError:
    AsyncSandbox = None

from cococat.core.sandbox.sandbox import Sandbox

logger = logging.getLogger("cococat.sandbox.cube")

class CubeSandboxExecutor:
    """CubeSandbox executor — creates Agent inside MicroVM for isolated execution."""

    def __init__(
        self,
        template_id: str | None = None,
        timeout_seconds: int = 300,
        get_llm: Callable[[str], Any] | None = None,
    ):
        self._template_id = template_id or os.environ.get(
            "CUBESANDBOX_TEMPLATE_ID",
            os.environ.get("E2B_TEMPLATE", "default"),
        )
        self._timeout = timeout_seconds
        self._sandbox_instances: dict[str, Any] = {}
        self._get_llm_fn = get_llm
        self._semaphore = asyncio.Semaphore(4)

    async def create(self, template: str = "default", permissions: dict | None = None) -> Sandbox:
        try:
            if AsyncSandbox is None:
                raise RuntimeError(
                    "e2b_code_interpreter not installed. Run: pip install e2b-code-interpreter"
                )

            sbx = await AsyncSandbox.create(
                template=self._template_id,
                timeout=self._timeout,
            )
            sandbox_id = sbx.sandbox_id
            self._sandbox_instances[sandbox_id] = sbx
            logger.info("CubeSandbox: created sandbox %s (template=%s)", sandbox_id, self._template_id)
            return Sandbox(id=sandbox_id, template=template, permissions=permissions or {})
        except Exception as e:
            logger.error("CubeSandbox create failed: %s", e)
            raise RuntimeError(f"CubeSandbox create failed: {e}") from e

    async def run(self, sandbox: Sandbox, task: dict, on_event: Callable | None = None) -> str:
        """Create an Agent and run the full ReAct loop. EXEC_TOOLS run in sandbox."""
        async with self._semaphore:
            return await self._do_run(sandbox, task, on_event)

    async def _do_run(self, sandbox: Sandbox, task: dict, on_event: Callable | None) -> str:
        sbx = self._sandbox_instances.get(sandbox.id)
        if not sbx:
            return f"Error: sandbox {sandbox.id} not found in active instances"

        from cococat.core.tools import create_core_tools
        from cococat.core.sandbox import _make_and_run_agent

        prompt = task.get("prompt", "")
        agent_id = task.get("agent_id", sandbox.id)
        session_id = task.get("session_id")
        provided_tools = task.get("tools")

        sandbox_run = _make_sandbox_run(sbx.sandbox_id, self._sandbox_run)

        if provided_tools:
            tools = _wrap_exec_tools(provided_tools, sandbox_run)
        else:
            tools = create_core_tools()
            tools = _wrap_exec_tools(tools, sandbox_run)

        return await _make_and_run_agent(
            agent_id=agent_id,
            prompt=prompt,
            tools=tools,
            resolve_llm=self._resolve_llm,
            session_id=session_id,
            on_event=on_event,
        )

    async def _sandbox_run(self, sandbox_id: str, code: str) -> str:
        """Execute a code snippet in the specified sandbox MicroVM."""
        sbx = self._sandbox_instances.get(sandbox_id)
        if not sbx:
            return f"Error: sandbox {sandbox_id} not found"

        try:
            execution = await sbx.run_code(code, language="python")
            logs = execution.logs
            stdout = list(logs.stdout) if logs and logs.stdout else []
            stderr = list(logs.stderr) if logs and logs.stderr else []

            parts = []
            if stdout:
                parts.append("\n".join(stdout))
            if stderr:
                parts.append("\n[stderr]\n" + "\n".join(stderr))
            if execution.error:
                parts.append(f"\n[error]\n{execution.error}")

            output = "\n".join(parts).strip()
            if not output:
                results = execution.results or []
                for r in results:
                    if hasattr(r, "text") and r.text:
                        output += r.text + "\n"
                output = output.strip()
            return output[:10000] if output else "(no output)"
        except Exception as e:
            return f"Error: CubeSandbox execution failed: {e}"

    async def destroy(self, sandbox: Sandbox) -> None:
        sbx = self._sandbox_instances.pop(sandbox.id, None)
        if sbx:
            try:
                await sbx.kill()
                logger.info("CubeSandbox: destroyed sandbox %s", sandbox.id)
            except Exception as e:
                logger.warning("CubeSandbox kill failed for %s: %s", sandbox.id, e)

    def _resolve_llm(self, agent_id: str):
        """Resolve LLM provider via injected callable."""
        return self._get_llm_fn(agent_id) if self._get_llm_fn else None


def _make_sandbox_run(sandbox_id: str, fn: Callable):
    """Create a sandbox_run closure bound to a specific sandbox_id."""
    async def wrapper(code: str) -> str:
        return await fn(sandbox_id, code)
    return wrapper


def _wrap_exec_tools(tools: list, sandbox_run) -> list:
    """Wrap EXEC_TOOLS with sandbox_run, leave HOST_TOOLS untouched.

    Uses tool.requires_sandbox flag instead of hardcoded name set.
    """
    wrapped = []
    for tool in tools:
        if getattr(tool, "requires_sandbox", False):
            tool_name = tool["name"]

            def make_wrapped(exec_fn=tool["execute"]):
                async def wrapped_fn(params, ctx):
                    code = _tool_to_code(tool_name, params)
                    if code is None:
                        return await exec_fn(params, ctx) if callable(getattr(exec_fn(params, ctx), "__await__", None)) \
                            else exec_fn(params, ctx)
                    return await sandbox_run(code)
                return wrapped_fn

            wrapped.append({**tool, "execute": make_wrapped()})
        else:
            wrapped.append(tool)
    return wrapped


def _tool_to_code(name: str, params: dict) -> str | None:
    """Convert a tool call into a Python code snippet for sandbox execution."""
    if name == "bash":
        cmd = params.get("command", "")
        return (
            "import subprocess, sys\n"
            f"r = subprocess.run({cmd!r}, shell=True, capture_output=True, text=True, timeout=30)\n"
            "sys.stdout.write(r.stdout)\n"
            "if r.stderr: sys.stderr.write(r.stderr)\n"
        )
    if name == "read_file":
        path = params.get("path", "")
        offset = int(params.get("offset", 0))
        limit = int(params.get("limit", 2000))
        return (
            f"import os\n"
            f"p = {path!r}\n"
            f"if not os.path.exists(p):\n"
            f"    print('Error: file not found: ' + p)\n"
            f"elif not os.path.isfile(p):\n"
            f"    print('Error: not a file: ' + p)\n"
            f"else:\n"
            f"    with open(p, 'r', encoding='utf-8', errors='replace') as f:\n"
            f"        lines = f.readlines()\n"
            f"        start = max(0, {offset})\n"
            f"        if start > 0: start -= 1\n"
            f"        end = start + {limit}\n"
            f"        selected = lines[start:end]\n"
            f"        for i, line in enumerate(selected):\n"
            f"            print(f'{{start + i + 1}}: {{line}}', end='')\n"
        )
    if name == "write_file":
        path = params.get("path", "")
        content = params.get("content", "")
        return (
            f"import os\n"
            f"p = {path!r}\n"
            f"os.makedirs(os.path.dirname(p) or '.', exist_ok=True)\n"
            f"with open(p, 'w', encoding='utf-8') as f:\n"
            f"    f.write({content!r})\n"
            f"print('Written: ' + p)\n"
        )
    if name == "edit_file":
        path = params.get("path", "")
        old = params.get("old", "")
        new = params.get("new", "")
        return (
            f"p = {path!r}\n"
            f"with open(p, 'r', encoding='utf-8', errors='replace') as f:\n"
            f"    content = f.read()\n"
            f"if {old!r} not in content:\n"
            f"    print('Error: old string not found in file')\n"
            f"else:\n"
            f"    content = content.replace({old!r}, {new!r})\n"
            f"    with open(p, 'w', encoding='utf-8') as f:\n"
            f"        f.write(content)\n"
            f"    print('Edited: ' + p)\n"
        )
    if name == "glob":
        pattern = params.get("pattern", "*")
        return (
            f"import glob\n"
            f"for f in sorted(glob.glob({pattern!r}, recursive=True)):\n"
            f"    print(f)\n"
        )
    if name == "grep":
        pat = params.get("pattern", "")
        path = params.get("path", "")
        return (
            f"import re, os\n"
            f"pat = re.compile({pat!r})\n"
            f"for root, dirs, files in os.walk({path!r} if os.path.isdir({path!r}) else '.'):\n"
            f"    for fname in files:\n"
            f"        fpath = os.path.join(root, fname)\n"
            f"        try:\n"
            f"            with open(fpath, encoding='utf-8', errors='replace') as f:\n"
            f"                for i, line in enumerate(f, 1):\n"
            f"                    if pat.search(line):\n"
            f"                        print(f'{{fpath}}:{{i}}: {{line.rstrip()}}')\n"
            f"        except Exception:\n"
            f"            pass\n"
        )
    if name == "browser":
        return "print('Error: browser tool is not available inside sandbox')"
    return None
