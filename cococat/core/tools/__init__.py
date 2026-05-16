"""Tool system — Tool dataclass with registry and execution.

Provides create_core_tools() and create_main_ai_tools() as the only public API.
Tool definitions are organized by domain in internal helper functions.
"""
import os
from dataclasses import dataclass
from typing import Any, Callable, Awaitable

from cococat.core.tools.registry import _make, ToolRegistry  # noqa: F401 — re-export
from cococat.core.tools.file_ops import _read_file, _write_file, _edit_file, _list_dir, _glob, _grep
from cococat.core.tools.execution import _bash, _browser
from cococat.core.tools.web import _web_search, _web_fetch
from cococat.core.tools.dag import (
    _define_dag, _append_stage, _update_dag, _dispatch_task, _check_tasks, _stop_task,
)
from cococat.core.tools.memory_tools import _pin, _unpin, _recall, _record_experience, _recall_experience
from cococat.core.tools.meta import _cron, _wait, _current_status, _todo_write
from cococat.core.tools.kb_tools import (
    _search_kb, _read_wiki, _write_wiki, _run_dedup,
    _run_lint, _gen_overview, _cascade_del, _get_graph, _call_worker, _list_kbs,
)


@dataclass
class Tool:
    """A tool with name, description, parameters, and execute function.

    Supports both dict-style access (t["name"]) and attribute access (t.name)
    for backward compatibility.
    """
    name: str
    description: str
    parameters: dict[str, Any]
    execute: Callable
    requires_sandbox: bool = False
    sandbox_operation: str = ""  # "read", "write", "exec", or "" for no check

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def keys(self):
        return ["name", "description", "parameters", "execute", "requires_sandbox", "sandbox_operation"]

    def __iter__(self):
        return iter(self.keys())


# ── Tool groups ──────────────────────────────────────────

def _make_file_tools() -> list[dict]:
    return [
        _make("read_file", "Read a file with offset/limit", {"path": "string", "offset": "integer", "limit": "integer"},
              lambda p, ctx: _read_file(p.get("path", ""), p.get("offset", 0), p.get("limit", 2000)),
              requires_sandbox=True, sandbox_operation="read"),
        _make("write_file", "Write content to a file", {"path": "string", "content": "string"},
              lambda p, ctx: _write_file(p.get("path", ""), p.get("content", "")),
              requires_sandbox=True, sandbox_operation="write"),
        _make("edit_file", "Edit a file by replacing text", {"path": "string", "old": "string", "new": "string"},
              lambda p, ctx: _edit_file(p.get("path", ""), p.get("old", ""), p.get("new", "")),
              requires_sandbox=True, sandbox_operation="write"),
        _make("list_dir", "List directory contents", {"path": "string"},
              lambda p, ctx: _list_dir(p.get("path", ""))),
        _make("glob", "Find files by glob pattern", {"pattern": "string"},
              lambda p, ctx: _glob(p.get("pattern", "")),
              requires_sandbox=True, sandbox_operation="read"),
        _make("grep", "Search file contents with regex", {"pattern": "string", "path": "string"},
              lambda p, ctx: _grep(p.get("pattern", ""), p.get("path", "")),
              requires_sandbox=True, sandbox_operation="read"),
    ]


def _make_execution_tools(sandbox_run=None) -> list[dict]:
    return [
        _make("bash", "Execute shell command", {"command": "string"},
              lambda p, ctx: _bash(p.get("command", ""), {**(ctx or {}), "sandbox_run": sandbox_run}),
              requires_sandbox=True, sandbox_operation="exec"),
        _make("browser", "Browser control — navigate, get_text, get_content, screenshot, click, type, scroll, execute_js, go_back",
              {"action": "string"},
              lambda p, ctx: _browser(p.get("action", "")),
              requires_sandbox=True, sandbox_operation="exec"),
    ]


