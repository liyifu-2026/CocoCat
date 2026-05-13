"""Tool system — flat dict tools with registry and execution."""

import json
import os
import uuid
from typing import Any, Callable, Awaitable

import yaml

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None


def create_core_tools(
    sub_agent_executor: Callable[[str, str], Awaitable[str]] | None = None,
    dag_dir: str = "runs",
    tavily_api_key: str | None = None,
    sandbox_run: Callable[[str], Awaitable[str]] | None = None,
) -> list[dict]:
    """Create the 20 core tools. Each is {name, description, parameters, execute}.

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


def _make(name: str, description: str, params: dict, execute_fn) -> dict:
    return {
        "name": name,
        "description": description,
        "parameters": params,
        "execute": execute_fn,
    }


class ToolRegistry:
    """Registry for executing tools."""

    def __init__(self, tools: list[dict]):
        self._tools = {t["name"]: t for t in tools}

    async def execute(self, name: str, params: dict, context: dict | None = None) -> str:
        """Execute a tool by name. Returns string result."""
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")
        context = context or {}
        result = tool["execute"](params, context)
        if callable(getattr(result, "__await__", None)):
            result = await result
        return str(result)

    def filter(self, allowed_names: set[str]) -> list[dict]:
        """Return tools whose names are in the allowed set."""
        return [t for name, t in self._tools.items() if name in allowed_names]

    def list_tools(self) -> list[dict]:
        return list(self._tools.values())


# ── concrete tool implementations (stubs for now, real logic in Phase 2) ──

def _read_file(path: str, offset: int = 0, limit: int = 2000) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        if offset:
            lines = lines[offset:]
        if limit:
            lines = lines[:limit]
        return "".join(lines)
    except Exception as e:
        return f"Error reading {path}: {e}"


def _write_file(path: str, content: str) -> str:
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Written {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error writing {path}: {e}"


def _edit_file(path: str, old_str: str, new_str: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
        if old_str not in content:
            return f"Error: old string not found in {path}"
        content = content.replace(old_str, new_str, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Edited {path}"
    except Exception as e:
        return f"Error editing {path}: {e}"


def _list_dir(path: str) -> str:
    try:
        items = os.listdir(path)
        items.sort()
        return "\n".join(items)
    except Exception as e:
        return f"Error listing {path}: {e}"


async def _bash(command: str, ctx: dict | None = None) -> str:
    if not command:
        return "Error: 'command' is required"

    ctx = ctx or {}
    sandbox_run = ctx.get("sandbox_run")

    if sandbox_run:
        # Run inside CubeSandbox MicroVM for hardware-level isolation
        code = (
            "import subprocess, sys\n"
            f"r = subprocess.run({command!r}, shell=True, capture_output=True, text=True, timeout=30)\n"
            "sys.stdout.write(r.stdout)\n"
            "if r.stderr:\n"
            "    sys.stderr.write(r.stderr)\n"
        )
        try:
            return await sandbox_run(code)
        except Exception as e:
            return f"Error in sandbox bash: {e}"

    # Local subprocess fallback
    import subprocess
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        out = result.stdout
        err = result.stderr
        if err:
            out += f"\n[stderr]\n{err}"
        return out.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: command timed out (30s)"
    except Exception as e:
        return f"Error: {e}"


def _grep(pattern: str, path: str) -> str:
    if not pattern:
        return "Error: 'pattern' is required"
    import subprocess
    try:
        cmd = ["grep", "-rn", pattern, path] if path else ["grep", "-rn", pattern, "."]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.stdout.strip() or "No matches found"
    except subprocess.TimeoutExpired:
        return "Error: grep timed out (30s)"
    except Exception as e:
        return f"Error: {e}"


def _memory_path(ctx: dict) -> str:
    if "memory_path" in ctx:
        return ctx["memory_path"]
    agent_dir = ctx.get("agent_dir", "agents/main")
    path = os.path.join(agent_dir, "memory", "memory.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def _pin(fact: str, ctx: dict) -> str:
    if not fact:
        return "Error: 'fact' is required"
    path = _memory_path(ctx)
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(fact if fact.endswith("\n") else fact + "\n")
        return f"Pinned: {fact}"
    except Exception as e:
        return f"Error pinning fact: {e}"


def _unpin(keyword: str, ctx: dict) -> str:
    if not keyword:
        return "Error: 'keyword' is required"
    path = _memory_path(ctx)
    try:
        if not os.path.exists(path):
            return f"No facts matching '{keyword}' found"
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        kept = [l for l in lines if keyword.lower() not in l.lower()]
        if len(kept) == len(lines):
            return f"No facts matching '{keyword}' found"
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(kept)
        return f"Unpinned facts matching '{keyword}'"
    except Exception as e:
        return f"Error unpinning fact: {e}"


async def _wait(seconds: float) -> str:
    import asyncio
    try:
        secs = float(seconds) if seconds else 0
        if secs < 0:
            return "Error: seconds must be non-negative"
        if secs > 0:
            await asyncio.sleep(secs)
        return f"Waited {secs}s" if secs > 0 else "Waited 0s"
    except (ValueError, TypeError):
        return "Error: 'seconds' must be a number"


def _current_status(ctx: dict) -> str:
    parts = []
    if ctx.get("agent_id"):
        parts.append(f"agent_id: {ctx['agent_id']}")
    if ctx.get("bound_scene"):
        parts.append(f"bound_scene: {ctx['bound_scene']}")
    if ctx.get("role"):
        parts.append(f"role: {ctx['role']}")
    parts.append(f"tools: 20 core tools loaded")
    return "\n".join(parts)


def _todo_write(todos, ctx: dict) -> str:
    if todos is None:
        return "Error: 'todos' is required"
    path = ctx.get("todos_path", "todos.json")
    import json
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(todos, f, indent=2, ensure_ascii=False)
        return f"Saved {len(todos)} todo items to {path}"
    except Exception as e:
        return f"Error saving todos: {e}"


def _web_fetch(url: str) -> str:
    if not url:
        return "Error: 'url' is required"
    import httpx
    try:
        resp = httpx.get(url, timeout=15.0, follow_redirects=True)
        resp.raise_for_status()
        text = resp.text
        return text[:5000] + ("..." if len(text) > 5000 else "")
    except httpx.TimeoutException:
        return "Error: request timed out"
    except Exception as e:
        return f"Error fetching {url}: {e}"


def _web_search(query: str, ctx: dict | None = None) -> str:
    if not query:
        return "Error: 'query' is required"
    ctx = ctx or {}
    api_key = ctx.get("tavily_api_key")
    if not api_key:
        return ("Web search requires a search API key (e.g. Tavily, SerpAPI). "
                f"Configure it to enable live search. Query was: {query}")
    if TavilyClient is None:
        return "Error: tavily-python package not installed. Run: pip install tavily-python"
    try:
        client = TavilyClient(api_key=api_key)
        response = client.search(query, max_results=5)
        results = response.get("results", [])
        if not results:
            return f"No results found for: {query}"
        lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "Untitled")
            url = r.get("url", "")
            content = r.get("content", "")
            lines.append(f"{i}. {title}\n   {url}\n   {content[:200]}")
        return "\n\n".join(lines)
    except Exception as e:
        return f"Error searching '{query}': {e}"


def _check_tasks(ctx: dict) -> str:
    import json
    dag_dir = ctx.get("dag_dir")
    if dag_dir and os.path.isdir(dag_dir):
        return _check_dag_tasks(dag_dir)

    tasks_path = ctx.get("tasks_path", "runs")
    tasks_file = os.path.join(tasks_path, "tasks.json")
    if not os.path.exists(tasks_file):
        return "No pending tasks"
    try:
        tasks = json.load(open(tasks_file))
        if not tasks:
            return "No pending tasks"
        lines = [f"{t.get('id', '?')}: {t.get('status', 'unknown')} — {t.get('description', '')}" for t in tasks]
        return "\n".join(lines)
    except Exception as e:
        return f"Error reading tasks: {e}"


def _check_dag_tasks(dag_dir: str) -> str:
    import json
    if not os.path.isdir(dag_dir):
        return "No pending tasks"

    entries = []
    for run_dir in sorted(os.listdir(dag_dir)):
        dag_path = os.path.join(dag_dir, run_dir, "dag.yaml")
        if not os.path.exists(dag_path):
            continue
        try:
            with open(dag_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except (yaml.YAMLError, OSError):
            continue

        run_id = data.get("run_id", run_dir)
        run_status = data.get("status", "?")
        entries.append(f"[{run_id}] run: {run_status}")

        for stage in data.get("stages", []):
            stage_id = stage.get("id", "?")
            stage_status = stage.get("status", "?")
            entries.append(f"  [{stage_id}] stage: {stage_status}")
            for task in stage.get("tasks", []):
                tid = task.get("id", "?")
                tstatus = task.get("status", "?")
                entries.append(f"    {tid}: {tstatus}")

    if not entries:
        return "No pending tasks"
    return "\n".join(entries)


def _stop_task(task_id: str, ctx: dict) -> str:
    if not task_id:
        return "Error: 'task_id' is required"
    cancel_dir = ctx.get("cancel_dir", "runs/cancellations")
    import json
    try:
        os.makedirs(cancel_dir, exist_ok=True)
        marker = os.path.join(cancel_dir, f"{task_id}.cancel")
        with open(marker, "w") as f:
            json.dump({"task_id": task_id, "cancelled_at": str(__import__("datetime").datetime.now())}, f)
        return f"Cancellation requested for task '{task_id}'"
    except Exception as e:
        return f"Error cancelling task: {e}"


def _recall(query: str, ctx: dict) -> str:
    if not query:
        return "Error: 'query' is required"
    q = query.lower()
    results = []

    mem_path = _memory_path(ctx)
    if os.path.exists(mem_path):
        with open(mem_path, encoding="utf-8") as f:
            for line in f:
                if q in line.lower():
                    results.append(("memory", line.strip()))

    exp_path = ctx.get("exp_path", "memory/experiences")
    if os.path.isdir(exp_path):
        for root, _, files in os.walk(exp_path):
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, encoding="utf-8") as f:
                    content = f.read()
                if q in content.lower():
                    results.append((os.path.relpath(root, exp_path), content.strip()[:200]))

    if not results:
        return "No matches found"
    return "\n---\n".join(f"[{src}] {text}" for src, text in results)


def _record_experience(category: str, entry: str, ctx: dict) -> str:
    if not category:
        return "Error: 'category' is required"
    if not entry:
        return "Error: 'entry' is required"
    exp_path = ctx.get("exp_path", "memory/experiences")
    cat_dir = os.path.join(exp_path, category)
    try:
        os.makedirs(cat_dir, exist_ok=True)
        slug = entry.lower().strip()[:60].replace(" ", "-").replace("/", "-")
        fname = f"{slug}.md"
        fpath = os.path.join(cat_dir, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(entry if entry.endswith("\n") else entry + "\n")
        return f"Recorded experience in '{category}': {entry[:80]}"
    except Exception as e:
        return f"Error recording experience: {e}"


def _recall_experience(category: str, ctx: dict) -> str:
    if not category:
        return "Error: 'category' is required"
    exp_path = ctx.get("exp_path", "memory/experiences")
    cat_dir = os.path.join(exp_path, category)
    if not os.path.isdir(cat_dir):
        return f"No experiences found for category '{category}'"
    try:
        entries = []
        for fname in sorted(os.listdir(cat_dir)):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(cat_dir, fname)
            with open(fpath, encoding="utf-8") as f:
                content = f.read().strip()
            entries.append(f"{fname[:-3]}:\n{content}")
        if not entries:
            return f"No experiences found for category '{category}'"
        return "\n\n".join(entries)
    except Exception as e:
        return f"Error reading experiences: {e}"


def _cron(schedule: str, task: str, ctx: dict) -> str:
    if not schedule:
        return "Error: 'schedule' is required"
    if not task:
        return "Error: 'task' is required"
    import json
    import uuid
    cron_path = ctx.get("cron_path", "runs/cron")
    try:
        os.makedirs(cron_path, exist_ok=True)
        entry = {
            "id": str(uuid.uuid4())[:8],
            "schedule": schedule,
            "task": task,
            "created_at": str(__import__("datetime").datetime.now()),
            "status": "active",
        }
        fname = f"{entry['id']}.json"
        with open(os.path.join(cron_path, fname), "w") as f:
            json.dump(entry, f, indent=2)
        return f"Scheduled task '{task}' with schedule '{schedule}' (id: {entry['id']})"
    except Exception as e:
        return f"Error scheduling task: {e}"


def _define_dag(yaml_str: str, ctx: dict) -> str:
    if not yaml_str:
        return "Error: 'yaml' is required"
    try:
        data = yaml.safe_load(yaml_str)
    except yaml.YAMLError as e:
        return f"Error parsing YAML: {e}"

    dag_dir = ctx.get("dag_dir", "runs")
    run_id = uuid.uuid4().hex[:12]
    run_dir = os.path.join(dag_dir, run_id)
    os.makedirs(run_dir, exist_ok=True)

    data["run_id"] = run_id
    data.setdefault("created_by", "main")
    data.setdefault("status", "running")
    for stage in data.get("stages", []):
        for task in stage.get("tasks", []):
            task.setdefault("status", "pending")

    dag_path = os.path.join(run_dir, "dag.yaml")
    with open(dag_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

    return run_id


def _load_dag(run_id: str, dag_dir: str) -> tuple[dict | None, str | None]:
    dag_path = os.path.join(dag_dir, run_id, "dag.yaml")
    if not os.path.exists(dag_path):
        return None, f"Error: run '{run_id}' not found"
    try:
        with open(dag_path, encoding="utf-8") as f:
            return yaml.safe_load(f), None
    except yaml.YAMLError as e:
        return None, f"Error reading dag.yaml: {e}"


def _save_dag(run_id: str, data: dict, dag_dir: str) -> None:
    dag_path = os.path.join(dag_dir, run_id, "dag.yaml")
    with open(dag_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


def _append_stage(run_id: str, stage_yaml: str, ctx: dict) -> str:
    if not run_id:
        return "Error: 'run_id' is required"
    if not stage_yaml:
        return "Error: 'stage_yaml' is required"

    dag_dir = ctx.get("dag_dir", "runs")
    data, err = _load_dag(run_id, dag_dir)
    if err:
        return err

    try:
        stage = yaml.safe_load(stage_yaml)
    except yaml.YAMLError as e:
        return f"Error parsing stage_yaml: {e}"

    stage.setdefault("status", "pending")
    for task in stage.get("tasks", []):
        task.setdefault("status", "pending")

    data.setdefault("stages", []).append(stage)
    _save_dag(run_id, data, dag_dir)
    return f"Appended stage '{stage.get('id', '?')}' to run '{run_id}'"


def _update_dag(run_id: str, path: str, value: str, ctx: dict) -> str:
    if not run_id:
        return "Error: 'run_id' is required"
    if not path:
        return "Error: 'path' is required"
    if not value:
        return "Error: 'value' is required"

    dag_dir = ctx.get("dag_dir", "runs")
    data, err = _load_dag(run_id, dag_dir)
    if err:
        return err

    parts = path.split(".")
    node = data
    for i, key in enumerate(parts[:-1]):
        idx = int(key) if key.isdigit() else key
        try:
            node = node[idx]
        except (KeyError, IndexError, TypeError):
            return f"Error: path '{path}' not found at segment '{key}'"

    final_key = parts[-1]
    final_idx = int(final_key) if final_key.isdigit() else final_key
    # Try to parse value (int, bool, or keep as string)
    if value.isdigit():
        parsed_value = int(value)
    elif value.lower() in ("true", "false"):
        parsed_value = value.lower() == "true"
    else:
        parsed_value = value

    try:
        node[final_idx] = parsed_value
    except (KeyError, IndexError, TypeError):
        return f"Error: path '{path}' not found at final segment '{final_key}'"

    _save_dag(run_id, data, dag_dir)
    return f"Updated '{path}' to '{value}' in run '{run_id}'"


async def _dispatch_task(run_id: str, task_id: str, prompt: str, ctx: dict) -> str:
    if not run_id:
        return "Error: 'run_id' is required"
    if not task_id:
        return "Error: 'task_id' is required"
    if not prompt:
        return "Error: 'prompt' is required"

    dag_dir = ctx.get("dag_dir", "runs")
    executor = ctx.get("sub_agent_executor")

    if not executor:
        return "Error: sub_agent_executor not configured — dispatch_task requires a running agent system"

    data, err = _load_dag(run_id, dag_dir)
    if err:
        return err

    # Find the task
    task_node = None
    for stage in data.get("stages", []):
        for task in stage.get("tasks", []):
            if task.get("id") == task_id:
                task_node = task
                break
        if task_node:
            break

    if task_node is None:
        return f"Error: task '{task_id}' not found in run '{run_id}'"

    # Mark running
    task_node["status"] = "running"
    _save_dag(run_id, data, dag_dir)

    # Execute via sub_agent_executor
    try:
        result = await executor(prompt, task_id)
    except Exception as e:
        task_node["status"] = "failed"
        task_node["error"] = str(e)
        _save_dag(run_id, data, dag_dir)
        return f"Error dispatching task '{task_id}': {e}"

    # Mark done
    task_node["status"] = "done"
    task_node["result"] = result
    _save_dag(run_id, data, dag_dir)

    return f"Task '{task_id}' completed in run '{run_id}'"


def _glob(pattern: str) -> str:
    if not pattern:
        return "Error: 'pattern' is required"
    import glob as glob_mod
    try:
        matches = glob_mod.glob(pattern, recursive=True)
        matches.sort()
        return "\n".join(matches) if matches else ""
    except Exception as e:
        return f"Error glob: {e}"


async def _browser(action_str: str) -> str:
    """Execute browser actions via Playwright.

    action_str is a JSON string: {"type": "...", ...}
    Supported types: navigate, get_text, get_content, screenshot, click, type, scroll, execute_js, go_back
    """
    if not action_str:
        return "Error: 'action' is required"

    try:
        action = json.loads(action_str)
    except json.JSONDecodeError as e:
        return f"Error parsing action JSON: {e}"

    action_type = action.get("type", "")
    if not action_type:
        return "Error: action 'type' is required"

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return "Error: playwright not installed. Run: pip install playwright && playwright install chromium"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()

                if action_type == "navigate":
                    url = action.get("url", "")
                    if not url:
                        return "Error: 'url' is required for navigate action"
                    await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    text = await page.inner_text("body")
                    title = await page.title()
                    return f"Title: {title}\n\n{text[:5000]}"

                elif action_type == "get_text":
                    text = await page.inner_text("body")
                    return text[:5000] if text else "(empty page)"

                elif action_type == "get_content":
                    selector = action.get("selector")
                    if selector:
                        try:
                            el = await page.wait_for_selector(selector, timeout=5000)
                            text = await el.inner_text()
                            return text[:5000] if text else "(empty element)"
                        except Exception:
                            html = await page.content()
                            return html[:5000]
                    html = await page.content()
                    return html[:5000]

                elif action_type == "screenshot":
                    import base64
                    url = action.get("url")
                    if url:
                        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    screenshot_bytes = await page.screenshot(full_page=action.get("full_page", False))
                    b64 = base64.b64encode(screenshot_bytes).decode()
                    path = action.get("save_path")
                    if path:
                        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                        with open(path, "wb") as f:
                            f.write(screenshot_bytes)
                        return f"Screenshot saved to {path} ({len(screenshot_bytes)} bytes)"
                    return f"Screenshot: {len(screenshot_bytes)} bytes (base64 length: {len(b64)})"

                elif action_type == "click":
                    url = action.get("url")
                    if url:
                        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    selector = action.get("selector", "")
                    if not selector:
                        return "Error: 'selector' is required for click action (CSS selector or text=...)"
                    try:
                        await page.click(selector, timeout=10000)
                        return f"Clicked '{selector}'"
                    except Exception as e:
                        try:
                            await page.click(f"text={selector}", timeout=5000)
                            return f"Clicked text '{selector}'"
                        except Exception:
                            return f"Error clicking '{selector}': {e}"

                elif action_type == "type":
                    url = action.get("url")
                    if url:
                        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    selector = action.get("selector", "")
                    text = action.get("text", "")
                    if not selector:
                        return "Error: 'selector' is required for type action"
                    await page.fill(selector, text, timeout=10000)
                    return f"Typed into '{selector}'"

                elif action_type == "scroll":
                    url = action.get("url")
                    if url:
                        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    direction = action.get("direction", "down")
                    amount = action.get("amount", 300)
                    if direction == "down":
                        await page.evaluate(f"window.scrollBy(0, {amount})")
                    elif direction == "up":
                        await page.evaluate(f"window.scrollBy(0, -{amount})")
                    else:
                        return f"Error: unknown scroll direction '{direction}'. Use 'up' or 'down'"
                    return f"Scrolled {direction} by {amount}px"

                elif action_type == "execute_js":
                    url = action.get("url")
                    if url:
                        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    code = action.get("code", "")
                    if not code:
                        return "Error: 'code' is required for execute_js action"
                    result = await page.evaluate(code)
                    return str(result) if result is not None else "(no return value)"

                elif action_type == "go_back":
                    await page.go_back()
                    text = await page.inner_text("body")
                    title = await page.title()
                    return f"[Back] Title: {title}\n\n{text[:5000]}"

                else:
                    return f"Error: unknown action type '{action_type}'. Supported: navigate, get_text, get_content, screenshot, click, type, scroll, execute_js, go_back"

            finally:
                await browser.close()
    except Exception as e:
        return f"Error in browser {action_type}: {e}"
