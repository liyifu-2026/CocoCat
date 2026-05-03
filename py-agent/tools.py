"""Tool definitions and ToolRegistry (nanobot + claw-code patterns)."""
import json
import subprocess
import os
import glob as glob_module
import re
from pathlib import Path
from enum import Enum


class PermissionMode(Enum):
    READONLY = "readonly"
    WORKSPACE_WRITE = "write"
    FULL_ACCESS = "full"

    def __le__(self, other):
        order = [PermissionMode.READONLY, PermissionMode.WORKSPACE_WRITE, PermissionMode.FULL_ACCESS]
        return order.index(self) <= order.index(other)


class Tool:
    """Base tool class (nanobot Tool pattern)."""
    name: str = ""
    description: str = ""
    parameters: dict = {}
    required_permission: PermissionMode = PermissionMode.FULL_ACCESS

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
    required_permission = PermissionMode.READONLY
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
        from sandbox import PathValidator
        PROJECT_ROOT = Path(__file__).resolve().parent.parent
        pv = PathValidator()
        is_safe, reason = pv.validate(path, PROJECT_ROOT)
        if not is_safe:
            return f"Error: {reason}"
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
    required_permission = PermissionMode.WORKSPACE_WRITE
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
        from sandbox import PathValidator
        PROJECT_ROOT = Path(__file__).resolve().parent.parent
        pv = PathValidator()
        is_safe, reason = pv.validate(path, PROJECT_ROOT)
        if not is_safe:
            return f"Error: {reason}"
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote {len(content)} bytes to {path}"
        except Exception as e:
            return f"Error writing file: {e}"


class ExecCommandTool(Tool):
    name = "exec_command"
    required_permission = PermissionMode.FULL_ACCESS
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
        from sandbox import CommandValidator, EnvironmentSanitizer, OutputTruncator

        validator = CommandValidator()
        is_safe, reason = validator.validate(command, self.required_permission)
        if not is_safe:
            return f"Error: Command rejected - {reason}"

        sanitizer = EnvironmentSanitizer()
        clean_env = sanitizer.sanitize(os.environ.copy())

        from sandbox import wrap_with_namespace
        command = wrap_with_namespace(command)

        PROJECT_ROOT = Path(__file__).resolve().parent.parent

        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=timeout, env=clean_env, cwd=PROJECT_ROOT,
            )
            output = OutputTruncator().truncate(result.stdout or "")
            if result.stderr:
                output += f"\n[stderr]\n{OutputTruncator().truncate(result.stderr)}"
            if result.returncode != 0:
                output += f"\n[exit code: {result.returncode}]"
            return output.strip() or "(no output)"
        except subprocess.TimeoutExpired:
            return f"Error: command timed out after {timeout}s"
        except Exception as e:
            return f"Error executing command: {e}"


class GlobSearchTool(Tool):
    name = "glob_search"
    required_permission = PermissionMode.READONLY
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
        if path and path != ".":
            from sandbox import PathValidator
            PROJECT_ROOT = Path(__file__).resolve().parent.parent
            pv = PathValidator()
            is_safe, reason = pv.validate(path, PROJECT_ROOT)
            if not is_safe:
                return f"Error: {reason}"
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
    required_permission = PermissionMode.READONLY
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
        if path and path != ".":
            from sandbox import PathValidator
            PROJECT_ROOT = Path(__file__).resolve().parent.parent
            pv = PathValidator()
            is_safe, reason = pv.validate(path, PROJECT_ROOT)
            if not is_safe:
                return f"Error: {reason}"
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