def _make_web_tools(tavily_api_key: str | None = None) -> list[dict]:
    return [
        _make("web_search", "Search the web", {"query": "string"},
              lambda p, ctx: _web_search(p.get("query", ""), {**(ctx or {}), "tavily_api_key": tavily_api_key})),
        _make("web_fetch", "Fetch URL content", {"url": "string"},
              lambda p, ctx: _web_fetch(p.get("url", ""))),
    ]


def _make_dag_tools(dag_store=None, sub_agent_executor=None) -> list[dict]:
    return [
        _make("define_dag", "Define a DAG task graph", {"yaml": "string"},
              lambda p, ctx: _define_dag(p.get("yaml", ""), {**(ctx or {}), "dag_store": dag_store})),
        _make("append_stage", "Append a stage to an existing DAG run", {"run_id": "string", "stage_yaml": "string"},
              lambda p, ctx: _append_stage(p.get("run_id", ""), p.get("stage_yaml", ""), {**(ctx or {}), "dag_store": dag_store})),
        _make("update_dag", "Update a node in dag.yaml by dot-path", {"run_id": "string", "path": "string", "value": "string"},
              lambda p, ctx: _update_dag(p.get("run_id", ""), p.get("path", ""), p.get("value", ""), {**(ctx or {}), "dag_store": dag_store})),
        _make("dispatch_task", "Dispatch a task in a DAG run", {"run_id": "string", "task_id": "string", "prompt": "string"},
              lambda p, ctx: _dispatch_task(p.get("run_id", ""), p.get("task_id", ""), p.get("prompt", ""), {
                  **(ctx or {}), "dag_store": dag_store, "sub_agent_executor": sub_agent_executor,
              })),
        _make("check_tasks", "Check pending task status", {},
              lambda p, ctx: _check_tasks({**(ctx or {}), "dag_store": dag_store})),
        _make("stop_task", "Cancel a running task", {"task_id": "string"},
              lambda p, ctx: _stop_task(p.get("task_id", ""), ctx or {})),
    ]


def _make_memory_tools() -> list[dict]:
    return [
        _make("recall", "Search memory by keyword (FTS5)", {"query": "string"},
              lambda p, ctx: _recall(p.get("query", ""), ctx or {})),
        _make("pin", "Pin a fact to persistent context", {"fact": "string"},
              lambda p, ctx: _pin(p.get("fact", ""), ctx or {})),
        _make("unpin", "Unpin a fact", {"keyword": "string"},
              lambda p, ctx: _unpin(p.get("keyword", ""), ctx or {})),
        _make("record_experience", "Record a categorized experience", {"category": "string", "entry": "string"},
              lambda p, ctx: _record_experience(p.get("category", ""), p.get("entry", ""), ctx or {})),
        _make("recall_experience", "Recall experiences by category", {"category": "string"},
              lambda p, ctx: _recall_experience(p.get("category", ""), ctx or {})),
    ]


def _make_meta_tools() -> list[dict]:
    return [
        _make("todo_write", "Structured task list", {"todos": "array"},
              lambda p, ctx: _todo_write(p.get("todos"), ctx or {})),
        _make("cron", "Schedule a recurring task", {"schedule": "string", "task": "string"},
              lambda p, ctx: _cron(p.get("schedule", ""), p.get("task", ""), ctx or {})),
        _make("current_status", "Agent runtime introspection", {},
              lambda p, ctx: _current_status(ctx or {})),
        _make("wait", "Sleep for seconds", {"seconds": "number"},
              lambda p, ctx: _wait(p.get("seconds", 0))),
    ]


def _make_sub_agent_tool(sub_agent_executor=None) -> list[dict]:
    return [
        _make("sub_agent", "Spawn a sub-agent (async)", {"task": "string", "agent_id": "string"},
              (lambda p, ctx: f"[sub_agent] {p.get('task', '')} — stub")
              if sub_agent_executor is None else
              (lambda p, ctx: sub_agent_executor(p.get("task", ""), p.get("agent_id", "sub")))),
    ]


