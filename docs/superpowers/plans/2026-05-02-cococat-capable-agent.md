# Capable Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Each Python agent becomes a capable LLM-driven agent with a ReAct loop, tools (read/write/exec/sub-agent), and sub-agent spawning — modeled after nanobot's AgentRunner and claw-code's Agent tool.

**Architecture:** The Python agent_runtime.py entry point dispatches to an AgentLoop (ReAct pattern). The AgentLoop calls an LLM provider, which returns text or tool calls. Tool calls are executed via a ToolRegistry. The `sub_agent` tool spawns a child Python agent process. All communication with the Rust core remains JSON-RPC over stdin/stdout.

**Prerequisites:** MVP is complete (Tasks 1-6). Multi-agent config exists (Task 1-6 from multi-agent plan, or just the current single-agent setup).

---

## File Structure

```
py-agent/
├── agent_runtime.py      # MODIFIED: entry point, JSON-RPC dispatch, agent loop orchestration
├── llm.py                # NEW: LLM client (OpenAI API)
├── tools.py              # NEW: tool definitions + ToolRegistry
├── context.py            # NEW: system prompt builder
└── requirements.txt      # NEW: Python dependencies
```

---

### Task 1: Python project setup + LLM client

**Files:**
- Create: `py-agent/requirements.txt`
- Create: `py-agent/llm.py`

- [ ] **Step 1: Create requirements.txt**

```
openai>=1.0.0
```

- [ ] **Step 2: Install dependencies**

```powershell
pip install -r py-agent/requirements.txt
```

- [ ] **Step 3: Write llm.py — OpenAI client**

```python
"""OpenAI-compatible LLM client (nanobot pattern)."""
import json
import os
from openai import OpenAI


class LLMClient:
    """Thin wrapper around OpenAI API for chat completions."""

    def __init__(self, api_key: str | None = None, model: str | None = None, base_url: str | None = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model or os.environ.get("LLM_MODEL", "gpt-4o-mini")
        base_url = base_url or os.environ.get("OPENAI_BASE_URL", "")
        self.client = OpenAI(api_key=self.api_key, base_url=base_url or None)

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> dict:
        """Call LLM and return response with content and/or tool_calls."""
        kwargs = dict(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        result = {
            "content": choice.message.content or "",
            "tool_calls": [],
            "finish_reason": choice.finish_reason,
        }

        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {"_error": f"failed to parse arguments: {tc.function.arguments}"}
                result["tool_calls"].append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": args,
                })

        return result
```

- [ ] **Step 4: Quick test**

```powershell
python -c "from llm import LLMClient; c = LLMClient(); r = c.chat([{'role':'user','content':'say hello'}], max_tokens=50); print(r['content'])"
```

Note: This will fail if OPENAI_API_KEY is not set. That's OK — test properly when environment is configured.

- [ ] **Step 5: Commit**

```bash
git add py-agent/requirements.txt py-agent/llm.py
git commit -m "feat: add Python LLM client (OpenAI)"
```

---

### Task 2: Tool definitions + ToolRegistry

**Files:**
- Create: `py-agent/tools.py`

- [ ] **Step 1: Write tools.py**