class SubAgentTool(Tool):
    """Spawn a child agent process to handle a subtask (claw-code Agent tool pattern)."""
    name = "sub_agent"
    required_permission = PermissionMode.FULL_ACCESS
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
            input_json = json.dumps({
                "jsonrpc": "2.0",
                "method": "task",
                "params": {"prompt": prompt},
                "id": 1,
            })
            result = subprocess.run(
                ["python", "-u", self.agent_runtime_path, "--id", name, "--name", name],
                input=input_json,
                capture_output=True,
                text=True,
                timeout=120,
            )
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    resp = json.loads(line)
                    if resp.get("result"):
                        return json.dumps(resp["result"], indent=2, ensure_ascii=False)
                    if resp.get("error"):
                        err = resp["error"]
                        return f"Sub-agent error [{err.get('code', '?')}]: {err.get('message', 'unknown')}"
                except json.JSONDecodeError:
                    continue
            return result.stdout.strip() or "(no output)"
        except subprocess.TimeoutExpired:
            return "Error: sub-agent task timed out after 120s"
        except Exception as e:
            return f"Error spawning sub-agent: {e}"


class DispatchTaskTool(Tool):
    """Request dispatching a task to another agent via Rust core proxy."""
    name = "dispatch_task"
    required_permission = PermissionMode.FULL_ACCESS
    description = "Send a task to another agent in the team. The target agent will process the task and the result will be returned to you."
    parameters = {
        "type": "object",
        "properties": {
            "target_id": {"type": "string", "description": "ID of the target agent (e.g. employee_a)"},
            "prompt": {"type": "string", "description": "The task prompt to send to the target agent"},
        },
        "required": ["target_id", "prompt"],
    }

    def execute(self, target_id="", prompt="", **kwargs) -> str:
        """Write a dispatch request file that Rust will read and forward."""
        import os
        import time
        from datetime import datetime
        script_dir = os.path.dirname(os.path.abspath(__file__))
        queue_dir = os.path.join(script_dir, "..", "agents", "dispatch_queue")
        os.makedirs(queue_dir, exist_ok=True)

        dispatch = {
            "__dispatch__": True,
            "target_id": target_id,
            "method": "task",
            "params": {"prompt": prompt},
            "timestamp": datetime.now().isoformat(),
        }

        filename = f"dispatch_{target_id}_{time.time_ns()}.json"
        filepath = os.path.join(queue_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(dispatch, f, ensure_ascii=False)

        return f"Dispatch request queued for '{target_id}'. Message: '{prompt[:80]}...'"


class HireAgentTool(Tool):
    """Request hiring a new agent. Creates a hire request file for the next restart."""
    name = "hire_agent"
    required_permission = PermissionMode.FULL_ACCESS
    description = "Request hiring a new team member. Specify id, name, role, and optional profile fields."
    parameters = {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "Unique ID for the new agent (e.g. employee_c)"},
            "name": {"type": "string", "description": "Display name for the new agent (e.g. 员工C)"},
            "role": {"type": "string", "description": "Role title for the agent (e.g. 资深工程师)"},
            "objective": {"type": "string", "description": "Primary objective for the agent"},
            "traits": {"type": "array", "items": {"type": "string"}, "description": "Personality traits"},
            "background": {"type": "string", "description": "Background description"},
            "rules": {"type": "array", "items": {"type": "string"}, "description": "Behavior rules"},
        },
        "required": ["id", "name", "role"],
    }

    def execute(self, id="", name="", role="", objective="", traits=None, background="", rules=None, **kwargs) -> str:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        hire_dir = os.path.join(script_dir, "..", "agents", "hire_requests", "pending")
        os.makedirs(hire_dir, exist_ok=True)
        if traits is None:
            traits = []
        if rules is None:
            rules = []
        request = {
            "id": id,
            "name": name,
            "scene": "development",
            "profile": {
                "role": role,
                "objective": objective,
                "traits": traits,
                "background": background,
                "rules": rules,
            },
            "status": "pending",
        }
        filepath = os.path.join(hire_dir, f"{id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(request, f, ensure_ascii=False, indent=2)
        return f"Hire request created for '{name}' ({id}). Waiting for admin confirmation."


class SearchKbTool(Tool):
    """Search the knowledge bases mounted to your current scene."""
    name = "search_kb"
    required_permission = PermissionMode.READONLY
    description = "Search knowledge bases mounted to your current scene. Returns matching content from KB wiki pages."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query (keywords or phrase)"},
            "max_results": {"type": "integer", "description": "Maximum results to return (default 5)"},
        },
        "required": ["query"],
    }

    def __init__(self, scene_id: str = "default"):
        super().__init__()
        self.scene_id = scene_id

    def execute(self, query="", max_results=5, **kwargs) -> str:
        import os as _os
        import re as _re

        script_dir = _os.path.dirname(_os.path.abspath(__file__))
        mount_path = _os.path.join(script_dir, "..", "scenes", self.scene_id, "mounted_kbs.json")

        if not _os.path.exists(mount_path):
            return "No knowledge bases mounted for this scene."

        try:
            with open(mount_path, "r", encoding="utf-8") as f:
                mount_data = json.load(f)
        except Exception as e:
            return f"Failed to load mounted KBs: {e}"

        mounted = mount_data.get("mounted", [])
        if not mounted:
            return "No knowledge bases mounted for this scene."

        kb_base = _os.path.join(script_dir, "..", "knowledge")
        results = []

        for kb_id in mounted:
            wiki_dir = _os.path.join(kb_base, kb_id, "wiki")
            if not _os.path.isdir(wiki_dir):
                continue

            for root, dirs, files in _os.walk(wiki_dir):
                for f in files:
                    if not f.endswith(".md"):
                        continue
                    fp = _os.path.join(root, f)
                    try:
                        with open(fp, "r", encoding="utf-8", errors="replace") as fh:
                            content = fh.read()
                    except Exception:
                        continue

                    query_lower = query.lower()
                    if query_lower in content.lower():
                        lines = content.split("\n")
                        matched_lines = []
                        for i, line in enumerate(lines):
                            if query_lower in line.lower():
                                start = max(0, i - 1)
                                end = min(len(lines), i + 3)
                                snippet = "\n".join(lines[start:end])
                                rel_path = _os.path.relpath(fp, kb_base)
                                matched_lines.append(f"[{rel_path}:{i+1}]\n{snippet}")
                        if matched_lines:
                            results.extend(matched_lines)

        if not results:
            return f"No matches found for '{query}' in mounted KBs."

        seen = set()
        unique = []
        for r in results:
            if r not in seen:
                seen.add(r)
                unique.append(r)

        top = unique[:max_results]
        output = f"Found {len(unique)} matches (showing {len(top)}):\n\n"
        output += "\n\n---\n\n".join(top)
        return output


