import subprocess
import json
import os
import threading


class LSPClient:
    """Minimal LSP client for code intelligence."""

    def __init__(self, server_command: str, root_uri: str):
        self.root_uri = root_uri
        self._proc = subprocess.Popen(
            server_command.split(),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )
        self._req_id = 0
        self._lock = threading.Lock()
        self._initialize()

    def _send(self, method: str, params: dict | None = None) -> dict:
        self._req_id += 1
        msg = json.dumps({"jsonrpc": "2.0", "id": self._req_id, "method": method, "params": params or {}})
        header = f"Content-Length: {len(msg)}\r\n\r\n"
        with self._lock:
            self._proc.stdin.write(header + msg)
            self._proc.stdin.flush()
        return self._read_response()

    def _read_response(self) -> dict:
        content_len = 0
        while True:
            line = self._proc.stdout.readline()
            if line.startswith("Content-Length:"):
                content_len = int(line.strip().split(":")[1])
            elif line.strip() == "" and content_len > 0:
                body = self._proc.stdout.read(content_len)
                return json.loads(body)

    def _initialize(self):
        self._send("initialize", {
            "processId": os.getpid(),
            "rootUri": self.root_uri,
            "capabilities": {"textDocument": {"hover": {}, "definition": {}, "references": {}}},
        })
        self._send("initialized")

    def _open_doc(self, file_path: str, language: str):
        uri = f"file://{os.path.abspath(file_path)}"
        with open(file_path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        self._send("textDocument/didOpen", {
            "textDocument": {"uri": uri, "languageId": language, "version": 1, "text": text},
        })
        return uri

    def hover(self, file_path: str, line: int, col: int, language: str = "python") -> str:
        uri = self._open_doc(file_path, language)
        resp = self._send("textDocument/hover", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": col},
        })
        result = resp.get("result", {})
        contents = result.get("contents", {})
        if isinstance(contents, dict):
            return contents.get("value", "")
        return str(contents) if contents else "(no info)"

    def definition(self, file_path: str, line: int, col: int, language: str = "python") -> str:
        uri = self._open_doc(file_path, language)
        resp = self._send("textDocument/definition", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": col},
        })
        result = resp.get("result")
        if not result:
            return "(no definition found)"
        if isinstance(result, list):
            result = result[0]
        loc = result
        target = loc.get("targetUri", loc.get("uri", "?"))
        r = loc.get("range", {})
        start = r.get("start", {})
        return f"{target}:{start.get('line', 0)}:{start.get('character', 0)}"

    def references(self, file_path: str, line: int, col: int, language: str = "python") -> str:
        uri = self._open_doc(file_path, language)
        resp = self._send("textDocument/references", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": col},
            "context": {"includeDeclaration": True},
        })
        result = resp.get("result", [])
        if not result:
            return "(no references found)"
        lines = [f"Found {len(result)} reference(s):", ""]
        for r in result:
            uri = r.get("uri", "?")
            rg = r.get("range", {})
            start = rg.get("start", {})
            lines.append(f"  {uri}:{start.get('line', 0)}:{start.get('character', 0)}")
        return "\n".join(lines)

    def close(self):
        try:
            self._proc.terminate()
            self._proc.wait(timeout=5)
        except Exception:
            self._proc.kill()