```python
"""Tool definitions and ToolRegistry (nanobot + claw-code patterns)."""
import json
import subprocess
import os
import glob as glob_module
from pathlib import Path


class Tool:
    """Base tool class (nanobot Tool pattern)."""
    name: str = ""
    description: str = ""
    parameters: dict = {}

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def execute(self, **kwargs) -> str:
        raise NotImplementedError


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read a text file. Specify path (required), offset (1-based, default 1), and limit (default 2000 lines)."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to read"},
            "offset": {"type": "integer", "description": "Starting line (1-based)", "minimum": 1},
            "limit": {"type": "integer", "description": "Max lines to read", "minimum": 1},
        },
        "required": ["path"],
    }

    def execute(self, path="", offset=1, limit=2000, **kwargs) -> str:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            start = max(0, offset - 1)
            end = min(len(lines), start + limit)
            selected = lines[start:end]
            result = "".join(selected)
            total = len(lines)
            return f"{result}\n[Read {len(selected)} lines, file has {total} total lines]"
        except FileNotFoundError:
            return f"Error: file not found: {path}"
        except Exception as e:
            return f"Error reading file: {e}"


class WriteFileTool(Tool):
    name = "write_file"
    description = "Write content to a file, creating directories if needed."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to write"},
            "content": {"type": "string", "description": "Content to write"},
        },
        "required": ["path", "content"],
    }

    def execute(self, path="", content="", **kwargs) -> str:
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote {len(content)} bytes to {path}"
        except Exception as e:
            return f"Error writing file: {e}"


class ExecCommandTool(Tool):
    name = "exec_command"
    description = "Execute a shell command. Returns stdout + stderr. Use timeout for long-running commands."
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to run"},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "minimum": 1},
            "description": {"type": "string", "description": "Brief description of what this command does"},
        },
        "required": ["command"],
    }

    def execute(self, command="", timeout=60, description="", **kwargs) -> str:
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            if result.returncode != 0:
                output += f"\n[exit code: {result.returncode}]"
            return output.strip() or "(no output)"
        except subprocess.TimeoutExpired:
            return f"Error: command timed out after {timeout}s"
        except Exception as e:
            return f"Error executing command: {e}"


class GlobSearchTool(Tool):
    name = "glob_search"
    description = "Search for files matching a glob pattern. Example: **/*.py"
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern to search"},
            "path": {"type": "string", "description": "Root directory to search from"},
        },
        "required": ["pattern"],
    }

    def execute(self, pattern="", path=".", **kwargs) -> str:
        try:
            matches = glob_module.glob(pattern, root_dir=path, recursive=True)
            matches = [m for m in matches if not m.startswith(".git/") and m != ".git"]
            if not matches:
                return "No files found."
            result = "\n".join(sorted(matches)[:100])
            total = len(matches)
            if total > 100:
                result += f"\n... and {total - 100} more"
            return result
        except Exception as e:
            return f"Error searching: {e}"


class GrepSearchTool(Tool):
    name = "grep_search"
    description = "Search file contents using a regex pattern."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regex pattern to search for"},
            "include": {"type": "string", "description": "File glob pattern to filter (e.g. *.py)"},
            "path": {"type": "string", "description": "Root directory"},
        },
        "required": ["pattern"],
    }

    def execute(self, pattern="", include="*", path=".", **kwargs) -> str:
        try:
            matches = []
            for root, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if d != ".git"]
                for f in files:
                    if not glob_module.fnmatch.fnmatch(f, include):
                        continue
                    fp = os.path.join(root, f)
                    try:
                        with open(fp, "r", encoding="utf-8", errors="replace") as fh:
                            for i, line in enumerate(fh, 1):
                                import re
                                if re.search(pattern, line):
                                    rel = os.path.relpath(fp, path)
                                    matches.append(f"{rel}:{i}: {line.rstrip()[:200]}")
                    except Exception:
                        pass
            if not matches:
                return "No matches found."
            result = "\n".join(matches[:50])
            total = len(matches)
            if total > 50:
                result += f"\n... and {total - 50} more matches"
            return result
        except Exception as e:
            return f"Error searching: {e}"


class ToolRegistry:
    """Registry of available tools (nanobot ToolRegistry pattern)."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def get_definitions(self) -> list[dict]:
        return [t.to_openai_schema() for t in self._tools.values()]

    def execute(self, name: str, arguments: dict) -> str:
        tool = self._tools.get(name)
        if not tool:
            return f"Error: unknown tool '{name}'"
        try:
            return tool.execute(**arguments)
        except Exception as e:
            return f"Error executing {name}: {e}"


def create_default_registry(sub_agent_callback=None) -> ToolRegistry:
    """Create registry with all standard tools."""
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(ExecCommandTool())
    registry.register(GlobSearchTool())
    registry.register(GrepSearchTool())
    return registry
```

- [ ] **Step 2: Quick test**

```powershell
python -c "from tools import create_default_registry; r = create_default_registry(); print([t.name for t in r._tools.values()])"
```

Expected: `['read_file', 'write_file', 'exec_command', 'glob_search', 'grep_search']`

- [ ] **Step 3: Commit**

```bash
git add py-agent/tools.py
git commit -m "feat: add tool definitions and ToolRegistry"
```

---

### Task 3: Context builder

**Files:**
- Create: `py-agent/context.py`

- [ ] **Step 1: Write context.py**