class RememberTool(Tool):
    """Store a fact into long-term memory."""
    name = "remember"
    required_permission = PermissionMode.WORKSPACE_WRITE
    description = "Store a fact into long-term memory"
    parameters = {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Fact to remember"},
            "user_id": {"type": "string", "description": "Optional: associate with specific user (default: global memory)"},
        },
        "required": ["content"],
    }

    def execute(self, agent_id: str = "", content: str = "", user_id: str = "", **kwargs) -> dict:
        from dream import get_user_memory_dir, _user_hash, _agent_memory_dir
        if user_id:
            user_hash = _user_hash(user_id)
            profile_path = os.path.join(get_user_memory_dir(agent_id, user_hash), "PROFILE.md")
            os.makedirs(os.path.dirname(profile_path), exist_ok=True)
            with open(profile_path, "a", encoding="utf-8") as f:
                f.write(f"- {content}\n")
            return {"success": True, "location": f"users/{user_hash}/PROFILE.md"}
        else:
            mem_path = os.path.join(_agent_memory_dir(agent_id), "MEMORY.md")
            os.makedirs(os.path.dirname(mem_path), exist_ok=True)
            with open(mem_path, "a", encoding="utf-8") as f:
                f.write(f"- {content}\n")
            return {"success": True, "location": "MEMORY.md"}


