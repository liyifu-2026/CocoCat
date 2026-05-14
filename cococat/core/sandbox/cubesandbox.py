"""CubeSandboxExecutor — KVM MicroVM via e2b_code_interpreter SDK.

CubeSandbox 兼容 E2B SDK 协议，只需设置 E2B_API_URL 即可使用。
每个沙箱是独立 Guest OS 内核，硬件级隔离。冷启动 < 60ms，单实例 < 5MB。

配置环境变量:
    E2B_API_URL                — CubeSandbox API 地址 (默认 http://127.0.0.1:3000)
    E2B_API_KEY                — API Key (默认 "dummy")
    CUBESANDBOX_TEMPLATE_ID    — 沙箱模板 ID (默认 "default")
"""
from __future__ import annotations

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
    """CubeSandbox executor — KVM MicroVM via e2b_code_interpreter SDK."""

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
        """Execute code in the CubeSandbox MicroVM."""
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
