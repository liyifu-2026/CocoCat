"""MCP Server — exposes CocoCat tools via Model Context Protocol.

Usage:
  python py-agent/mcp_server.py          # stdio mode (for Claude Desktop)
  python py-agent/mcp_server.py --port 8080  # HTTP SSE mode
"""
import sys, os, json, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path
from sandbox import CommandValidator, PathValidator, OutputTruncator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = os.environ.get("COCOCAT_WORKSPACE", str(PROJECT_ROOT))


def _read_file(path: str, offset: int = 1, limit: int = 2000) -> str:
    """Read a text file."""
    pv = PathValidator()
    is_safe, reason = pv.validate(path, Path(WORKSPACE))
    if not is_safe:
        return f"Error: {reason}"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        start = max(0, offset - 1)
        end = min(len(lines), start + limit)
        return "".join(lines[start:end])
    except Exception as e:
        return f"Error: {e}"


def _write_file(path: str, content: str) -> str:
    """Write content to a file."""
    pv = PathValidator()
    is_safe, reason = pv.validate(path, Path(WORKSPACE))
    if not is_safe:
        return f"Error: {reason}"
    from sandbox import atomic_write
    try:
        atomic_write(path, content)
        return f"Successfully wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"


def _exec_command(command: str, timeout: int = 30) -> str:
    """Execute a shell command with sandbox protection."""
    import subprocess
    validator = CommandValidator()
    is_safe, reason = validator.validate(command, "FULL_ACCESS")
    if not is_safe:
        return f"Error: Command rejected - {reason}"
    from sandbox import EnvironmentSanitizer
    sanitizer = EnvironmentSanitizer()
    clean_env = sanitizer.sanitize(os.environ.copy())
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True,
                                timeout=timeout, env=clean_env, cwd=WORKSPACE)
        output = OutputTruncator().truncate(result.stdout or "")
        if result.stderr:
            output += f"\n[stderr]\n{OutputTruncator().truncate(result.stderr)}"
        return output.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: command timed out"
    except Exception as e:
        return f"Error: {e}"


def _glob_search(pattern: str, path: str = ".") -> str:
    """Search for files matching a glob pattern."""
    import glob as glob_module
    pv = PathValidator()
    if path and path != ".":
        is_safe, reason = pv.validate(path, Path(WORKSPACE))
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
        return f"Error: {e}"


def _grep_search(pattern: str, include: str = "*", path: str = ".") -> str:
    """Search file contents using a regex pattern."""
    import re
    pv = PathValidator()
    if path and path != ".":
        is_safe, reason = pv.validate(path, Path(WORKSPACE))
        if not is_safe:
            return f"Error: {reason}"
    try:
        matches = []
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d != ".git"]
            for f in files:
                if not __import__("glob").fnmatch.fnmatch(f, include):
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
        return result
    except Exception as e:
        return f"Error: {e}"


def _web_fetch(url: str, max_chars: int = 5000) -> str:
    """Fetch content from a URL."""
    import urllib.request, re
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CocoCat-MCP/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8", errors="replace")
            text = re.sub(r'<[^>]+>', '', content)
            text = re.sub(r'\s+', ' ', text).strip()
            if len(text) > max_chars:
                text = text[:max_chars] + f"\n...[truncated {len(text) - max_chars} chars]"
            return text
    except Exception as e:
        return f"Error: {e}"


MCP_TOOLS = [
    {
        "name": "read_file",
        "description": "Read a text file from the workspace",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to workspace"},
                "offset": {"type": "integer", "description": "Starting line (1-based, default 1)"},
                "limit": {"type": "integer", "description": "Max lines to read (default 2000)"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file in the workspace",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to workspace"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "exec_command",
        "description": "Execute a shell command in the workspace (with sandbox protection)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "glob_search",
        "description": "Search for files matching a glob pattern",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (e.g. **/*.py)"},
                "path": {"type": "string", "description": "Root directory (default .)"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "grep_search",
        "description": "Search file contents using a regex pattern",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search for"},
                "include": {"type": "string", "description": "File glob filter (e.g. *.py)"},
                "path": {"type": "string", "description": "Root directory (default .)"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "web_fetch",
        "description": "Fetch content from a URL",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"},
                "max_chars": {"type": "integer", "description": "Max characters (default 5000)"},
            },
            "required": ["url"],
        },
    },
]


def run_stdio():
    """Run MCP server in stdio mode (for Claude Desktop)."""
    import sys

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            msg_id = msg.get("id")
            method = msg.get("method")
            params = msg.get("params", {})

            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "cococat-mcp", "version": "1.0.0"},
                    },
                }
            elif method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"tools": MCP_TOOLS},
                }
            elif method == "tools/call":
                tool_name = params.get("name", "")
                arguments = params.get("arguments", {})

                handlers = {
                    "read_file": lambda: _read_file(**arguments),
                    "write_file": lambda: _write_file(**arguments),
                    "exec_command": lambda: _exec_command(**arguments),
                    "glob_search": lambda: _glob_search(**arguments),
                    "grep_search": lambda: _grep_search(**arguments),
                    "web_fetch": lambda: _web_fetch(**arguments),
                }

                handler = handlers.get(tool_name)
                if handler:
                    result = handler()
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [{"type": "text", "text": result}],
                        },
                    }
                else:
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
                    }
            elif method == "notifications/initialized":
                continue
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }

            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()

        except json.JSONDecodeError:
            continue
        except Exception as e:
            error_resp = {
                "jsonrpc": "2.0",
                "id": msg.get("id"),
                "error": {"code": -32603, "message": str(e)},
            }
            sys.stdout.write(json.dumps(error_resp) + "\n")
            sys.stdout.flush()


def run_http(port: int):
    """Run MCP server in HTTP SSE mode."""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import urllib.parse

    class MCPHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/sse":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(f"data: {json.dumps({'endpoint': '/messages'})}\n\n".encode())
                while True:
                    try:
                        self.wfile.write(b": keepalive\n\n")
                        import time
                        time.sleep(15)
                    except BrokenPipeError:
                        break
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            if self.path == "/messages":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode()
                self.send_response(202)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

        def log_message(self, format, *args):
            pass

    server = HTTPServer(("0.0.0.0", port), MCPHandler)
    print(f"[MCP Server] HTTP SSE mode on port {port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[MCP Server] Shutting down...")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CocoCat MCP Server")
    parser.add_argument("--port", type=int, default=0, help="HTTP SSE port (default: stdio mode)")
    args = parser.parse_args()

    if args.port:
        run_http(args.port)
    else:
        run_stdio()