class RecallTool(Tool):
    """Retrieve facts from long-term memory."""
    name = "recall"
    required_permission = PermissionMode.READONLY
    description = "Retrieve facts from long-term memory"
    parameters = {
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "Optional keyword filter"},
            "user_id": {"type": "string", "description": "Optional: search user-specific memory (default: global only)"},
        },
    }

    def execute(self, agent_id: str = "", keyword: str = "", user_id: str = "", **kwargs) -> dict:
        from dream import _user_hash, get_user_memory_dir, _agent_memory_dir
        results = []
        mem_path = os.path.join(_agent_memory_dir(agent_id), "MEMORY.md")
        if os.path.exists(mem_path):
            with open(mem_path) as f:
                content = f.read()
                if not keyword or keyword.lower() in content.lower():
                    results.append({"source": "MEMORY.md", "content": content})
        if user_id:
            user_hash = _user_hash(user_id)
            profile_path = os.path.join(get_user_memory_dir(agent_id, user_hash), "PROFILE.md")
            if os.path.exists(profile_path):
                with open(profile_path) as f:
                    content = f.read()
                    if not keyword or keyword.lower() in content.lower():
                        results.append({"source": f"users/{user_hash}/PROFILE.md", "content": content})
        return {"success": True, "results": results}


class RevertMemoryTool(Tool):
    """Revert the last Dream commit to undo bad memory changes."""
    name = "revert_memory"
    required_permission = PermissionMode.WORKSPACE_WRITE
    description = "Revert the last Dream commit to undo bad memory changes"
    parameters = {"type": "object", "properties": {}}

    def execute(self, agent_id: str = "", **kwargs) -> dict:
        from git_store import GitStore
        from dream import _agent_memory_dir
        mem_dir = _agent_memory_dir(agent_id)
        store = GitStore(mem_dir)
        last_msg = store.last_commit_message()
        ok = store.revert()
        if ok:
            return {"success": True, "reverted": last_msg}
        return {"success": False, "error": "No previous commit to revert to"}


class DreamTool(Tool):
    """Run the Dream process: analyze recent history and consolidate into MEMORY.md."""
    name = "dream"
    required_permission = PermissionMode.WORKSPACE_WRITE
    description = "Process recent history and consolidate important findings into long-term memory. The LLM will analyze your task history and extract key facts, decisions, and patterns."
    parameters = {
        "type": "object",
        "properties": {
            "scope": {"type": "string", "description": "What to focus on: recent, all"},
        },
    }

    def __init__(self, agent_id: str = "", agent_name: str = "Agent"):
        super().__init__()
        self.agent_id = agent_id
        self.agent_name = agent_name

    def execute(self, scope="recent", **kwargs) -> str:
        """Trigger the real Dream process."""
        from dream import run_dream
        try:
            result = run_dream(self.agent_id, self.agent_name)
            return result
        except Exception as e:
            return f"Dream failed: {e}"


class IngestToKbTool(Tool):
    """Ingest a raw source file into a knowledge base. Two-stage LLM pipeline: analyze then generate wiki pages."""
    name = "ingest_to_kb"
    required_permission = PermissionMode.WORKSPACE_WRITE
    description = "Process a raw source file into structured wiki pages in a knowledge base. Specify kb_id and source_filename (relative to knowledge/{kb}/raw/sources/)."
    parameters = {
        "type": "object",
        "properties": {
            "kb_id": {"type": "string", "description": "Knowledge base ID (e.g. team-wiki)"},
            "source_filename": {"type": "string", "description": "Source filename in knowledge/{kb}/raw/sources/"},
        },
        "required": ["kb_id", "source_filename"],
    }

    def execute(self, kb_id="", source_filename="", **kwargs) -> str:
        from ingest import run_ingest
        try:
            result = run_ingest(kb_id, source_filename)
            return result
        except Exception as e:
            return f"Ingestion failed: {e}"


