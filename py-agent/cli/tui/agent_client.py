"""Agent subprocess client — spawns agent_runtime, reads event lines."""
import json
import subprocess
from pathlib import Path

RUNTIME_PATH = Path(__file__).resolve().parent.parent.parent / "agent_runtime.py"


class AgentClient:
    """Manages a subprocess running agent_runtime.py with streaming events.

    Yields event dicts parsed from stdout:
      {"event": "progress", "content": "..."}
      {"event": "delta", "content": "..."}
      {"event": "done", "content": "..."}
      {"event": "tool_start", "tool": "...", "args": "..."}
      {"event": "tool_done", "tool": "...", "result": "..."}
      {"event": "reasoning", "content": "..."}
    """

    def __init__(self):
        self._proc: subprocess.Popen | None = None

    def send(self, agent_id: str, prompt: str, timeout: int = 120):
        """Send a task_stream request and yield events as they arrive."""
        proc = subprocess.Popen(
            ["python3", "-u", str(RUNTIME_PATH), "--id", agent_id, "--name", agent_id],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._proc = proc

        request = json.dumps({
            "jsonrpc": "2.0", "method": "task_stream",
            "params": {"prompt": prompt}, "id": 1,
        })
        proc.stdin.write(request + "\n")
        proc.stdin.flush()

        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            yield data
            if data.get("event") == "done":
                break

        proc.stdin.close()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    def close(self):
        if self._proc:
            self._proc.kill()
            self._proc = None
