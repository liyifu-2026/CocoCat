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
    _create_kb,
)
from cococat.core.types import ToolContext, DagEnv, SandboxEnv, WebEnv


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


def _make_readonly_file_tools() -> list[dict]:
    """Read-only file tools for Coco — safe exploration, no writes."""
    return [
        _make("read_file", "Read a file with offset/limit", {"path": "string", "offset": "integer", "limit": "integer"},
              lambda p, ctx: _read_file(p.get("path", ""), p.get("offset", 0), p.get("limit", 2000)),
              requires_sandbox=True, sandbox_operation="read"),
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
              lambda p, ctx: _bash(p.get("command", ""), _merge_ctx(ctx, sandbox=SandboxEnv(run=sandbox_run))),
              requires_sandbox=True, sandbox_operation="exec"),
        _make("browser", "Browser control — navigate, get_text, get_content, screenshot, click, type, scroll, execute_js, go_back",
              {"action": "string"},
              lambda p, ctx: _browser(p.get("action", "")),
              requires_sandbox=True, sandbox_operation="exec"),
    ]


def _make_web_tools(tavily_api_key: str | None = None) -> list[dict]:
    return [
        _make("web_search", "Search the web", {"query": "string"},
              lambda p, ctx: _web_search(p.get("query", ""), _merge_ctx(ctx, web=WebEnv(tavily_api_key=tavily_api_key)))),
        _make("web_fetch", "Fetch URL content", {"url": "string"},
              lambda p, ctx: _web_fetch(p.get("url", ""))),
    ]


def _make_dag_tools(dag_store=None, sub_agent_executor=None) -> list[dict]:
    return [
        _make("define_dag", "Define a DAG task graph", {"yaml": "string"},
              lambda p, ctx: _define_dag(p.get("yaml", ""), _merge_ctx(ctx, dag=DagEnv(store=dag_store)))),
        _make("append_stage", "Append a stage to an existing DAG run", {"run_id": "string", "stage_yaml": "string"},
              lambda p, ctx: _append_stage(p.get("run_id", ""), p.get("stage_yaml", ""), _merge_ctx(ctx, dag=DagEnv(store=dag_store)))),
        _make("update_dag", "Update a node in dag.yaml by dot-path", {"run_id": "string", "path": "string", "value": "string"},
              lambda p, ctx: _update_dag(p.get("run_id", ""), p.get("path", ""), p.get("value", ""), _merge_ctx(ctx, dag=DagEnv(store=dag_store)))),
        _make("dispatch_task", "Dispatch a task in a DAG run", {"run_id": "string", "task_id": "string", "prompt": "string", "title": "string"},
              lambda p, ctx: _dispatch_task(p.get("run_id", ""), p.get("task_id", ""), p.get("prompt", ""),
                  _merge_ctx(ctx, dag=DagEnv(store=dag_store, executor=sub_agent_executor)), p.get("title"))),
        _make("check_tasks", "Check pending task status", {},
              lambda p, ctx: _check_tasks(_merge_ctx(ctx, dag=DagEnv(store=dag_store)))),
        _make("stop_task", "Cancel a running task", {"task_id": "string"},
              lambda p, ctx: _stop_task(p.get("task_id", ""), _ensure_tool_context(ctx))),
    ]


def _make_memory_tools() -> list[dict]:
    return [
        _make("recall", "Search memory by keyword (FTS5)", {"query": "string"},
              lambda p, ctx: _recall(p.get("query", ""), _ensure_tool_context(ctx))),
        _make("pin", "Pin a fact to persistent context", {"fact": "string"},
              lambda p, ctx: _pin(p.get("fact", ""), _ensure_tool_context(ctx))),
        _make("unpin", "Unpin a fact", {"keyword": "string"},
              lambda p, ctx: _unpin(p.get("keyword", ""), _ensure_tool_context(ctx))),
        _make("record_experience", "Record a categorized experience", {"category": "string", "entry": "string"},
              lambda p, ctx: _record_experience(p.get("category", ""), p.get("entry", ""), _ensure_tool_context(ctx))),
        _make("recall_experience", "Recall experiences by category", {"category": "string"},
              lambda p, ctx: _recall_experience(p.get("category", ""), _ensure_tool_context(ctx))),
    ]


