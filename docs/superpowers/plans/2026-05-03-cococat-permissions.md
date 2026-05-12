# Permission System Plan

**Goal:** Add tool-level permissions (claw-code pattern): ReadOnly → WorkspaceWrite → FullAccess. Agent runs in a default mode; tools exceeding it return "permission denied".

---

### Task 1: Add permission levels to tools

**Files:**
- Modify: `py-agent/tools.py`

- [ ] **Step 1: Add PermissionMode**

At the top of tools.py, add:

```python
from enum import Enum

class PermissionMode(Enum):
    READONLY = "readonly"        # read_file, glob, grep, search_kb, recall, web_fetch, web_search
    WORKSPACE_WRITE = "write"    # write_file, edit_file, exec_command, ingest_to_kb, remember
    FULL_ACCESS = "full"         # sub_agent, dispatch_task, hire_agent, send_message, dream, mcp_call

    def __le__(self, other):
        order = [PermissionMode.READONLY, PermissionMode.WORKSPACE_WRITE, PermissionMode.FULL_ACCESS]
        return order.index(self) <= order.index(other)
```

- [ ] **Step 2: Add `required_permission` to base Tool class**

```python
class Tool:
    name: str = ""
    description: str = ""
    parameters: dict = {}
    required_permission: PermissionMode = PermissionMode.FULL_ACCESS
```

- [ ] **Step 3: Set permissions on each tool**

Set `required_permission` on each tool class:

| Tool | Permission |
|------|-----------|
| ReadFileTool | READONLY |
| WriteFileTool | WORKSPACE_WRITE |
| ExecCommandTool | FULL_ACCESS |
| GlobSearchTool | READONLY |
| GrepSearchTool | READONLY |
| SubAgentTool | FULL_ACCESS |
| DispatchTaskTool | FULL_ACCESS |
| HireAgentTool | FULL_ACCESS |
| SearchKbTool | READONLY |
| RememberTool | WORKSPACE_WRITE |
| RecallTool | READONLY |
| DreamTool | WORKSPACE_WRITE |
| IngestToKbTool | WORKSPACE_WRITE |
| WebFetchTool | READONLY |
| WebSearchTool | READONLY |
| EditFileTool | WORKSPACE_WRITE |
| AskUserTool | FULL_ACCESS |
| McpCallTool | FULL_ACCESS |
| SendMessageTool | FULL_ACCESS |

- [ ] **Step 4: Add permission checking to ToolRegistry.execute()**

```python
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
```

- [ ] **Step 5: Update AgentLoop to pass permission mode**

In `agent_loop.py`, add `permission_mode` parameter to `__init__()` and pass it in `run()`:

```python
    def __init__(self, ..., permission_mode: PermissionMode = PermissionMode.FULL_ACCESS):
        ...
        self.permission_mode = permission_mode
```

In the tool execution loop, change `self.tools.execute(...)` to:
```python
    result = self.tools.execute(tc["name"], tc.get("arguments", {}), self.permission_mode)
```

- [ ] **Step 6: Test**

```bash
python -m pytest tests/ -v
```

- [ ] **Step 7: Commit**

```bash
git add py-agent/tools.py py-agent/agent_loop.py
git commit -m "feat: add permission system with ReadOnly/WorkspaceWrite/FullAccess"
```
