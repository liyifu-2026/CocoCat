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
    scene_id: str = "default"
    user_id: str = "local"
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

    def copy_with(self, **overrides) -> ToolContext:
        """Return a new ToolContext with overridden fields."""
        import dataclasses
        fields = {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}
        fields.update(overrides)
        return ToolContext(**fields)
