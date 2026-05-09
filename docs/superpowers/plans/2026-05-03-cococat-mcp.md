# MCP Plugin Support Plan

**Goal:** Agents can call tools from MCP servers via a simple `mcp_call` tool.

**Architecture:** New `mcp_call` tool that spawns an MCP server process, connects via stdio, calls the specified tool, and returns the result. Uses the `mcp` Python library.

---

### Task 1: Install mcp + create McpCallTool

**Files:**
- Modify: `py-agent/tools.py`

- [ ] **Step 1: Install mcp**

```powershell
pip install mcp
```

- [ ] **Step 2: Add McpCallTool**

After `WebSearchTool`, add:

```python
class McpCallTool(Tool):
    """Call a tool from an MCP server. Spawns the server, calls the tool, returns result."""
    name = "mcp_call"
    description = "Call a tool from an MCP (Model Context Protocol) server. Specify the server command to run and the tool name with arguments."
    parameters = {
        "type": "object",
        "properties": {
            "server_command": {"type": "string", "description": "Shell command to start the MCP server (e.g. npx -y @modelcontextprotocol/server-filesystem /path)"},
            "tool_name": {"type": "string", "description": "Name of the tool to call on the MCP server"},
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
            # MCP initialize
            init = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "cococat", "version": "1.0"}}})
            proc.stdin.write(init + "\n")
            proc.stdin.flush()
            proc.stdout.readline()  # consume init response

            # Call tool
            call = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": tool_name, "arguments": arguments or {}}})
            proc.stdin.write(call + "\n")
            proc.stdin.flush()

            result_lines = []
            for line in proc.stdout:
                line = line.strip()
                if line:
                    try:
                        resp = json.loads(line)
                        if "result" in resp:
                            content = resp["result"].get("content", [])
                            for c in content:
                                if isinstance(c, dict) and c.get("type") == "text":
                                    result_lines.append(c["text"])
                        if "error" in resp:
                            result_lines.append(f"Error: {resp['error'].get('message', 'unknown')}")
                    except json.JSONDecodeError:
                        continue
                # Read up to 100 lines
                if len(result_lines) > 0 and any("content" in line for line in result_lines):
                    break

            proc.terminate()
            return "\n".join(result_lines) if result_lines else "(no result)"
        except Exception as e:
            return f"MCP call failed: {e}"
```

- [ ] **Step 3: Register**

```python
    registry.register(McpCallTool())
```

- [ ] **Step 4: Test import**

```powershell
python -c "import sys; sys.path.insert(0,'py-agent'); from tools import McpCallTool; t=McpCallTool(); print('mcp tool ok:', t.name)"
```

- [ ] **Step 5: Commit**

```bash
git add py-agent/tools.py
git commit -m "feat: add mcp_call tool for MCP server integration"
```
