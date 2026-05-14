"""Tool system — flat dict tools with registry and execution.

Provides create_core_tools() and create_main_ai_tools() as the only public API.
Internal implementations are organized by domain in submodules.
"""
import os
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


def create_core_tools(
    sub_agent_executor: Callable[[str, str], Awaitable[str]] | None = None,
    dag_dir: str = "runs",
    tavily_api_key: str | None = None,
    sandbox_run: Callable[[str], Awaitable[str]] | None = None,
) -> list[dict]:
    """Create the 26 core tools. Each is {name, description, parameters, execute}.

    Args:
        sub_agent_executor: Optional async callable(task, agent_id) -> task_id.
        dag_dir: Directory for DAG run storage (default: "runs").
        tavily_api_key: Optional Tavily API key. Defaults to TAVILY_API_KEY env var.
        sandbox_run: Optional async callable(code) -> output. When set, bash commands
                     run inside CubeSandbox MicroVM instead of local subprocess.
    """
    if tavily_api_key is None:
        tavily_api_key = os.environ.get("TAVILY_API_KEY")
    return [
        _make("read_file", "Read a file with offset/limit", {"path": "string", "offset": "integer", "limit": "integer"},
              lambda p, ctx: _read_file(p.get("path", ""), p.get("offset", 0), p.get("limit", 2000))),
        _make("write_file", "Write content to a file", {"path": "string", "content": "string"},
              lambda p, ctx: _write_file(p.get("path", ""), p.get("content", ""))),
        _make("edit_file", "Edit a file by replacing text", {"path": "string", "old": "string", "new": "string"},
              lambda p, ctx: _edit_file(p.get("path", ""), p.get("old", ""), p.get("new", ""))),
        _make("list_dir", "List directory contents", {"path": "string"},
              lambda p, ctx: _list_dir(p.get("path", ""))),
        _make("bash", "Execute shell command", {"command": "string"},
              lambda p, ctx: _bash(p.get("command", ""), {**(ctx or {}), "sandbox_run": sandbox_run})),
        _make("glob", "Find files by glob pattern", {"pattern": "string"},
              lambda p, ctx: _glob(p.get("pattern", ""))),
        _make("grep", "Search file contents with regex", {"pattern": "string", "path": "string"},
              lambda p, ctx: _grep(p.get("pattern", ""), p.get("path", ""))),
        _make("web_search", "Search the web", {"query": "string"},
              lambda p, ctx: _web_search(p.get("query", ""), {**(ctx or {}), "tavily_api_key": tavily_api_key})),
        _make("web_fetch", "Fetch URL content", {"url": "string"},
              lambda p, ctx: _web_fetch(p.get("url", ""))),
        _make("browser", "Browser control — navigate, get_text, get_content, screenshot, click, type, scroll, execute_js, go_back", {"action": "string"},
              lambda p, ctx: _browser(p.get("action", ""))),
        _make("sub_agent", "Spawn a sub-agent (async)", {"task": "string", "agent_id": "string"},
              (lambda p, ctx: (
                  f"[sub_agent] {p.get('task', '')} — stub"
              )) if sub_agent_executor is None else
              (lambda p, ctx: sub_agent_executor(p.get("task", ""), p.get("agent_id", "sub")))),
        _make("define_dag", "Define a DAG task graph", {"yaml": "string"},
              lambda p, ctx: _define_dag(p.get("yaml", ""), {**(ctx or {}), "dag_dir": dag_dir})),
        _make("append_stage", "Append a stage to an existing DAG run", {"run_id": "string", "stage_yaml": "string"},
              lambda p, ctx: _append_stage(p.get("run_id", ""), p.get("stage_yaml", ""), {**(ctx or {}), "dag_dir": dag_dir})),
        _make("update_dag", "Update a node in dag.yaml by dot-path", {"run_id": "string", "path": "string", "value": "string"},
              lambda p, ctx: _update_dag(p.get("run_id", ""), p.get("path", ""), p.get("value", ""), {**(ctx or {}), "dag_dir": dag_dir})),
        _make("dispatch_task", "Dispatch a task in a DAG run", {"run_id": "string", "task_id": "string", "prompt": "string"},
              lambda p, ctx: _dispatch_task(p.get("run_id", ""), p.get("task_id", ""), p.get("prompt", ""), {
                  **(ctx or {}), "dag_dir": dag_dir, "sub_agent_executor": sub_agent_executor
              })),
        _make("check_tasks", "Check pending task status", {},
              lambda p, ctx: _check_tasks(ctx or {})),
        _make("stop_task", "Cancel a running task", {"task_id": "string"},
              lambda p, ctx: _stop_task(p.get("task_id", ""), ctx or {})),
        _make("todo_write", "Structured task list", {"todos": "array"},
              lambda p, ctx: _todo_write(p.get("todos"), ctx or {})),
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
        _make("cron", "Schedule a recurring task", {"schedule": "string", "task": "string"},
              lambda p, ctx: _cron(p.get("schedule", ""), p.get("task", ""), ctx or {})),
        _make("current_status", "Agent runtime introspection", {},
              lambda p, ctx: _current_status(ctx or {})),
        _make("wait", "Sleep for seconds", {"seconds": "number"},
              lambda p, ctx: _wait(p.get("seconds", 0))),
    ]


