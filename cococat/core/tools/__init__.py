"""Tool system — create_core_tools() / create_main_ai_tools() / create_resident_tools()."""
import os
from typing import Any, Callable, Awaitable

from cococat.core.tools.types import Tool, ToolRegistry, _make, _merge_ctx, _ensure_tool_context  # noqa: F401 — re-export
from cococat.core.tools.file_ops import (
    _read_file, _write_file, _edit_file, _list_dir, _glob, _grep,
    make_file_tools, make_readonly_file_tools,
)
from cococat.core.tools.execution import _bash, _browser, make_execution_tools
from cococat.core.tools.web import _web_search, _web_fetch, make_web_tools
from cococat.core.tools.dag import (
    _define_dag, _append_stage, _update_dag, _dispatch_task, _check_tasks, _stop_task,
    make_dag_tools,
)
from cococat.core.tools.memory_tools import (
    _pin, _unpin, _recall, _record_experience, _recall_experience,
    make_memory_tools,
)
from cococat.core.tools.meta import _cron, _wait, _current_status, _todo_write, make_meta_tools
from cococat.core.tools.kb_tools import (
    _search_kb, _read_wiki, _write_wiki, _run_dedup,
    _run_lint, _gen_overview, _cascade_del, _get_graph, _call_worker, _list_kbs,
    _create_kb, make_kb_tools, make_kb_admin_tools,
)
from cococat.core.types import ToolContext, DagEnv, SandboxEnv, WebEnv


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


def _resolve_tavily_key() -> str | None:
    key = os.environ.get("TAVILY_API_KEY")
    if key:
        return key
    try:
        import json
        with open("config/auth.json", encoding="utf-8") as f:
            return json.load(f).get("tavily")
    except Exception:
        return None


def create_core_tools(
    sub_agent_executor=None, dag_store=None, tavily_api_key=None, sandbox_run=None,
) -> list:
    key = tavily_api_key or _resolve_tavily_key()
    return (
        make_file_tools() +
        make_execution_tools(sandbox_run) +
        make_web_tools(key) +
        make_dag_tools(dag_store, sub_agent_executor) +
        _make_sub_agent_tool(sub_agent_executor) +
        make_memory_tools() +
        make_meta_tools() +
        make_kb_tools()
    )


def create_main_ai_tools(
    sub_agent_executor=None, dag_store=None, tavily_api_key=None,
) -> list:
    key = tavily_api_key or _resolve_tavily_key()
    return (
        make_dag_tools(dag_store, sub_agent_executor) +
        make_memory_tools() +
        make_meta_tools() +
        make_readonly_file_tools() +
        make_web_tools(key) +
        make_kb_tools()
    )


def create_resident_tools(
    sub_agent_executor=None, dag_store=None, is_kb_agent=False,
) -> list:
    if is_kb_agent:
        return (
            make_file_tools() +
            make_memory_tools() +
            make_meta_tools() +
            _make_call_worker_tool(sub_agent_executor) +
            make_kb_tools() +
            make_kb_admin_tools()
        )
    return (
        make_dag_tools(dag_store, sub_agent_executor) +
        make_memory_tools() +
        make_meta_tools() +
        _make_call_worker_tool(sub_agent_executor) +
        make_kb_tools()
    )