def _make_meta_tools() -> list[dict]:
    return [
        _make("todo_write", "Structured task list", {"todos": "array"},
              lambda p, ctx: _todo_write(p.get("todos"), _ensure_tool_context(ctx))),
        _make("cron", "Schedule a recurring task", {"schedule": "string", "task": "string"},
              lambda p, ctx: _cron(p.get("schedule", ""), p.get("task", ""), _ensure_tool_context(ctx))),
        _make("current_status", "Agent runtime introspection", {},
              lambda p, ctx: _current_status(_ensure_tool_context(ctx))),
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
        _make("search_kb", "Search knowledge base with inverted index (supports multi-keyword AND/OR)", 
              {"kb_name": "string", "query": "string", "mode": "string", "type": "string", "tag": "string", "source": "string", "limit": "integer"},
              lambda p, ctx: _search_kb(p, _ensure_tool_context(ctx))),
        _make("read_wiki", "Read a wiki page", {"kb_name": "string", "type": "string", "slug": "string"},
              lambda p, ctx: _read_wiki(p, _ensure_tool_context(ctx))),
        _make("list_kbs", "List available knowledge bases", {},
              lambda p, ctx: _list_kbs(p, _ensure_tool_context(ctx))),
    ]


def _make_kb_admin_tools() -> list[dict]:
    """KB admin tools (write + maintenance) for kb-agent only."""
    return [
        _make("create_kb", "Create a new knowledge base with proper directory structure", {"kb_name": "string", "purpose": "string"},
              lambda p, ctx: _create_kb(p, _ensure_tool_context(ctx))),
        _make("write_wiki", "Write a wiki page", {"kb_name": "string", "type": "string", "slug": "string", "content": "string", "title": "string"},
              lambda p, ctx: _write_wiki(p, _ensure_tool_context(ctx))),
        _make("run_dedup", "Run KB dedup pipeline", {"kb_name": "string"},
              lambda p, ctx: _run_dedup(p, _ensure_tool_context(ctx))),
        _make("run_lint", "Run KB health check", {"kb_name": "string"},
              lambda p, ctx: _run_lint(p, _ensure_tool_context(ctx))),
        _make("gen_overview", "Generate KB overview", {"kb_name": "string"},
              lambda p, ctx: _gen_overview(p, _ensure_tool_context(ctx))),
        _make("cascade_del", "Cascade delete source file from KB", {"kb_name": "string", "source_filename": "string"},
              lambda p, ctx: _cascade_del(p, _ensure_tool_context(ctx))),
        _make("get_graph", "Get KB knowledge graph", {"kb_name": "string"},
              lambda p, ctx: _get_graph(p, _ensure_tool_context(ctx))),
    ]


def _make_call_worker_tool(sub_agent_executor=None) -> list[dict]:
    """call_worker tool for resident agents to invoke worker pool."""
    return [
        _make("call_worker", "Call a worker agent for execution", {"task": "string"},
              (lambda p, ctx: f"[call_worker] {p.get('task', '')} — stub")
              if sub_agent_executor is None else
              (lambda p, ctx: _call_worker(p, _merge_ctx(ctx, dag=DagEnv(executor=sub_agent_executor))))),
    ]


# ── Context helpers ────────────────────────────────────────

def _ensure_tool_context(ctx: dict | ToolContext | None) -> ToolContext:
    """Convert a dict or None to a ToolContext safely."""
    return ToolContext.from_dict(ctx)


def _merge_ctx(ctx: dict | ToolContext | None, **overrides) -> ToolContext:
    """Merge overrides into ctx, returning a new ToolContext."""
    base = _ensure_tool_context(ctx)
    for key, val in overrides.items():
        setattr(base, key, val)
    return base


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
    """Create Coco's tools.

    Coco CAN directly: read_file, list_dir, glob, grep, web_search, web_fetch.
    Coco MUST use DAG for: write_file, edit_file, bash, browser (sub-agents only).
    """
    if tavily_api_key is None:
        tavily_api_key = os.environ.get("TAVILY_API_KEY")
    return (
        _make_dag_tools(dag_store, sub_agent_executor) +
        _make_memory_tools() +
        _make_meta_tools() +
        _make_readonly_file_tools() +
        _make_web_tools(tavily_api_key) +
        _make_kb_tools()
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
    if is_kb_agent:
        tools = (
            _make_file_tools() +
            _make_memory_tools() +
            _make_meta_tools() +
            _make_call_worker_tool(sub_agent_executor) +
            _make_kb_tools() +
            _make_kb_admin_tools()
        )
    else:
        tools = (
            _make_dag_tools(dag_store, sub_agent_executor) +
            _make_memory_tools() +
            _make_meta_tools() +
            _make_call_worker_tool(sub_agent_executor) +
            _make_kb_tools()
        )
    return tools