class WebFetchTool(Tool):
    """Fetch content from a URL and return as text."""
    name = "web_fetch"
    required_permission = PermissionMode.READONLY
    description = "Fetch content from a URL and return it as text. Useful for reading documentation, APIs, and web pages."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
            "max_chars": {"type": "integer", "description": "Maximum characters to return (default 5000)"},
        },
        "required": ["url"],
    }

    def execute(self, url="", max_chars=5000, **kwargs) -> str:
        import urllib.request
        import urllib.error
        import re
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CocoCat/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read().decode("utf-8", errors="replace")
                text = re.sub(r'<[^>]+>', '', content)
                text = re.sub(r'\s+', ' ', text).strip()
                if len(text) > max_chars:
                    text = text[:max_chars] + f"\n...[truncated {len(text) - max_chars} chars]"
                return text
        except urllib.error.HTTPError as e:
            return f"HTTP error {e.code}: {e.reason}"
        except urllib.error.URLError as e:
            return f"URL error: {e.reason}"
        except Exception as e:
            return f"Failed to fetch {url}: {e}"


class WebSearchTool(Tool):
    """Search the web using DuckDuckGo (no API key needed)."""
    name = "web_search"
    required_permission = PermissionMode.READONLY
    description = "Search the web for information. Returns a list of results with titles and snippets."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "max_results": {"type": "integer", "description": "Maximum results (default 5)"},
        },
        "required": ["query"],
    }

    def execute(self, query="", max_results=5, **kwargs) -> str:
        import urllib.request
        import urllib.parse
        import json
        try:
            encoded = urllib.parse.quote(query)
            url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1"
            req = urllib.request.Request(url, headers={"User-Agent": "CocoCat/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            results = []
            heading = data.get("Heading", "")
            abstract = data.get("AbstractText", "")
            if heading and abstract:
                results.append(f"## {heading}\n{abstract}\n")
            related = data.get("RelatedTopics", [])[:max_results]
            for r in related:
                if isinstance(r, dict):
                    text = r.get("Text", "")
                    url2 = r.get("FirstURL", "")
                    if text:
                        results.append(f"- {text}\n  {url2}" if url2 else f"- {text}")
            return "\n".join(results) if results else f"No results found for '{query}'."
        except Exception as e:
            return f"Search failed: {e}"


class McpCallTool(Tool):
    """Call a tool from an MCP server."""
    name = "mcp_call"
    required_permission = PermissionMode.FULL_ACCESS
    description = "Call a tool from an MCP (Model Context Protocol) server. Specify the server command, tool name, and arguments."
    parameters = {
        "type": "object",
        "properties": {
            "server_command": {"type": "string", "description": "Shell command to start the MCP server"},
            "tool_name": {"type": "string", "description": "Name of the tool to call"},
            "arguments": {"type": "object", "description": "Arguments to pass to the tool"},
        },
        "required": ["server_command", "tool_name"],
    }

    def execute(self, server_command="", tool_name="", arguments=None, **kwargs) -> str:
        import subprocess, json
        try:
            proc = subprocess.Popen(
                server_command, shell=True,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True,
            )
            init = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "cococat", "version": "1.0"}}})
            proc.stdin.write(init + "\n")
            proc.stdin.flush()
            proc.stdout.readline()

            call = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": tool_name, "arguments": arguments or {}}})
            proc.stdin.write(call + "\n")
            proc.stdin.flush()

            result_lines = []
            for line in proc.stdout:
                line = line.strip()
                if line:
                    try:
                        resp = json.loads(line)
                        content_list = resp.get("result", {}).get("content", [])
                        for c in content_list:
                            if isinstance(c, dict) and c.get("type") == "text":
                                result_lines.append(c["text"])
                        if "error" in resp:
                            result_lines.append(f"Error: {resp['error'].get('message', '')}")
                    except json.JSONDecodeError:
                        continue
                if len(result_lines) > 3:
                    break

            proc.terminate()
            return "\n".join(result_lines) if result_lines else "(no result)"
        except Exception as e:
            return f"MCP call failed: {e}"


