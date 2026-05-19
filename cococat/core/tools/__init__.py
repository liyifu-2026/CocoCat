"""Tool system — ToolCatalog centralises tool assembly per agent role."""

from cococat.core.tools.types import Tool, ToolRegistry, _make, _merge_ctx, _ensure_tool_context  # noqa: F401 — re-export
from cococat.core.tools.file_ops import make_file_tools, make_readonly_file_tools
from cococat.core.tools.execution import make_execution_tools
from cococat.core.tools.web import make_web_tools
from cococat.core.tools.dag import make_dag_tools
from cococat.core.tools.memory_tools import make_memory_tools
from cococat.core.tools.meta import make_meta_tools
from cococat.core.tools.kb_tools import _call_worker, make_kb_tools, make_kb_admin_tools
from cococat.core.types import DagEnv

import os


def resolve_tavily_key(config_store=None) -> str | None:
    key = os.environ.get("TAVILY_API_KEY")
    if key:
        return key
    if config_store:
        try:
            return config_store.get_auth("tavily")
        except Exception:
            pass
    return None


class ToolCatalog:
    """Single source of truth for agent tool assembly.

    Callers ask for a preset by role instead of composing make_* functions inline.

        catalog = ToolCatalog(sub_agent_executor=dispatch, dag_store=store)
        worker_tools = catalog.worker()      # full tool set
        main_tools  = catalog.main_ai()      # orchestration tools
        res_tools   = catalog.resident(kb=True)  # resident tools
    """

    def __init__(self, *, sub_agent_executor=None, dag_store=None, sandbox_run=None, tavily_api_key=None):
        self._sub_agent_executor = sub_agent_executor
        self._dag_store = dag_store
        self._sandbox_run = sandbox_run
        self._tavily_api_key = tavily_api_key

    def worker(self) -> list[Tool]:
        """Full tool set for worker agents (file r/w, bash, browser, web, dag, ...)."""
        return (
            make_file_tools() +
            make_execution_tools(self._sandbox_run) +
            make_web_tools(self._tavily_api_key) +
            make_dag_tools(self._dag_store, self._sub_agent_executor) +
            _make_sub_agent_tool(self._sub_agent_executor) +
            make_memory_tools() +
            make_meta_tools() +
            make_kb_tools()
        )

    def main_ai(self) -> list[Tool]:
        """Orchestration tools for the main AI agent (dag, readonly files, web, kb)."""
        return (
            make_dag_tools(self._dag_store, self._sub_agent_executor) +
            make_memory_tools() +
            make_meta_tools() +
            make_readonly_file_tools() +
            make_web_tools(self._tavily_api_key) +
            make_kb_tools()
        )

    def resident(self, *, kb_agent: bool = False) -> list[Tool]:
        """Tools for resident (page-bound) agents. Set kb_agent=True for KB admin."""
        if kb_agent:
            return (
                make_file_tools() +
                make_memory_tools() +
                make_meta_tools() +
                _make_call_worker_tool(self._sub_agent_executor) +
                make_kb_tools() +
                make_kb_admin_tools()
            )
        return (
            make_dag_tools(self._dag_store, self._sub_agent_executor) +
            make_memory_tools() +
            make_meta_tools() +
            _make_call_worker_tool(self._sub_agent_executor) +
            make_kb_tools()
        )


def _make_sub_agent_tool(sub_agent_executor=None) -> list[Tool]:
    return [
        _make("sub_agent", "Spawn a sub-agent (async)", {"task": "string", "agent_id": "string"},
              (lambda p, ctx: f"[sub_agent] {p.get('task', '')} — stub")
              if sub_agent_executor is None else
              (lambda p, ctx: sub_agent_executor(p.get("task", ""), p.get("agent_id", "sub")))),
    ]


def _make_call_worker_tool(sub_agent_executor=None) -> list[Tool]:
    return [
        _make("call_worker", "Call a worker agent for execution", {"task": "string"},
              (lambda p, ctx: f"[call_worker] {p.get('task', '')} — stub")
              if sub_agent_executor is None else
              (lambda p, ctx: _call_worker(p, _merge_ctx(ctx, dag=DagEnv(executor=sub_agent_executor))))),
    ]


# ── backward-compat aliases ──────────────────────────────────

def create_core_tools(
    sub_agent_executor=None, dag_store=None, tavily_api_key=None, sandbox_run=None,
) -> list:
    return ToolCatalog(
        sub_agent_executor=sub_agent_executor,
        dag_store=dag_store,
        sandbox_run=sandbox_run,
        tavily_api_key=tavily_api_key,
    ).worker()


def create_main_ai_tools(
    sub_agent_executor=None, dag_store=None, tavily_api_key=None,
) -> list:
    return ToolCatalog(
        sub_agent_executor=sub_agent_executor,
        dag_store=dag_store,
        tavily_api_key=tavily_api_key,
    ).main_ai()


def create_resident_tools(
    sub_agent_executor=None, dag_store=None, is_kb_agent=False,
) -> list:
    return ToolCatalog(
        sub_agent_executor=sub_agent_executor,
        dag_store=dag_store,
    ).resident(kb_agent=is_kb_agent)
