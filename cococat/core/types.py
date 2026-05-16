"""Shared types for tool context — typed providers replace flat dict."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class DagEnv:
    """DAG orchestration provider injected into tool context."""
    store: Any = None            # DagStore
    executor: Callable | None = None  # sub_agent_executor
    dag_dir: str = "runs"
    tasks_path: str = "runs"
    cancel_dir: str = "runs/cancellations"


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
    dag: DagEnv = field(default_factory=DagEnv)
    sandbox: SandboxEnv = field(default_factory=SandboxEnv)
    memory: MemoryEnv = field(default_factory=MemoryEnv)
    web: WebEnv = field(default_factory=WebEnv)
    cron_path: str = "runs/cron"
    todos_path: str = "todos.json"
    _llm: Any = None             # LLM instance (for kb tools)

    @classmethod
    def from_dict(cls, d: dict | None) -> ToolContext:
        """Convert legacy flat dict to typed ToolContext."""
        if d is None:
            return cls()
        if isinstance(d, cls):
            return d
        # Build sub-providers from flat keys
        dag_kw = {}
        if "dag_store" in d:
            dag_kw["store"] = d["dag_store"]
        if "sub_agent_executor" in d:
            dag_kw["executor"] = d["sub_agent_executor"]
        if "dag_dir" in d:
            dag_kw["dag_dir"] = d["dag_dir"]
        if "tasks_path" in d:
            dag_kw["tasks_path"] = d["tasks_path"]
        if "cancel_dir" in d:
            dag_kw["cancel_dir"] = d["cancel_dir"]
        dag = DagEnv(**dag_kw) if dag_kw else DagEnv()

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
                       "db", "cron_path", "todos_path", "_llm"}
        direct = {k: v for k, v in d.items() if k in direct_keys}

        return cls(
            dag=dag,
            sandbox=sandbox,
            memory=memory,
            web=web,
            **direct,
        )
