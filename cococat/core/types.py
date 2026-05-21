"""Shared types for tool context — typed providers replace flat dict."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class SandboxEnv:
    """Sandbox execution provider."""
    run: Callable | None = None  # sandbox_run(code) → str


@dataclass
class MemoryEnv:
    """Memory file-paths provider."""
    memory_path: str = ""
    agent_dir: str = ""
    exp_path: str = "memory/experiences"


@dataclass
class WebEnv:
    """Web tools provider."""
    tavily_api_key: str | None = None


@dataclass
class ToolContext:
    """Typed context passed through the tool execution pipeline."""

    agent_id: str = ""
    agent_dir: str = ""
    bound_scene: str | None = None
    role: str = ""
    session_id: str | None = None

    db: Any = None               # Database
    sub_agent_executor: Callable | None = None
    sandbox: SandboxEnv = field(default_factory=SandboxEnv)
    memory: MemoryEnv = field(default_factory=MemoryEnv)
    web: WebEnv = field(default_factory=WebEnv)
    cron_path: str = "runs/cron"
    _llm: Any = None             # LLM instance (for kb tools)

    @classmethod
    def from_dict(cls, d: dict | None) -> ToolContext:
        """Convert legacy flat dict to typed ToolContext."""
        if d is None:
            return cls()
        if isinstance(d, cls):
            return d
        sandbox = SandboxEnv(
            run=d.get("sandbox_run"),
        )

        mem_kw = {}
        if "memory_path" in d:
            mem_kw["memory_path"] = d["memory_path"]
        if "agent_dir" in d:
            mem_kw["agent_dir"] = d["agent_dir"]
        if "exp_path" in d:
            mem_kw["exp_path"] = d["exp_path"]
        memory = MemoryEnv(**mem_kw) if mem_kw else MemoryEnv()

        web = WebEnv(
            tavily_api_key=d.get("tavily_api_key"),
        )

        direct_keys = {"agent_id", "agent_dir", "bound_scene", "role", "session_id",
                       "db", "sub_agent_executor", "cron_path", "_llm"}
        direct = {k: v for k, v in d.items() if k in direct_keys}

        return cls(
            sandbox=sandbox,
            memory=memory,
            web=web,
            **direct,
        )