def _make_kb_tools() -> list[dict]:
    """KB tools for all agents (read-only)."""
    return [
        _make("search_kb", "Search a knowledge base wiki", {"kb_name": "string", "query": "string"},
              lambda p, ctx: _search_kb(p, ctx)),
        _make("read_wiki", "Read a wiki page", {"kb_name": "string", "type": "string", "slug": "string"},
              lambda p, ctx: _read_wiki(p, ctx)),
        _make("list_kbs", "List available knowledge bases", {},
              lambda p, ctx: _list_kbs(p, ctx)),
    ]


def _make_kb_admin_tools() -> list[dict]:
    """KB admin tools (write + maintenance) for kb-agent only."""
    return [
        _make("write_wiki", "Write a wiki page", {"kb_name": "string", "type": "string", "slug": "string", "content": "string", "title": "string"},
              lambda p, ctx: _write_wiki(p, ctx)),
        _make("run_dedup", "Run KB dedup pipeline", {"kb_name": "string"},
              lambda p, ctx: _run_dedup(p, ctx)),
        _make("run_lint", "Run KB health check", {"kb_name": "string"},
              lambda p, ctx: _run_lint(p, ctx)),
        _make("gen_overview", "Generate KB overview", {"kb_name": "string"},
              lambda p, ctx: _gen_overview(p, ctx)),
        _make("cascade_del", "Cascade delete source file from KB", {"kb_name": "string", "source_filename": "string"},
              lambda p, ctx: _cascade_del(p, ctx)),
        _make("get_graph", "Get KB knowledge graph", {"kb_name": "string"},
              lambda p, ctx: _get_graph(p, ctx)),
    ]


def _make_call_worker_tool(sub_agent_executor=None) -> list[dict]:
    """call_worker tool for resident agents to invoke worker pool."""
    return [
        _make("call_worker", "Call a worker agent for execution", {"task": "string"},
              (lambda p, ctx: f"[call_worker] {p.get('task', '')} — stub")
              if sub_agent_executor is None else
              (lambda p, ctx: _call_worker(p, {**(ctx or {}), "sub_agent_executor": sub_agent_executor}))),
    ]


# ── Public API ────────────────────────────────────────────

def create_core_tools(
    sub_agent_executor: Callable[[str, str], Awaitable[str]] | None = None,
    dag_store=None,
    tavily_api_key: str | None = None,
    sandbox_run: Callable[[str], Awaitable[str]] | None = None,
) -> list[dict]:
    """Create the 26 core tools for sub-agents."""
    if tavily_api_key is None:
        tavily_api_key = os.environ.get("TAVILY_API_KEY")
    return (
        _make_file_tools() +
        _make_execution_tools(sandbox_run) +
        _make_web_tools(tavily_api_key) +
        _make_dag_tools(dag_store, sub_agent_executor) +
        _make_sub_agent_tool(sub_agent_executor) +
        _make_memory_tools() +
        _make_meta_tools() +
        _make_kb_tools()
    )


def create_main_ai_tools(
    sub_agent_executor: Callable[[str, str], Awaitable[str]] | None = None,
    dag_store=None,
    tavily_api_key: str | None = None,
) -> list[dict]:
    """Create Coco's tools — DAG orchestration + memory + meta ONLY.
    Coco NEVER calls execution tools directly. All execution goes through
    define_dag → dispatch_task → sub-agent.
    """
    return (
        _make_dag_tools(dag_store, sub_agent_executor) +
        _make_memory_tools() +
        _make_meta_tools()
    )


def create_resident_tools(
    sub_agent_executor: Callable[[str, str], Awaitable[str]] | None = None,
    dag_store=None,
    is_kb_agent: bool = False,
) -> list[dict]:
    """Create tools for a resident agent.

    Coco: DAG + memory + meta + call_worker + kb_read
    kb-agent: KB tools (read+write+admin) + call_worker + meta
    """
    tools = (
        _make_dag_tools(dag_store, sub_agent_executor) +
        _make_memory_tools() +
        _make_meta_tools() +
        _make_call_worker_tool(sub_agent_executor) +
        _make_kb_tools()
    )
    if is_kb_agent:
        tools += _make_kb_admin_tools()
    return tools