```python
"""System prompt builder (nanobot ContextBuilder pattern)."""
import os


SYSTEM_PROMPT_TEMPLATE = """You are {agent_name}, a capable AI agent in the CocoCat multi-agent team.

## Identity
- Name: {agent_name}
- ID: {agent_id}

## Capabilities
You have access to the following tools:
{tool_descriptions}

## Guidelines
1. You can use tools to read/write files, execute commands, and search the workspace.
2. When you need to delegate a subtask, use the sub_agent tool to spawn a child agent.
3. Think step by step before using tools.
4. When you have completed the task, provide a clear summary of what was done.
5. You work in the directory: {workspace}

## Communication
- You receive tasks via your team and report results back.
- Be concise but thorough in your responses.
"""


def build_system_prompt(
    agent_id: str = "unknown",
    agent_name: str = "Agent",
    tool_descriptions: str = "",
    workspace: str = "",
) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        agent_id=agent_id,
        agent_name=agent_name,
        tool_descriptions=tool_descriptions,
        workspace=workspace or os.getcwd(),
    )


def build_tool_descriptions(tools: list[dict]) -> str:
    """Build a human-readable tool list from OpenAI-style tool definitions."""
    lines = []
    for t in tools:
        name = t["function"]["name"]
        desc = t["function"]["description"]
        params = t["function"]["parameters"]
        required = params.get("required", [])
        props = params.get("properties", {})
        param_lines = []
        for pname, pinfo in props.items():
            req = "required" if pname in required else "optional"
            param_lines.append(f"    {pname} ({req}): {pinfo.get('description', '')}")
        param_str = "\n" + "\n".join(param_lines) if param_lines else ""
        lines.append(f"- {name}: {desc}{param_str}")
    return "\n".join(lines)
```

- [ ] **Step 2: Quick test**

```powershell
python -c "from context import build_system_prompt, build_tool_descriptions; print(build_system_prompt('test', 'TestAgent', 'tools: read_file'))"
```

- [ ] **Step 3: Commit**

```bash
git add py-agent/context.py
git commit -m "feat: add system prompt builder"
```

---

### Task 4: Agent loop with ReAct pattern

**Files:**
- Create: `py-agent/agent_loop.py`

- [ ] **Step 1: Write agent_loop.py**

```python
"""ReAct agent loop (nanobot AgentRunner + claw-code ConversationRuntime pattern)."""
from llm import LLMClient
from tools import ToolRegistry, create_default_registry
from context import build_system_prompt, build_tool_descriptions


class AgentLoop:
    """Main agent execution loop.
    
    Pattern: receives a prompt → ReAct loop (LLM call → tool execution → repeat) → return result.
    Modeled after nanobot's AgentRunner.run() and claw-code's ConversationRuntime.run_turn().
    """

    def __init__(
        self,
        agent_id: str = "unknown",
        agent_name: str = "Agent",
        tools: ToolRegistry | None = None,
        llm: LLMClient | None = None,
        max_iterations: int = 20,
        workspace: str = "",
    ):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.tools = tools or create_default_registry()
        self.llm = llm or LLMClient()
        self.max_iterations = max_iterations
        self.workspace = workspace

    def run(self, prompt: str) -> dict:
        """Execute a task prompt and return the result."""
        # Build tool descriptions for system prompt
        tool_defs = self.tools.get_definitions()
        tool_desc = build_tool_descriptions(tool_defs)

        system_prompt = build_system_prompt(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            tool_descriptions=tool_desc,
            workspace=self.workspace,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        iteration = 0
        final_content = ""

        while iteration < self.max_iterations:
            iteration += 1

            # Step 1: Call LLM
            response = self.llm.chat(
                messages=messages,
                tools=tool_defs if tool_defs else None,
            )

            content = response.get("content", "") or ""
            tool_calls = response.get("tool_calls", []) or []

            # Step 2: Handle tool calls
            if tool_calls:
                # Add assistant message with tool calls
                assistant_msg = {"role": "assistant", "content": content}
                if tool_calls:
                    assistant_msg["tool_calls"] = [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json_dumps(tc.get("arguments", {})),
                            },
                        }
                        for tc in tool_calls
                    ]
                messages.append(assistant_msg)

                # Execute each tool
                for tc in tool_calls:
                    result = self.tools.execute(tc["name"], tc.get("arguments", {}))
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    })

                # Continue loop to feed tool results back to LLM
                continue

            # Step 3: No tool calls — final response
            final_content = content
            messages.append({"role": "assistant", "content": content})
            break

        return {
            "content": final_content,
            "iterations": iteration,
        }


def json_dumps(obj: dict) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)
```

- [ ] **Step 2: Test import**

```powershell
python -c "from agent_loop import AgentLoop; print('import ok')"
```

- [ ] **Step 3: Commit**

```bash
git add py-agent/agent_loop.py
git commit -m "feat: add ReAct agent loop"
```

---

### Task 5: Sub-agent tool + update agent_runtime.py

**Files:**
- Modify: `py-agent/tools.py`
- Modify: `py-agent/agent_runtime.py`