class SendMessageTool(Tool):
    """Send a message to another agent's mailbox."""
    name = "send_message"
    required_permission = PermissionMode.FULL_ACCESS
    description = "Send a message to another agent. The target agent will receive it in their mailbox and can respond on their next heartbeat."
    parameters = {
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "Target agent ID (e.g. employee_a)"},
            "message": {"type": "string", "description": "Message content"},
        },
        "required": ["to", "message"],
    }

    def __init__(self, from_agent: str = ""):
        super().__init__()
        self.from_agent = from_agent

    def execute(self, to="", message="", **kwargs) -> str:
        from mailbox import send_message
        return send_message(to, self.from_agent, message)


class LearnSkillTool(Tool):
    """Learn a new skill."""
    name = "learn_skill"
    description = "Learn a new skill and add it to your permanent skill set."
    parameters = {
        "type": "object",
        "properties": {
            "skill_name": {"type": "string", "description": "Name of the skill to learn (e.g. code_review)"},
        },
        "required": ["skill_name"],
    }

    def __init__(self, agent_id: str = ""):
        super().__init__()
        self.agent_id = agent_id

    def execute(self, skill_name="", **kwargs) -> str:
        import os, json
        manifest_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agents", self.agent_id, "skills", "manifest.json")
        if not os.path.exists(manifest_path):
            return "No manifest found"
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        if skill_name in manifest.get("private", []):
            return f"Already knows '{skill_name}'"
        manifest.setdefault("private", []).append(skill_name)
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        return f"Learned skill '{skill_name}'"


class ForgetSkillTool(Tool):
    """Forget a skill."""
    name = "forget_skill"
    description = "Forget a skill you no longer need."
    parameters = {
        "type": "object",
        "properties": {
            "skill_name": {"type": "string", "description": "Name of the skill to forget"},
        },
        "required": ["skill_name"],
    }

    def __init__(self, agent_id: str = ""):
        super().__init__()
        self.agent_id = agent_id

    def execute(self, skill_name="", **kwargs) -> str:
        import os, json
        manifest_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agents", self.agent_id, "skills", "manifest.json")
        if not os.path.exists(manifest_path):
            return "No manifest found"
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        if skill_name not in manifest.get("private", []):
            return f"Does not know '{skill_name}'"
        manifest["private"] = [s for s in manifest["private"] if s != skill_name]
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        return f"Forgot skill '{skill_name}'"


class ListSkillsTool(Tool):
    """List all skills."""
    name = "list_skills"
    description = "List all skills you currently have (public + private)."
    parameters = {"type": "object", "properties": {}}

    def __init__(self, agent_id: str = ""):
        super().__init__()
        self.agent_id = agent_id

    def execute(self, **kwargs) -> str:
        import os, json
        manifest_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agents", self.agent_id, "skills", "manifest.json")
        if not os.path.exists(manifest_path):
            return "No manifest found"
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        public = manifest.get("public", [])
        private = manifest.get("private", [])
        lines = ["## Public Skills"]
        lines.extend(f"- {s}" for s in public)
        lines.append("\n## Private Skills")
        lines.extend(f"- {s}" for s in private) if private else lines.append("(none)")
        return "\n".join(lines)


