# Agent Mailbox System Plan

**Goal:** Agents can send messages to each other's mailboxes. Heartbeat checks mailbox and processes incoming messages.

**Architecture:** Each agent has an inbox (JSONL). `send_message` tool writes to target's inbox. Heartbeat reads inbox and processes pending messages.

---

### Task 1: Mailbox module + send_message tool

**Files:**
- Create: `py-agent/mailbox.py`
- Modify: `py-agent/tools.py`

- [ ] **Step 1: Create mailbox.py**

```python
"""Agent mailbox system — inbox/outbox for inter-agent messaging."""
import os
import json
from datetime import datetime


def _mailbox_dir(agent_id: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agents", "mailbox", agent_id)


def send_message(to_agent: str, from_agent: str, content: str) -> str:
    dir_path = _mailbox_dir(to_agent)
    os.makedirs(dir_path, exist_ok=True)
    inbox_path = os.path.join(dir_path, "inbox.jsonl")
    entry = {
        "from": from_agent,
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "status": "unread",
    }
    with open(inbox_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return f"Message sent to {to_agent}"


def read_inbox(agent_id: str) -> list[dict]:
    inbox_path = os.path.join(_mailbox_dir(agent_id), "inbox.jsonl")
    if not os.path.exists(inbox_path):
        return []
    messages = []
    with open(inbox_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return messages


def mark_read(agent_id: str, idx: int):
    messages = read_inbox(agent_id)
    if 0 <= idx < len(messages):
        messages[idx]["status"] = "read"
    inbox_path = os.path.join(_mailbox_dir(agent_id), "inbox.jsonl")
    with open(inbox_path, "w", encoding="utf-8") as f:
        for m in messages:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
```

- [ ] **Step 2: Add SendMessageTool**

```python
class SendMessageTool(Tool):
    """Send a message to another agent's mailbox."""
    name = "send_message"
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
```

- [ ] **Step 3: Register + agent_id wiring**

Change `create_default_registry` to pass `agent_id` to `SendMessageTool`:

```python
    registry.register(SendMessageTool(agent_id=agent_id))
```

- [ ] **Step 4: Wire mailbox check into heartbeat**

In `heartbeat.py`'s `_heartbeat_loop`, add before checking schedule:

```python
            # Check mailbox
            try:
                from mailbox import read_inbox, mark_read
                messages = read_inbox(agent_id)
                unread = [m for m in messages if m.get("status") == "unread"]
                if unread:
                    print(f"[Mailbox] {agent_name} has {len(unread)} unread message(s)")
                    for i, msg in enumerate(messages):
                        if msg.get("status") == "unread":
                            # Execute the message as a task
                            from_prompt = f"[Message from {msg.get('from', 'unknown')}]\n{msg.get('content', '')}"
                            _execute_task(agent_id, agent_name, {"id": i, "task": from_prompt})
                            mark_read(agent_id, i)
            except Exception as e:
                print(f"[Mailbox] Error: {e}")
```

- [ ] **Step 5: Test**

```powershell
python -c "import sys; sys.path.insert(0,'py-agent'); from mailbox import send_message, read_inbox; import tempfile; import os; os.chdir(tempfile.mkdtemp()); send_message('employee_a','leader','hello'); msgs=read_inbox('employee_a'); print('mailbox ok:', len(msgs), 'messages')"
```

```bash
cargo build
python -m pytest tests/ -v
```

- [ ] **Step 6: Commit**

```bash
git add py-agent/mailbox.py py-agent/tools.py py-agent/heartbeat.py
git commit -m "feat: add agent mailbox system with send_message tool"
```