- [ ] **Step 1: Add SubAgentTool to tools.py**

Append after GrepSearchTool class:

```python
class SubAgentTool(Tool):
    """Spawn a child agent process to handle a subtask (claw-code Agent tool pattern)."""
    name = "sub_agent"
    description = "Spawn a child agent to handle a subtask. Provide a clear prompt describing what the subtask should accomplish."
    parameters = {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "Clear instructions for the subtask"},
            "name": {"type": "string", "description": "Optional name for the sub-agent"},
        },
        "required": ["prompt"],
    }

    def __init__(self, agent_runtime_path: str = ""):
        super().__init__()
        self.agent_runtime_path = agent_runtime_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "agent_runtime.py"
        )

    def execute(self, prompt="", name="subtask", **kwargs) -> str:
        """Spawn a new Python process running agent_runtime.py with the subtask."""
        try:
            result = subprocess.run(
                ["python", "-u", self.agent_runtime_path, "--id", name, "--name", name],
                input=json.dumps({
                    "jsonrpc": "2.0",
                    "method": "task",
                    "params": {"prompt": prompt},
                    "id": 1,
                }),
                capture_output=True,
                text=True,
                timeout=120,
            )
            # Parse the response
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if line:
                    try:
                        resp = json.loads(line)
                        if resp.get("result"):
                            return json.dumps(resp["result"], indent=2, ensure_ascii=False)
                    except json.JSONDecodeError:
                        continue
            # Fallback: return raw output
            return result.stdout or "(no output)"
        except subprocess.TimeoutExpired:
            return "Error: sub-agent task timed out after 120s"
        except Exception as e:
            return f"Error spawning sub-agent: {e}"
```

Update `create_default_registry` to accept and pass SubAgentTool:

```python
def create_default_registry(agent_runtime_path: str = "") -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(ExecCommandTool())
    registry.register(GlobSearchTool())
    registry.register(GrepSearchTool())
    registry.register(SubAgentTool(agent_runtime_path=agent_runtime_path))
    return registry
```

- [ ] **Step 2: Rewrite agent_runtime.py**

Replace the entire file. This version:
- Accepts `--id` and `--name` CLI args (from Task 2 of multi-agent plan)
- Handles `ping`, `echo`, `identify` (existing)
- Handles `task` method: runs the AgentLoop with the prompt
- Everything flows through the same stdin/stdout JSON-RPC loop

```python
"""CocoCat Agent Runtime — capable agent with LLM + tools + sub-agents."""
import sys
import json
import os

# Insert py-agent directory into path so imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

IDENTITY = {"id": None, "name": "unknown"}


def handle_request(request: dict, agent_loop=None) -> dict:
    method = request.get("method", "")
    params = request.get("params", {})

    if method == "ping":
        return {"pong": True, "agent": "cococat-capable"}
    elif method == "echo":
        return params
    elif method == "identify":
        return dict(IDENTITY)
    elif method == "task":
        if agent_loop is None:
            return {"error": "agent loop not initialized"}
        prompt = params.get("prompt", "")
        if not prompt:
            return {"error": "no prompt provided"}
        result = agent_loop.run(prompt)
        return result
    else:
        raise ValueError(f"Method not found: {method}")


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--id", default=None)
    parser.add_argument("--name", default="unknown")
    args, _ = parser.parse_known_args()
    if args.id:
        IDENTITY["id"] = args.id
        IDENTITY["name"] = args.name

    # Initialize agent loop (lazy — first task request triggers it)
    agent_loop = None

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        req_id = None
        try:
            request = json.loads(line)
            req_id = request.get("id")

            # Lazy init agent loop on first task request
            if request.get("method") == "task" and agent_loop is None:
                from agent_loop import AgentLoop
                from tools import create_default_registry

                script_dir = os.path.dirname(os.path.abspath(__file__))
                agent_runtime_path = os.path.join(script_dir, "agent_runtime.py")
                tools = create_default_registry(agent_runtime_path=agent_runtime_path)
                agent_loop = AgentLoop(
                    agent_id=IDENTITY["id"] or "unknown",
                    agent_name=IDENTITY["name"] or "Agent",
                    tools=tools,
                )

            result = handle_request(request, agent_loop=agent_loop)
            response = {"jsonrpc": "2.0", "result": result, "id": req_id}
        except json.JSONDecodeError as e:
            response = {
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": f"Parse error: {e}"},
                "id": None,
            }
        except Exception as e:
            response = {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(e)},
                "id": req_id,
            }

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Test manually**

```powershell
# Test task method
$body = '{"jsonrpc":"2.0","method":"task","params":{"prompt":"say hello and nothing else"},"id":1}'
$body | python -u py-agent/agent_runtime.py --id worker1 --name Worker1
```

**Note:** This will fail if OPENAI_API_KEY is not set. Set it first:
```powershell
$env:OPENAI_API_KEY = "your-key-here"
```

- [ ] **Step 4: Commit**

```bash
git add py-agent/tools.py py-agent/agent_runtime.py
git commit -m "feat: add sub_agent tool and task routing to agent_runtime"
```

---

### Task 6: Rust side — send tasks to agents

**Files:**
- Modify: `src/main.rs`

- [ ] **Step 1: Update main.rs to send a "task" instead of just ping**

```rust
mod transport;
mod agent_manager;
mod agent_registry;

