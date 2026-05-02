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


def create_default_registry() -> ToolRegistry:
    """Create registry with all standard tools."""
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(ExecCommandTool())
    registry.register(GlobSearchTool())
    registry.register(GrepSearchTool())
    return registry
