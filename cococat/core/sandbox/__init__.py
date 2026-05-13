"""SandboxProvider — abstract execution environment for agents.

Architecture:
  SandboxProvider (统一入口)
    ├── LocalExecutor   ← 当前：子进程运行 Agent
    └── CubeSandbox     ← 未来：KVM MicroVM（TencentCloud CubeSandbox）

用法:
  provider = SandboxProvider(executor=LocalExecutor())
  result = await provider.run({
      "prompt": "write a python script",
      "agent_id": "main",
      "permissions": {"kbs": ["default"], "skills": ["public"]},
      "tools": [...],
  }, on_event=my_callback)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import traceback
from typing import Any, Callable

try:
    from e2b_code_interpreter import AsyncSandbox
except ImportError:
    AsyncSandbox = None

logger = logging.getLogger("cococat.sandbox")


class SandboxProvider:
    """Manages agent execution environments.

    create() / destroy() 管理沙箱生命周期。
    run() 在沙箱内执行一个 agent 任务。
    """

    def __init__(self, executor: Executor | None = None):
        self._executor = executor or LocalExecutor()
        self._sandboxes: dict[str, Sandbox] = {}

    async def create(self, template: str = "default", permissions: dict | None = None) -> str:
        sandbox = await self._executor.create(template, permissions or {})
        self._sandboxes[sandbox.id] = sandbox
        return sandbox.id

    async def run(
        self,
        sandbox_id: str,
        task: dict,
        on_event: Callable[[str, dict], Any] | None = None,
    ) -> str:
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox:
            raise ValueError(f"Unknown sandbox: {sandbox_id}")
        return await self._executor.run(sandbox, task, on_event)

    async def destroy(self, sandbox_id: str) -> None:
        sandbox = self._sandboxes.pop(sandbox_id, None)
        if sandbox:
            await self._executor.destroy(sandbox)

    async def run_once(
        self,
        prompt: str,
        agent_id: str = "main",
        permissions: dict | None = None,
        tools: list[dict] | None = None,
        on_event: Callable[[str, dict], Any] | None = None,
    ) -> str:
        """Create a sandbox, run a task, destroy it. One-shot convenience."""
        sandbox_id = await self.create(permissions=permissions)
        try:
            return await self.run(sandbox_id, {
                "prompt": prompt,
                "agent_id": agent_id,
                "tools": tools or [],
            }, on_event)
        finally:
            await self.destroy(sandbox_id)


class Sandbox:
    """Represents a sandbox instance."""
    def __init__(self, id: str, template: str, permissions: dict):
        self.id = id
        self.template = template
        self.permissions = permissions
        self.created_at = None


class Executor:
    """Abstract executor backend."""

    async def create(self, template: str, permissions: dict) -> Sandbox:
        raise NotImplementedError

    async def run(self, sandbox: Sandbox, task: dict, on_event: Callable | None) -> str:
        raise NotImplementedError

    async def destroy(self, sandbox: Sandbox) -> None:
        raise NotImplementedError


class LocalExecutor(Executor):
    """Local subprocess executor — runs Agent code in a child process."""

    def __init__(self, max_workers: int = 4):
        self._max_workers = max_workers
        self._semaphore = asyncio.Semaphore(max_workers)
        self._counter = 0

    async def create(self, template: str, permissions: dict) -> Sandbox:
        self._counter += 1
        sandbox_id = f"local-{self._counter}"
        logger.info("LocalExecutor: created %s", sandbox_id)
        return Sandbox(id=sandbox_id, template=template, permissions=permissions)

    async def run(self, sandbox: Sandbox, task: dict, on_event: Callable | None) -> str:
        logger.info("LocalExecutor: running task in %s", sandbox.id)
        from cococat.core.agent import Agent, AgentRole
        from cococat.core.tools import create_core_tools

        prompt = task.get("prompt", "")
        agent_id = task.get("agent_id", sandbox.id)

        # Build tool list with permission filtering
        all_tools = create_core_tools()
        allowed_kbs = sandbox.permissions.get("kbs", [])
        allowed_skills = sandbox.permissions.get("skills", [])
        # For now, local executor allows all tools
        tools = all_tools

        # Create a temporary Agent object
        llm = self._get_llm(agent_id)
        if not llm:
            return f"[System] No LLM provider for agent '{agent_id}'"

        agent = Agent(
            id=agent_id,
            name=agent_id,
            role=AgentRole.SUB,
            llm=llm,
            tools=tools,
            agent_dir=f"agents/{agent_id}" if os.path.isdir(f"agents/{agent_id}") else None,
        )

        try:
            result = await agent.run(
                prompt,
                on_text=lambda t: on_event("text_delta", {"content": t}) if on_event else None,
                on_tool=lambda n, s: on_event("tool", {"name": n, "status": s}) if on_event else None,
                on_reasoning=lambda c: on_event("reasoning", {"content": c}) if on_event else None,
            )
            return result
        except Exception as e:
            logger.error("LocalExecutor: task failed: %s", e)
            return f"Error: {e}"

    async def destroy(self, sandbox: Sandbox) -> None:
        logger.info("LocalExecutor: destroyed %s", sandbox.id)

    def _get_llm(self, agent_id: str):
        """Get LLM provider for an agent. Tries AgentPool first, then creates from DB."""
        from cococat.providers.factory import ProviderFactory
        from cococat.providers.credentials import CredentialManager
        import os

        factory = ProviderFactory(credential_manager=CredentialManager("config/auth.json"))
        model = "deepseek-v4-flash"

        rows = []
        try:
            import sqlite3
            db_path = os.environ.get("COCOCAT_DB", "cococat.db")
            conn = sqlite3.connect(db_path)
            rows = conn.execute(
                "SELECT model FROM agents WHERE id = ?", (agent_id,)
            ).fetchall()
            conn.close()
        except Exception:
            pass

        if rows:
            model = rows[0][0]

        provider = factory.create_sync(model)
        return provider


class CubeSandboxExecutor(Executor):
    """CubeSandbox executor — KVM MicroVM via e2b_code_interpreter SDK.

    CubeSandbox 兼容 E2B SDK 协议，只需设置 E2B_API_URL 即可使用。
    每个沙箱是独立 Guest OS 内核，硬件级隔离。冷启动 < 60ms，单实例 < 5MB。

    配置环境变量:
        E2B_API_URL                — CubeSandbox API 地址 (默认 http://127.0.0.1:3000)
        E2B_API_KEY                — API Key (默认 "dummy")
        CUBESANDBOX_TEMPLATE_ID    — 沙箱模板 ID (默认 "default")
    """

    def __init__(
        self,
        template_id: str | None = None,
        timeout_seconds: int = 300,
    ):
        self._template_id = template_id or os.environ.get(
            "CUBESANDBOX_TEMPLATE_ID",
            os.environ.get("E2B_TEMPLATE", "default"),
        )
        self._timeout = timeout_seconds
        self._sandbox_instances: dict[str, Any] = {}

    async def create(self, template: str = "default", permissions: dict | None = None) -> Sandbox:
        try:
            if AsyncSandbox is None:
                raise RuntimeError("e2b_code_interpreter not installed. Run: pip install e2b-code-interpreter")

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
        """Execute code in the CubeSandbox MicroVM.

        The prompt is executed directly as Python code in the isolated VM.
        For shell commands, wrap with: import subprocess; subprocess.run(cmd, shell=True, capture_output=True, text=True)
        """
        sbx = self._sandbox_instances.get(sandbox.id)
        if not sbx:
            return f"Error: sandbox {sandbox.id} not found in active instances"

        code = task.get("prompt", "")

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
                # Check results for non-log output (e.g. print return value)
                results = execution.results or []
                for r in results:
                    if hasattr(r, "text") and r.text:
                        output += r.text + "\n"
                output = output.strip()

            logger.info("CubeSandbox: executed in %s, output %d chars", sandbox.id, len(output))
            return output[:10000] if output else "(no output)"
        except Exception as e:
            logger.error("CubeSandbox run failed in %s: %s", sandbox.id, e)
            return f"Error: CubeSandbox execution failed: {e}"

    async def destroy(self, sandbox: Sandbox) -> None:
        sbx = self._sandbox_instances.pop(sandbox.id, None)
        if sbx:
            try:
                await sbx.kill()
                logger.info("CubeSandbox: destroyed sandbox %s", sandbox.id)
            except Exception as e:
                logger.warning("CubeSandbox kill failed for %s: %s", sandbox.id, e)