def create_main_ai_tools(
    sub_agent_executor: Callable[[str, str], Awaitable[str]] | None = None,
    dag_dir: str = "runs",
    tavily_api_key: str | None = None,
) -> list[dict]:
    """Create the Main AI tool set — orchestration + read-only tools only.

    Main AI has NO execution tools (write_file, edit_file, bash, glob, grep, browser, sub_agent).
    It delegates all execution to sub-agents via dispatch_task.
    """
    if tavily_api_key is None:
        tavily_api_key = os.environ.get("TAVILY_API_KEY")
    return [
        _make("read_file", "Read a file with offset/limit", {"path": "string", "offset": "integer", "limit": "integer"},
              lambda p, ctx: _read_file(p.get("path", ""), p.get("offset", 0), p.get("limit", 2000))),
        _make("list_dir", "List directory contents", {"path": "string"},
              lambda p, ctx: _list_dir(p.get("path", ""))),
        _make("web_search", "Search the web", {"query": "string"},
              lambda p, ctx: _web_search(p.get("query", ""), {**(ctx or {}), "tavily_api_key": tavily_api_key})),
        _make("web_fetch", "Fetch URL content", {"url": "string"},
              lambda p, ctx: _web_fetch(p.get("url", ""))),
        _make("define_dag", "Define a DAG task graph", {"yaml": "string"},
              lambda p, ctx: _define_dag(p.get("yaml", ""), {**(ctx or {}), "dag_dir": dag_dir})),
        _make("append_stage", "Append a stage to an existing DAG run", {"run_id": "string", "stage_yaml": "string"},
              lambda p, ctx: _append_stage(p.get("run_id", ""), p.get("stage_yaml", ""), {**(ctx or {}), "dag_dir": dag_dir})),
        _make("update_dag", "Update a node in dag.yaml by dot-path", {"run_id": "string", "path": "string", "value": "string"},
              lambda p, ctx: _update_dag(p.get("run_id", ""), p.get("path", ""), p.get("value", ""), {**(ctx or {}), "dag_dir": dag_dir})),
        _make("dispatch_task", "Dispatch a task in a DAG run", {"run_id": "string", "task_id": "string", "prompt": "string"},
              lambda p, ctx: _dispatch_task(p.get("run_id", ""), p.get("task_id", ""), p.get("prompt", ""), {
                  **(ctx or {}), "dag_dir": dag_dir, "sub_agent_executor": sub_agent_executor
              })),
        _make("check_tasks", "Check pending task status", {},
              lambda p, ctx: _check_tasks(ctx or {})),
        _make("stop_task", "Cancel a running task", {"task_id": "string"},
              lambda p, ctx: _stop_task(p.get("task_id", ""), ctx or {})),
        _make("todo_write", "Structured task list", {"todos": "array"},
              lambda p, ctx: _todo_write(p.get("todos"), ctx or {})),
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
        _make("cron", "Schedule a recurring task", {"schedule": "string", "task": "string"},
              lambda p, ctx: _cron(p.get("schedule", ""), p.get("task", ""), ctx or {})),
        _make("current_status", "Agent runtime introspection", {},
              lambda p, ctx: _current_status(ctx or {})),
        _make("wait", "Sleep for seconds", {"seconds": "number"},
              lambda p, ctx: _wait(p.get("seconds", 0))),
    ]