class EditFileTool(Tool):
    """Replace text in a file using search/replace (claw-code pattern)."""
    name = "edit_file"
    required_permission = PermissionMode.WORKSPACE_WRITE
    description = "Replace text in a file. Specify old_string to find and new_string to replace it with. Use replace_all=true to replace all occurrences."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path"},
            "old_string": {"type": "string", "description": "Text to find (exact match, not regex)"},
            "new_string": {"type": "string", "description": "Text to replace with"},
            "replace_all": {"type": "boolean", "description": "Replace all occurrences (default false)"},
        },
        "required": ["path", "old_string", "new_string"],
    }

    def execute(self, path="", old_string="", new_string="", replace_all=False, **kwargs) -> str:
        from sandbox import PathValidator
        PROJECT_ROOT = Path(__file__).resolve().parent.parent
        pv = PathValidator()
        is_safe, reason = pv.validate(path, PROJECT_ROOT)
        if not is_safe:
            return f"Error: {reason}"
        import os
        path = os.path.abspath(path)
        try:
            with open(path, "r", encoding="utf-8") as f:
                original = f.read()
        except FileNotFoundError:
            return f"Error: file not found: {path}"
        except Exception as e:
            return f"Error reading file: {e}"

        if old_string == new_string:
            return "Error: old_string and new_string must differ"

        if old_string not in original:
            return f"Error: old_string not found in file"

        if replace_all:
            updated = original.replace(old_string, new_string)
        else:
            updated = original.replace(old_string, new_string, 1)

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(updated)
        except Exception as e:
            return f"Error writing file: {e}"

        return f"Applied edit to {path}"


class AskUserTool(Tool):
    """Ask the user a question and wait for response."""
    name = "ask_user"
    required_permission = PermissionMode.FULL_ACCESS
    description = "Ask the user a question and get their response. The agent pauses and waits for user input."
    parameters = {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "Question to ask the user"},
            "options": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional multiple-choice options",
            },
        },
        "required": ["question"],
    }

    def execute(self, question="", options=None, **kwargs) -> str:
        import os, json
        from datetime import datetime
        question_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agents", "_ask_user.json")
        data = {"question": question, "options": options or [], "timestamp": datetime.now().isoformat(), "status": "pending"}
        with open(question_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return f"Question saved: {question}\nWaiting for user response..."

class ToolRegistry:
    """Registry of available tools (nanobot ToolRegistry pattern)."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def get_definitions(self) -> list[dict]:
        return [t.to_openai_schema() for t in self._tools.values()]

    def execute(self, name: str, arguments: dict, current_mode: PermissionMode = PermissionMode.FULL_ACCESS) -> str:
        tool = self._tools.get(name)
        if not tool:
            return f"Error: unknown tool '{name}'"
        if not (tool.required_permission <= current_mode):
            return f"Permission denied: '{name}' requires {tool.required_permission.value}, current mode is {current_mode.value}"
        try:
            return tool.execute(**arguments)
        except Exception as e:
            return f"Error executing {name}: {e}"


def create_default_registry(agent_runtime_path: str = "", scene_id: str = "default", agent_id: str = "", agent_name: str = "Agent") -> ToolRegistry:
    """Create registry with all standard tools."""
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(ExecCommandTool())
    registry.register(GlobSearchTool())
    registry.register(GrepSearchTool())
    registry.register(SubAgentTool(agent_runtime_path=agent_runtime_path))
    registry.register(DispatchTaskTool())
    registry.register(HireAgentTool())
    registry.register(SearchKbTool(scene_id=scene_id))
    registry.register(RememberTool())
    registry.register(RecallTool())
    registry.register(RevertMemoryTool())
    registry.register(DreamTool(agent_id=agent_id, agent_name=agent_name))
    registry.register(IngestToKbTool())
    registry.register(WebFetchTool())
    registry.register(WebSearchTool())
    registry.register(EditFileTool())
    registry.register(AskUserTool())
    registry.register(McpCallTool())
    registry.register(SendMessageTool(from_agent=agent_id))
    registry.register(LearnSkillTool(agent_id=agent_id))
    registry.register(ForgetSkillTool(agent_id=agent_id))
    registry.register(ListSkillsTool(agent_id=agent_id))
    return registry