use agent_registry::AgentRegistry;
use serde_json::json;

fn main() {
    println!("CocoCat Core starting...\n");

    let configs = AgentRegistry::load_config("agents/config.toml")
        .expect("failed to load agent config");
    println!("Loaded {} agent definitions\n", configs.len());

    for cfg in &configs {
        let status = if cfg.enabled { "enabled" } else { "disabled" };
        println!("  [{status}] {} ({})", cfg.name, cfg.id);
    }
    println!();

    let mut registry = AgentRegistry::new(configs);
    match registry.start_all() {
        Ok(()) => {}
        Err(e) => eprintln!("Warning: some agents failed to spawn: {e}"),
    }

    let statuses = registry.status();
    let running_count = statuses.iter().filter(|s| s.running).count();
    println!("Spawned {running_count} agents\n");

    // Ping each agent
    for cfg in registry.configs.clone() {
        if !cfg.enabled {
            continue;
        }
        let Some(agent) = registry.get(&cfg.id) else {
            println!("  ⚠️  {}: not running", cfg.name);
            continue;
        };
        let response = match agent.call("ping", None, 1) {
            Ok(r) => r,
            Err(e) => {
                println!("  ❌ {}: ping failed — {e}", cfg.name);
                continue;
            }
        };
        let is_ok = response
            .result
            .map(|r| r.get("pong") == Some(&serde_json::json!(true)))
            .unwrap_or(false);
        let mark = if is_ok { "✅" } else { "❌" };
        println!("  {mark} {} ({})", cfg.name, cfg.id);
    }
    println!();

    // Send a task to the first available agent
    if let Some(cfg) = registry.configs.iter().find(|c| c.enabled) {
        let agent = registry.get(&cfg.id).expect("agent should be running");

        println!("Sending task to {} ({})...\n", cfg.name, cfg.id);

        let task_params = json!({
            "prompt": "Tell me your identity and what tools you have available. Keep response under 100 words."
        });

        let response = match agent.call("task", Some(task_params), 2) {
            Ok(r) => r,
            Err(e) => {
                eprintln!("Task failed: {e}");
                return;
            }
        };

        if let Some(result) = response.result {
            let content = result.get("content").and_then(|c| c.as_str()).unwrap_or("?");
            let iterations = result.get("iterations").and_then(|i| i.as_u64()).unwrap_or(0);
            println!("=== Agent Response ===");
            println!("{content}");
            println!("\n(completed in {iterations} iteration(s))");
        }
    }

    println!("\nCocoCat Core exiting.");
}
```

- [ ] **Step 2: Build and run**

```powershell
$env:OPENAI_API_KEY = "your-key-here"
cargo run
```

Expected: Agent receives task, processes it via LLM, returns identity and tool list.

- [ ] **Step 3: Commit**

```bash
git add src/main.rs
git commit -m "feat: send tasks to agents via Rust core"
```

---

## Summary

After this phase:
- ✅ Python agent has LLM client (OpenAI API)
- ✅ Python agent has tool system (read_file, write_file, exec_command, glob, grep)
- ✅ Python agent has ReAct agent loop (nanobot/claw-code pattern)
- ✅ Python agent can spawn sub-agents (claw-code Agent tool pattern)
- ✅ Rust core can send "task" requests to agents
- ✅ Agents respond with results

**Architecture after this phase:**
```
Rust Core ──JSON-RPC──► Python Agent Process
                            │
                            ├── LLM Client (OpenAI)
                            ├── Tool Registry
                            │   ├── read_file
                            │   ├── write_file
                            │   ├── exec_command
                            │   ├── glob_search
                            │   ├── grep_search
                            │   └── sub_agent ──spawns──► Child Python Agent
                            └── AgentLoop (ReAct: think → act → observe)
```
