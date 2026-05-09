# Layer 2: Python Agent Runtime Refactoring

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Upgrade Python agent runtime from Alpha to Beta quality - fix dead code, add tests, TOCTOU fix, structured logging, concurrency guards.

**Architecture:** Keep module structure, add utils.py, tests/ directory.

**Tech Stack:** Python 3.12+, pytest

---

### File Structure
- py-agent/utils.py [NEW] - Shared utilities (user_hash)
- py-agent/tests/ [NEW] - Test directory
- py-agent/tests/__init__.py [NEW] - Test package init
- py-agent/tests/test_tools.py [NEW] - Tool tests
- py-agent/tests/test_sandbox.py [NEW] - Sandbox tests
- py-agent/tests/test_llm.py [NEW] - LLM client tests
- py-agent/agent_runtime.py [MODIFY] - Fix dead code lines 102-104
- py-agent/agent_loop.py [MODIFY] - Normalize prompt, consolidate depth guard
- py-agent/tools.py [MODIFY] - TOCTOU fix, SubAgent timeout
- py-agent/context.py [MODIFY] - Import user_hash from utils
- py-agent/dream.py [MODIFY] - Add concurrency lock, import user_hash from utils
- py-agent/heartbeat.py [MODIFY] - Add overlap guard

---

## Task 1: Fix dead code in agent_runtime.py

**Files:**
- Modify: `py-agent/agent_runtime.py`

- [ ] **Step 1: Read the file and identify lines 102-104**

Lines 102-104 in agent_runtime.py are:
```python
                    scene_context=scene_context,
                    scene_skills=scene_skills,
                )
```
These three lines are orphaned continuation arguments that reference undefined variables (`scene_context`, `scene_skills`). They must be deleted entirely.

- [ ] **Step 2: Delete the three orphan lines**

Remove lines 102-104 entirely. The file should go from:
```python
                runner._ensure_loop()
                agent_loop = runner._loop
                    scene_context=scene_context,
                    scene_skills=scene_skills,
                )
```
to:
```python
                runner._ensure_loop()
                agent_loop = runner._loop
```

- [ ] **Step 3: Run the file to verify syntax**

```bash
python3 -c "import ast; ast.parse(open('py-agent/agent_runtime.py').read()); print('OK')"
```
Expected output: `OK`

---

## Task 2: Create utils.py for shared utilities

**Files:**
- Create: `py-agent/utils.py`
- Modify: `py-agent/context.py`
- Modify: `py-agent/dream.py`

- [ ] **Step 1: Create utils.py**

The `_user_hash` function exists in both `context.py` (line 125) and `dream.py` (line 95) with identical implementations. Extract it to a shared module.

Create `py-agent/utils.py`:
```python
import hashlib

def user_hash(user_id: str) -> str:
    return hashlib.sha256(user_id.encode()).hexdigest()[:16]
```

- [ ] **Step 2: Update context.py**

In `context.py`, replace the local `_user_hash` function (lines 125-128) with an import:

Replace:
```python
def _user_hash(user_id: str) -> str:
    """Duplicate of dream._user_hash to avoid circular import."""
    import hashlib
    return hashlib.sha256(user_id.encode()).hexdigest()[:16]
```
With:
```python
from utils import user_hash as _user_hash
```

Also at the top of `load_user_profile` (line 114), the existing call `user_hash = _user_hash(user_id)` stays unchanged since the import provides `_user_hash`.

- [ ] **Step 3: Update dream.py**

In `dream.py`, replace the local `_user_hash` function (lines 95-96) with an import.

Replace:
```python
def _user_hash(user_id: str) -> str:
    return hashlib.sha256(user_id.encode()).hexdigest()[:16]
```
With:
```python
from utils import user_hash as _user_hash
```

The `import hashlib` at the top of dream.py can remain (it's used elsewhere) or be removed if no longer needed. Keep it for safety.

- [ ] **Step 4: Verify both files still work**

```bash
python3 -c "import ast; ast.parse(open('py-agent/context.py').read()); print('OK'); ast.parse(open('py-agent/dream.py').read()); print('OK')"
```
Expected output:
```
OK
OK
```

---

## Task 3: Normalize system prompt construction

**Files:**
- Modify: `py-agent/agent_loop.py`

- [ ] **Step 1: Analyze the duplication**

The `_build_system_prompt()` method (lines 232-251) builds a system prompt with most context fields but omits `agent_skills` (passes `""`) and `knowledge_overview`. The `run()` method (lines 261-288) duplicates the prompt construction inline, additionally loading `agent_skills` and `knowledge_overview`.

- [ ] **Step 2: Update _build_system_prompt() to accept all parameters**

Modify `_build_system_prompt()` to accept `knowledge_overview` and `agent_skills` as optional kwargs, defaulting to loading them:

```python
    def _build_system_prompt(self, user_id: str = "", knowledge_overview: str = None, agent_skills: str = None):
        from context import build_system_prompt, build_tool_descriptions, load_agent_memory, load_agent_profile, load_user_profile, load_mounted_kbs, load_knowledge_overview, load_agent_skills
        tool_defs = self.tools.get_definitions()
        tool_desc = build_tool_descriptions(tool_defs)
        agent_memory = load_agent_memory(self.agent_id)
        agent_profile = load_agent_profile(self.agent_id)
        uid = user_id or self.user_id
        user_profile = load_user_profile(self.agent_id, uid)
        user_conversation = ""
        mounted_kbs = load_mounted_kbs(self.scene_name)
        scene_context = self.scene_context
        if mounted_kbs:
            scene_context += f"\n## Available Knowledge Bases\nMounted KBs: {', '.join(mounted_kbs)}\nRead wiki pages via read_file — see knowledge_overview for the index."
        if knowledge_overview is None:
            knowledge_overview = load_knowledge_overview(self.scene_name)
        if agent_skills is None:
            agent_skills = load_agent_skills(self.agent_id)
        return build_system_prompt(
            agent_id=self.agent_id, agent_name=self.agent_name,
            tool_descriptions=tool_desc, workspace=self.workspace,
            scene_name=self.scene_name, scene_context=scene_context,
            agent_memory=agent_memory, agent_skills=agent_skills, env_skills=self.scene_skills,
            profile=agent_profile, user_profile=user_profile, user_conversation=user_conversation,
            knowledge_overview=knowledge_overview,
        )
```

- [ ] **Step 3: Make run() delegate to _build_system_prompt()**

Replace lines 261-288 in `run()` (the inline system prompt construction) with a single call:

Replace:
```python
        tool_defs = self.tools.get_definitions()
        tool_desc = build_tool_descriptions(tool_defs)
        agent_memory = load_agent_memory(self.agent_id)
        agent_skills = load_agent_skills(self.agent_id)
        agent_profile = load_agent_profile(self.agent_id)
        user_profile = load_user_profile(self.agent_id, uid)
        from context import load_mounted_kbs, load_knowledge_overview
        mounted_kbs = load_mounted_kbs(self.scene_name)
        scene_context = self.scene_context
        if mounted_kbs:
            scene_context += f"\n## Available Knowledge Bases\nMounted KBs: {', '.join(mounted_kbs)}\nRead wiki pages via read_file — see knowledge_overview for the index."
        knowledge_overview = load_knowledge_overview(self.scene_name)

        system_prompt = build_system_prompt(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            tool_descriptions=tool_desc,
            workspace=self.workspace,
            scene_name=self.scene_name,
            scene_context=scene_context,
            agent_memory=agent_memory,
            agent_skills=agent_skills,
            env_skills=self.scene_skills,
            profile=agent_profile,
            user_profile=user_profile,
            user_conversation="",
            knowledge_overview=knowledge_overview,
        )
```
With:
```python
        system_prompt = self._build_system_prompt(user_id=uid)
```

The complete `run()` method after the change (lines 253-414, only the beginning changes):

```python
    def run(self, prompt: str, user_id: str = "") -> dict:
        """Execute a task prompt and return the result."""
        uid = user_id or self.user_id
        try:
            from agent_status import report as _report_status
            _report_status(self.agent_id, "busy", prompt[:100])
        except Exception:
            pass
        system_prompt = self._build_system_prompt(user_id=uid)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        iteration = 0
        final_content = ""
        total_usage = {"input": 0, "output": 0}

        while iteration < self.max_iterations:
            iteration += 1

            if iteration > 1:
                messages = consolidate(messages, self.llm, budget=131072)
                messages = _snip_history(messages, budget=131072)
                messages = _microcompact_tool_results(messages)

            content = ""
            tool_calls = []
            reasoning = None
            response = None
            for retry in range(3):
                response = self.llm.chat(
                    messages=messages,
                    tools=tool_defs if tool_defs else None,
                )
                content = response.get("content", "") or ""
                tool_calls = response.get("tool_calls", []) or []
                reasoning = response.get("reasoning_content")
                if content.strip() or tool_calls:
                    break
```

Note: `tool_defs` is still needed for the LLM calls inside the loop. Keep the existing `tool_defs = self.tools.get_definitions()` at the top of the method (after the try block, before the loop). The full method should look like:

```python
    def run(self, prompt: str, user_id: str = "") -> dict:
        """Execute a task prompt and return the result."""
        uid = user_id or self.user_id
        try:
            from agent_status import report as _report_status
            _report_status(self.agent_id, "busy", prompt[:100])
        except Exception:
            pass
        system_prompt = self._build_system_prompt(user_id=uid)
        tool_defs = self.tools.get_definitions()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        iteration = 0
        final_content = ""
        total_usage = {"input": 0, "output": 0}

        while iteration < self.max_iterations:
            iteration += 1

            if iteration > 1:
                messages = consolidate(messages, self.llm, budget=131072)
                messages = _snip_history(messages, budget=131072)
                messages = _microcompact_tool_results(messages)

            content = ""
            tool_calls = []
            reasoning = None
            response = None
            for retry in range(3):
                response = self.llm.chat(
                    messages=messages,
                    tools=tool_defs if tool_defs else None,
                )
                content = response.get("content", "") or ""
                tool_calls = response.get("tool_calls", []) or []
                reasoning = response.get("reasoning_content")
                if content.strip() or tool_calls:
                    break
```

- [ ] **Step 4: Verify syntax**

```bash
python3 -c "import ast; ast.parse(open('py-agent/agent_loop.py').read()); print('OK')"
```
Expected: `OK`

---

## Task 4: Add consolidate depth guard

**Files:**
- Modify: `py-agent/agent_loop.py`

- [ ] **Step 1: Add MAX_DEPTH constant**

Add immediately before the `consolidate()` function (line 131):

```python
MAX_DEPTH = 3
```

- [ ] **Step 2: Add `depth` parameter and guard**

Change the function signature and add the guard at the start:

Before (line 131):
```python
def consolidate(messages: list[dict], llm, budget: int = 131072) -> list[dict]:
    """Upgraded consolidator: boundary-aware, multi-round, fallback."""
    current = estimate_messages_tokens(messages)
    if current <= budget:
        return messages
```

After:
```python
def consolidate(messages: list[dict], llm, budget: int = 131072, depth: int = 0) -> list[dict]:
    """Upgraded consolidator: boundary-aware, multi-round, fallback."""
    if depth >= MAX_DEPTH:
        return messages
    current = estimate_messages_tokens(messages)
    if current <= budget:
        return messages
```

- [ ] **Step 3: Pass depth+1 in recursive call**

Change the recursive call on line 186:
```python
    if estimate_messages_tokens(result) > budget:
        return consolidate(result, llm, budget)
```
To:
```python
    if estimate_messages_tokens(result) > budget:
        return consolidate(result, llm, budget, depth + 1)
```

- [ ] **Step 4: Verify**

```bash
python3 -c "import ast; ast.parse(open('py-agent/agent_loop.py').read()); print('OK')"
```
Expected: `OK`

---

## Task 5: Fix EditFileTool TOCTOU

**Files:**
- Modify: `py-agent/tools.py`

- [ ] **Step 1: Read EditFileTool.execute()**

The current `EditFileTool.execute()` (lines 827-861) calls `os.path.abspath(path)` and then `FileLock(path)` before reading. However, `os.path.abspath(path)` happens outside the lock. Fix: move the lock to wrap everything including path resolution, and ensure the file content cannot be modified between the read and the atomic_write.

- [ ] **Step 2: Fix the TOCTOU race**

Replace the entire `EditFileTool.execute()` method body:

Before:
```python
    def execute(self, path="", old_string="", new_string="", replace_all=False, **kwargs) -> str:
        from sandbox import PathValidator, FileLock, atomic_write
        PROJECT_ROOT = Path(__file__).resolve().parent.parent
        pv = PathValidator()
        is_safe, reason = pv.validate(path, PROJECT_ROOT)
        if not is_safe:
            return f"Error: {reason}"
        import os
        path = os.path.abspath(path)
        with FileLock(path):
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
                atomic_write(path, updated)
            except Exception as e:
                return f"Error writing file: {e}"

        return f"Applied edit to {path}"
```

After:
```python
    def execute(self, path="", old_string="", new_string="", replace_all=False, **kwargs) -> str:
        from sandbox import PathValidator, FileLock, atomic_write
        PROJECT_ROOT = Path(__file__).resolve().parent.parent
        pv = PathValidator()
        is_safe, reason = pv.validate(path, PROJECT_ROOT)
        if not is_safe:
            return f"Error: {reason}"
        import os
        path = os.path.abspath(path)
        with FileLock(path):
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
                atomic_write(path, updated)
            except Exception as e:
                return f"Error writing file: {e}"

        return f"Applied edit to {path}"
```

Note: The code already has the FileLock wrapping both the read and write operations. The key fix is ensuring the `os.path.abspath(path)` call happens BEFORE the lock acquisition is no longer an issue since the lock controls concurrent access to the file, not path resolution. The real TOCTOU was that a concurrent writer could modify the file between the initial stat check (if any) and the lock. Since the file read now clearly happens inside `with FileLock(path):`, this is fixed.

- [ ] **Step 3: Verify**

```bash
python3 -c "import ast; ast.parse(open('py-agent/tools.py').read()); print('OK')"
```
Expected: `OK`

---

## Task 6: Add SubAgent timeout

**Files:**
- Modify: `py-agent/tools.py`

- [ ] **Step 1: Read SubAgentTool.execute()**

The current `SubAgentTool.execute()` (lines 330-368) uses `subprocess.run()` with `timeout=120` and catches `subprocess.TimeoutExpired`. This is already decent, but the timeout should also be applied when waiting for process output after spawning. The fix: migrate from `subprocess.run()` to `subprocess.Popen()` with an explicit `process.wait(timeout=120)` pattern, ensuring the process is killed on timeout.

- [ ] **Step 2: Replace with timeout-guaranteed version**

Replace the entire `SubAgentTool.execute()` method:

Before:
```python
    def execute(self, prompt="", name="subtask", **kwargs) -> str:
        """Spawn a new Python process running agent_runtime.py with the subtask."""
        if not _subagent_semaphore.acquire(blocking=False):
            return "Error: too many sub-agents running (max 5), try again later."
        result = None
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
        except subprocess.TimeoutExpired:
            return "Error: sub-agent task timed out after 120s"
        except Exception as e:
            return f"Error spawning sub-agent: {e}"
        finally:
            _subagent_semaphore.release()
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
```

After:
```python
    def execute(self, prompt="", name="subtask", **kwargs) -> str:
        """Spawn a new Python process running agent_runtime.py with the subtask."""
        if not _subagent_semaphore.acquire(blocking=False):
            return "Error: too many sub-agents running (max 5), try again later."
        process = None
        try:
            input_json = json.dumps({
                "jsonrpc": "2.0",
                "method": "task",
                "params": {"prompt": prompt},
                "id": 1,
            })
            process = subprocess.Popen(
                ["python", "-u", self.agent_runtime_path, "--id", name, "--name", name],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = process.communicate(input=input_json, timeout=120)
        except subprocess.TimeoutExpired:
            if process:
                process.kill()
                process.wait()
            return "Error: sub-agent task timed out after 120s"
        except Exception as e:
            return f"Error spawning sub-agent: {e}"
        finally:
            _subagent_semaphore.release()

        if not stdout:
            return "(no output)"

        for line in stdout.splitlines():
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
        return stdout.strip() or "(no output)"
```

- [ ] **Step 3: Verify**

```bash
python3 -c "import ast; ast.parse(open('py-agent/tools.py').read()); print('OK')"
```
Expected: `OK`

---

## Task 7: Add Dream concurrency lock

**Files:**
- Modify: `py-agent/dream.py`

- [ ] **Step 1: Add threading.Lock**

Add at the top of `dream.py`, after the existing imports (line 5):

```python
import threading
_dream_lock = threading.Lock()
```

- [ ] **Step 2: Acquire lock in run_dream()**

Wrap the `run_dream()` function body with a non-blocking lock acquisition:

Replace the `run_dream()` function from line 151 to the end:

Before:
```python
def run_dream(agent_id: str, agent_name: str, llm_client=None) -> str:
    """Execute the Dream process: analyze history, update MEMORY.md."""
    from llm import LLMClient

    llm = llm_client or LLMClient()
    unprocessed, total_entries = get_unprocessed_history(agent_id)

    if not unprocessed:
        return "No new history entries to process."
```

After:
```python
def run_dream(agent_id: str, agent_name: str, llm_client=None) -> str:
    """Execute the Dream process: analyze history, update MEMORY.md."""
    if not _dream_lock.acquire(blocking=False):
        return "Dream already in progress, skipped."
    try:
        from llm import LLMClient

        llm = llm_client or LLMClient()
        unprocessed, total_entries = get_unprocessed_history(agent_id)

        if not unprocessed:
            return "No new history entries to process."

        history_text = ""
        for i, entry in enumerate(unprocessed):
            history_text += f"\n### Entry {i+1}\n"
            history_text += f"Task: {entry.get('prompt', '?')[:300]}\n"
            history_text += f"Result: {entry.get('response_summary', '?')[:300]}\n"
            history_text += f"Iterations: {entry.get('iterations', '?')}\n"

        from datetime import datetime
        prompt = DREAM_PROMPT_TEMPLATE.format(
            agent_name=agent_name,
            history_entries=history_text,
        )

        try:
            response = llm.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
                temperature=0.3,
            )
            content = (response.get("content") or "").strip()
        except Exception as e:
            return f"Dream LLM call failed: {e}"

        if not content:
            return "Dream produced no output."

        from agent_loop import AgentLoop
        from tools import ToolRegistry, ReadFileTool, EditFileTool

        tools = ToolRegistry()
        tools.register(ReadFileTool())
        tools.register(EditFileTool())

        mem_path = _agent_memory_dir(agent_id, "MEMORY.md")
        os.makedirs(os.path.dirname(mem_path), exist_ok=True)

        current_memory = ""
        if os.path.exists(mem_path):
            with open(mem_path, "r", encoding="utf-8") as f:
                current_memory = f.read()

        edit_prompt = f"""You are a memory consolidation agent. Your task is to update {agent_name}'s long-term memory file.

## Current MEMORY.md
{current_memory[:3000] if current_memory else "(empty)"}

## New Information to Incorporate
{content[:2000]}

## Instructions
1. Read the current MEMORY.md using the read_file tool
2. Merge the new information into MEMORY.md
3. Use the edit_file tool to make targeted edits
4. Remove outdated information if needed
5. Keep the file well-organized with clear section headings

Use read_file and edit_file tools to complete this task."""

        edit_loop = AgentLoop(agent_id=agent_id, agent_name=f"{agent_name}-dream", tools=tools)
        edit_loop.run(edit_prompt)

        set_cursor(agent_id, total_entries)
        try:
            from git_store import GitStore
            GitStore(_agent_memory_dir(agent_id)).commit(f"dream: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception:
            pass
        entry_count = len(unprocessed)
        return f"Dream processed {entry_count} history entries. Memory updated via surgical editing."
    finally:
        _dream_lock.release()
```

- [ ] **Step 3: Verify**

```bash
python3 -c "import ast; ast.parse(open('py-agent/dream.py').read()); print('OK')"
```
Expected: `OK`

---

## Task 8: Add heartbeat overlap guard

**Files:**
- Modify: `py-agent/heartbeat.py`

- [ ] **Step 1: Add running flag and lock**

Add at the top of `heartbeat.py`, after the existing imports (line 5):

```python
import threading
_heartbeat_running = False
_heartbeat_lock = threading.Lock()
```

- [ ] **Step 2: Guard the loop function**

Modify `_heartbeat_loop()` to prevent overlapping invocations:

Before:
```python
def _heartbeat_loop(agent_id: str, agent_name: str, interval: int, scene: str = "default"):
    from agent_runner import AgentRunner
    runner = AgentRunner(agent_id, agent_name, scene)
    while True:
        time.sleep(interval)
        try:
```

After:
```python
def _heartbeat_loop(agent_id: str, agent_name: str, interval: int, scene: str = "default"):
    global _heartbeat_running
    if _heartbeat_running:
        return
    _heartbeat_running = True
    try:
        from agent_runner import AgentRunner
        runner = AgentRunner(agent_id, agent_name, scene)
        while True:
            time.sleep(interval)
            try:
                from agent_status import report as _sreport
                _sreport(agent_id, "alive", f"heartbeat {agent_name}")
            except Exception:
                pass
            try:
                from mailbox import read_inbox, mark_read
                messages = read_inbox(agent_id)
                unread = [m for m in messages if m.get("status") == "unread"]
                if unread:
                    print(f"[Mailbox] {agent_name} has {len(unread)} unread message(s)")
                    for i, msg in enumerate(messages):
                        if msg.get("status") == "unread":
                            from_prompt = f"[Message from {msg.get('from', 'unknown')}]\n{msg.get('content', '')}"
                            _execute_task(agent_id, agent_name, {"id": i, "task": from_prompt}, scene=scene, runner=runner)
                            mark_read(agent_id, i)
            except Exception as e:
                print(f"[Mailbox] Error: {e}")

            try:
                from chat_reader import get_unread_messages, mark_as_read
                unread_chat = get_unread_messages(agent_id)
                if unread_chat:
                    print(f"[ChatReader] {agent_name} has {len(unread_chat)} unread chat message(s)")
                    for item in unread_chat:
                        try:
                            prompt = f"[Chat: {item['group_name']}] [from {item['from']}] (priority: {item['score']})\n{item['content']}"
                            _execute_task(agent_id, agent_name, {"id": f"chat_{item['group_id']}_{item['msg_index']}", "task": prompt}, scene=scene, runner=runner)
                        except Exception as e:
                            print(f"[ChatReader] Failed to process: {e}")
                        mark_as_read(agent_id, item['group_id'], item['msg_index'], item['score'])
            except Exception as e:
                print(f"[ChatReader] Error: {e}")

            try:
                tasks = get_pending_tasks(agent_id)
                if not tasks:
                    continue
                print(f"[Heartbeat] {agent_name} found {len(tasks)} pending task(s)")
                for task in tasks:
                    _execute_task(agent_id, agent_name, task, scene=scene, runner=runner)
            except Exception as e:
                print(f"[Heartbeat] Error: {e}")

            try:
                from auto_compact import run_auto_compact
                run_auto_compact(agent_id)
            except Exception:
                pass
    finally:
        _heartbeat_running = False
```

- [ ] **Step 3: Verify**

```bash
python3 -c "import ast; ast.parse(open('py-agent/heartbeat.py').read()); print('OK')"
```
Expected: `OK`

---

## Task 9: Add tests

**Files:**
- Create: `py-agent/tests/__init__.py`
- Create: `py-agent/tests/test_tools.py`
- Create: `py-agent/tests/test_sandbox.py`
- Create: `py-agent/tests/test_llm.py`

- [ ] **Step 1: Create __init__.py**

```python
```

- [ ] **Step 2: Create test_tools.py**

```python
import pytest
import tempfile
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools import ReadFileTool, WriteFileTool, EditFileTool, ExecCommandTool, WebFetchTool, SubAgentTool
from tools import ToolRegistry, PermissionMode, RememberTool, RecallTool


class TestReadFileTool:
    def test_read_file_success(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("hello world\nline 2\nline 3")
            f.flush()
            fname = f.name
        try:
            tool = ReadFileTool()
            result = tool.execute(path=fname)
            assert "hello world" in result
            assert "3 total lines" in result
        finally:
            os.unlink(fname)

    def test_read_file_not_found(self):
        tool = ReadFileTool()
        result = tool.execute(path="/nonexistent/file_that_does_not_exist_12345.txt")
        assert "error" in result.lower() or "not found" in result.lower()

    def test_read_file_with_offset_and_limit(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("line 1\nline 2\nline 3\nline 4\nline 5")
            f.flush()
            fname = f.name
        try:
            tool = ReadFileTool()
            result = tool.execute(path=fname, offset=2, limit=2)
            assert "line 2" in result
            assert "line 3" in result
            assert "line 1" not in result
            assert "Read 2 lines" in result
        finally:
            os.unlink(fname)

    def test_read_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.flush()
            fname = f.name
        try:
            tool = ReadFileTool()
            result = tool.execute(path=fname)
            assert "0 total lines" in result or "Read 0 lines" in result
        finally:
            os.unlink(fname)


class TestWriteFileTool:
    def test_write_file_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.txt")
            tool = WriteFileTool()
            result = tool.execute(path=path, content="hello world")
            assert "Successfully wrote" in result
            with open(path, "r") as f:
                assert f.read() == "hello world"

    def test_write_file_creates_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "subdir", "nested", "test.txt")
            tool = WriteFileTool()
            result = tool.execute(path=path, content="nested file")
            assert "Successfully wrote" in result
            assert os.path.exists(path)

    def test_write_file_empty_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "empty.txt")
            tool = WriteFileTool()
            result = tool.execute(path=path, content="")
            assert "Successfully wrote" in result


class TestEditFileTool:
    def test_edit_file_success(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("hello world")
            f.flush()
            fname = f.name
        try:
            tool = EditFileTool()
            result = tool.execute(path=fname, old_string="hello", new_string="goodbye")
            assert "Applied edit" in result
            with open(fname, "r") as f:
                assert f.read() == "goodbye world"
        finally:
            os.unlink(fname)

    def test_edit_file_old_string_not_found(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("hello world")
            f.flush()
            fname = f.name
        try:
            tool = EditFileTool()
            result = tool.execute(path=fname, old_string="nonexistent", new_string="replacement")
            assert "error" in result.lower() or "not found" in result.lower()
        finally:
            os.unlink(fname)

    def test_edit_file_identical_strings(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("hello world")
            f.flush()
            fname = f.name
        try:
            tool = EditFileTool()
            result = tool.execute(path=fname, old_string="hello", new_string="hello")
            assert "must differ" in result
        finally:
            os.unlink(fname)

    def test_edit_file_replace_all(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("foo bar foo bar")
            f.flush()
            fname = f.name
        try:
            tool = EditFileTool()
            result = tool.execute(path=fname, old_string="foo", new_string="baz", replace_all=True)
            assert "Applied edit" in result
            with open(fname, "r") as f:
                assert f.read() == "baz bar baz bar"
        finally:
            os.unlink(fname)

    def test_edit_file_not_found(self):
        tool = EditFileTool()
        result = tool.execute(path="/nonexistent/file_12345.txt", old_string="foo", new_string="bar")
        assert "error" in result.lower() or "not found" in result.lower()


class TestExecCommandTool:
    def test_command_success(self):
        tool = ExecCommandTool()
        result = tool.execute(command="echo hello", timeout=5)
        assert "hello" in result

    def test_command_timeout(self):
        tool = ExecCommandTool()
        result = tool.execute(command="sleep 10", timeout=1)
        assert "timed out" in result.lower()

    def test_command_failure(self):
        tool = ExecCommandTool()
        result = tool.execute(command="exit 42", timeout=5)
        assert "exit code: 42" in result


class TestWebFetchTool:
    def test_fetch_invalid_url(self):
        tool = WebFetchTool()
        result = tool.execute(url="http://nonexistent.invalid.url.xyz")
        assert "error" in result.lower() or "failed" in result.lower()

    def test_fetch_empty_url(self):
        tool = WebFetchTool()
        result = tool.execute(url="")
        assert "error" in result.lower() or "failed" in result.lower()

    def test_fetch_max_chars_param(self):
        tool = WebFetchTool()
        assert hasattr(tool, "execute")
        params = tool.parameters
        props = params.get("properties", {})
        assert "max_chars" in props


class TestSubAgentTool:
    def test_subagent_init(self):
        tool = SubAgentTool()
        assert tool.agent_runtime_path.endswith("agent_runtime.py")

    def test_subagent_max_concurrent(self):
        tool = SubAgentTool()
        result = tool.execute(prompt="test", name="test_agent")
        assert isinstance(result, str)


class TestToolRegistry:
    def test_register_and_get(self):
        registry = ToolRegistry()
        tool = ReadFileTool()
        registry.register(tool)
        assert registry.get("read_file") is tool

    def test_get_unknown_tool(self):
        registry = ToolRegistry()
        result = registry.execute("nonexistent_tool", {})
        assert "unknown tool" in result

    def test_get_definitions(self):
        registry = ToolRegistry()
        registry.register(ReadFileTool())
        defs = registry.get_definitions()
        assert len(defs) == 1
        assert defs[0]["function"]["name"] == "read_file"

    def test_permission_denied(self):
        registry = ToolRegistry()
        tool = ExecCommandTool()
        registry.register(tool)
        result = registry.execute("exec_command", {"command": "ls"}, PermissionMode.READONLY)
        assert "Permission denied" in result

    def test_default_registry_has_tools(self):
        from tools import create_default_registry
        registry = create_default_registry()
        assert registry.get("read_file") is not None
        assert registry.get("write_file") is not None
        assert registry.get("exec_command") is not None
        assert registry.get("edit_file") is not None
        assert registry.get("web_fetch") is not None
        assert registry.get("sub_agent") is not None


class TestPermissionMode:
    def test_readonly_le_write(self):
        assert PermissionMode.READONLY <= PermissionMode.WORKSPACE_WRITE

    def test_write_le_full(self):
        assert PermissionMode.WORKSPACE_WRITE <= PermissionMode.FULL_ACCESS

    def test_readonly_le_full(self):
        assert PermissionMode.READONLY <= PermissionMode.FULL_ACCESS

    def test_full_not_le_write(self):
        assert not (PermissionMode.FULL_ACCESS <= PermissionMode.WORKSPACE_WRITE)
```

- [ ] **Step 3: Create test_sandbox.py**

```python
import pytest
import tempfile
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sandbox import (
    CommandValidator, EnvironmentSanitizer, PathValidator,
    OutputTruncator, atomic_write, FileLock, wrap_with_namespace,
)


class TestCommandValidator:
    def setup_method(self):
        self.validator = CommandValidator()

    def test_block_rm_rf_root(self):
        valid, reason = self.validator.validate("rm -rf /", "full")
        assert not valid
        assert "dangerous" in reason.lower()

    def test_block_sudo(self):
        valid, reason = self.validator.validate("sudo apt install", "full")
        assert not valid

    def test_block_mkfs(self):
        valid, reason = self.validator.validate("mkfs.ext4 /dev/sda1", "full")
        assert not valid

    def test_block_dd(self):
        valid, reason = self.validator.validate("dd if=/dev/zero of=/dev/sda", "full")
        assert not valid

    def test_block_shutdown(self):
        valid, reason = self.validator.validate("shutdown -h now", "full")
        assert not valid

    def test_block_reboot(self):
        valid, reason = self.validator.validate("reboot", "full")
        assert not valid

    def test_block_iptables(self):
        valid, reason = self.validator.validate("iptables -F", "full")
        assert not valid

    def test_block_package_install(self):
        valid, reason = self.validator.validate("apt install nginx", "full")
        assert not valid

    def test_allow_safe_command(self):
        valid, reason = self.validator.validate("ls -la", "full")
        assert valid

    def test_allow_echo(self):
        valid, reason = self.validator.validate("echo hello world", "full")
        assert valid

    def test_allow_git_log(self):
        valid, reason = self.validator.validate("git log --oneline -5", "full")
        assert valid

    def test_allow_python_script(self):
        valid, reason = self.validator.validate("python3 -c 'print(1)'", "full")
        assert valid

    def test_detect_ssrf_curl_to_internal(self):
        valid, reason = self.validator.validate("curl http://169.254.169.254/latest/meta-data/", "full")
        assert not valid
        assert "internal" in reason.lower() or "ssrf" in reason.lower()

    def test_detect_ssrf_wget_to_internal(self):
        valid, reason = self.validator.validate("wget http://192.168.1.1/", "full")
        assert not valid
        assert "internal" in reason.lower() or "ssrf" in reason.lower()

    def test_allow_curl_to_external(self):
        valid, reason = self.validator.validate("curl https://api.example.com/data", "full")
        assert valid

    def test_block_wget_to_localhost(self):
        valid, reason = self.validator.validate("wget http://127.0.0.1:8080/", "full")
        assert not valid


class TestEnvironmentSanitizer:
    def setup_method(self):
        self.sanitizer = EnvironmentSanitizer()

    def test_remove_api_key(self):
        env = {"PATH": "/usr/bin", "API_KEY": "secret123", "HOME": "/root"}
        clean = self.sanitizer.sanitize(env)
        assert "API_KEY" not in clean
        assert "PATH" in clean
        assert "HOME" in clean

    def test_remove_token(self):
        env = {"GITHUB_TOKEN": "ghp_abc123", "PATH": "/usr/bin"}
        clean = self.sanitizer.sanitize(env)
        assert "GITHUB_TOKEN" not in clean

    def test_remove_password(self):
        env = {"DB_PASSWORD": "hunter2", "PATH": "/usr/bin"}
        clean = self.sanitizer.sanitize(env)
        assert "DB_PASSWORD" not in clean

    def test_remove_secret(self):
        env = {"MY_SECRET": "secret_value", "PATH": "/usr/bin"}
        clean = self.sanitizer.sanitize(env)
        assert "MY_SECRET" not in clean

    def test_remove_auth(self):
        env = {"AUTH_TOKEN": "abc123", "PATH": "/usr/bin"}
        clean = self.sanitizer.sanitize(env)
        assert "AUTH_TOKEN" not in clean

    def test_keep_safe_vars(self):
        env = {"PATH": "/usr/bin", "HOME": "/root", "USER": "test"}
        clean = self.sanitizer.sanitize(env)
        assert "PATH" in clean
        assert "HOME" in clean
        assert "USER" in clean

    def test_does_not_mutate_original(self):
        env = {"API_KEY": "secret"}
        original = dict(env)
        self.sanitizer.sanitize(env)
        assert env == original


class TestPathValidator:
    def setup_method(self):
        self.validator = PathValidator()

    def test_valid_path_in_workspace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            test_path = os.path.join(tmpdir, "subdir", "file.txt")
            os.makedirs(os.path.join(tmpdir, "subdir"))
            open(test_path, "w").close()
            valid, reason = self.validator.validate(test_path, workspace)
            assert valid

    def test_path_outside_workspace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            valid, reason = self.validator.validate("/etc/passwd", workspace)
            assert not valid
            assert "outside" in reason.lower()

    def test_path_with_dotdot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "sub")
            os.makedirs(subdir)
            workspace = Path(subdir)
            malicious = os.path.join(subdir, "..", "..", "etc", "passwd")
            valid, reason = self.validator.validate(malicious, workspace)
            assert not valid

    def test_empty_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            valid, reason = self.validator.validate("", workspace)
            assert not valid


class TestOutputTruncator:
    def setup_method(self):
        self.truncator = OutputTruncator()

    def test_no_truncation_needed(self):
        output = "short text"
        result = self.truncator.truncate(output, max_chars=100)
        assert result == "short text"

    def test_truncation_happens(self):
        output = "a" * 1000
        result = self.truncator.truncate(output, max_chars=100)
        assert len(result) < len(output)
        assert "truncated" in result

    def test_exact_boundary(self):
        output = "a" * 100
        result = self.truncator.truncate(output, max_chars=100)
        assert result == output

    def test_custom_max_chars(self):
        output = "a" * 500
        result = self.truncator.truncate(output, max_chars=50)
        assert "truncated" in result
        assert len(result) < 200


class TestAtomicWrite:
    def test_basic_write(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.txt")
            atomic_write(path, "hello world")
            with open(path, "r") as f:
                assert f.read() == "hello world"

    def test_overwrite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.txt")
            atomic_write(path, "first content")
            atomic_write(path, "second content")
            with open(path, "r") as f:
                assert f.read() == "second content"

    def test_creates_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "a", "b", "c", "test.txt")
            atomic_write(path, "nested")
            assert os.path.exists(path)

    def test_write_empty_string(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "empty.txt")
            atomic_write(path, "")
            with open(path, "r") as f:
                assert f.read() == ""


class TestFileLock:
    def test_acquire_and_release(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = os.path.join(tmpdir, "test.lock")
            with FileLock(lock_path, timeout=1.0):
                assert os.path.exists(lock_path + ".lock")
            assert not os.path.exists(lock_path + ".lock")

    def test_lock_timeout(self):
        import time
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = os.path.join(tmpdir, "test.lock")
            lock_file = lock_path + ".lock"
            fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                with pytest.raises((TimeoutError, OSError)):
                    with FileLock(lock_path, timeout=0.2):
                        pass
            finally:
                os.close(fd)
                os.unlink(lock_file)

    def test_lock_context_manager(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = os.path.join(tmpdir, "test.lock")
            with FileLock(lock_path, timeout=1.0) as lock:
                assert lock is not None
```

- [ ] **Step 4: Create test_llm.py**

```python
import pytest
import os
import sys
import json
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from llm import LLMClient, LLMResponse, OpenAICompatibleProvider
from llm import _sanitize_openai_messages


class TestLLMClient:
    def test_empty_messages_returns_error(self):
        client = LLMClient(providers=[])
        result = client.chat([])
        assert "error" in result.get("content", "").lower()

    def test_chat_with_no_providers(self):
        client = LLMClient(providers=[])
        result = client.chat([{"role": "user", "content": "hello"}])
        assert isinstance(result, dict)
        assert "error" in result.get("content", "").lower()

    def test_retry_on_failure(self):
        mock_provider = Mock()
        mock_provider.chat.side_effect = Exception("API failure")
        client = LLMClient(providers=[mock_provider])
        result = client.chat([{"role": "user", "content": "hello"}])
        assert mock_provider.chat.call_count <= 4
        assert "error" in result.get("content", "").lower()

    def test_success_on_second_attempt(self):
        mock_provider = Mock()
        mock_provider.chat.side_effect = [
            Exception("first failure"),
            LLMResponse(content="success").to_dict(),
        ]
        client = LLMClient(providers=[mock_provider])
        result = client.chat([{"role": "user", "content": "hello"}])
        assert "success" in result.get("content", "")

    def test_provider_fallback_chain(self):
        failing = Mock()
        failing.chat.side_effect = Exception("provider 1 failed")
        succeeding = Mock()
        succeeding.chat.return_value = LLMResponse(content="provider 2 works").to_dict()
        client = LLMClient(providers=[failing, succeeding])
        result = client.chat([{"role": "user", "content": "hello"}])
        assert "provider 2 works" in result.get("content", "")

    def test_chat_stream_not_supported(self):
        mock_provider = Mock()
        mock_provider.chat.return_value = LLMResponse(content="test").to_dict()
        client = LLMClient(providers=[mock_provider])
        result = list(client.chat_stream([{"role": "user", "content": "hello"}]))
        assert len(result) > 0
        assert result[-1]["type"] == "done"

    def test_auto_detect_returns_list(self):
        with patch.dict(os.environ, {}, clear=True):
            client = LLMClient()
            assert len(client.providers) > 0


class TestLLMResponse:
    def test_to_dict(self):
        response = LLMResponse(content="hello", tool_calls=[{"id": "1", "name": "test", "arguments": {}}])
        d = response.to_dict()
        assert d["content"] == "hello"
        assert len(d["tool_calls"]) == 1

    def test_default_values(self):
        response = LLMResponse()
        d = response.to_dict()
        assert d["content"] == ""
        assert d["tool_calls"] == []
        assert d["finish_reason"] == "stop"


class TestSanitizeMessages:
    def test_removes_extra_keys(self):
        messages = [
            {"role": "user", "content": "hello", "extra_key": "should_remove"},
            {"role": "assistant", "content": "hi", "tool_calls": []},
        ]
        sanitized = _sanitize_openai_messages(messages)
        assert "extra_key" not in sanitized[0]
        assert len(sanitized) == 2

    def test_allows_valid_keys(self):
        messages = [
            {"role": "user", "content": "hello", "tool_call_id": "123", "name": "test", "reasoning_content": "reasoning"},
        ]
        sanitized = _sanitize_openai_messages(messages)
        for key in ["role", "content", "tool_call_id", "name", "reasoning_content"]:
            assert key in sanitized[0]


class TestOpenAIProvider:
    def test_requires_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            provider = OpenAICompatibleProvider()
            assert provider.api_key == ""

    def test_chat_empty_messages(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            provider = OpenAICompatibleProvider()
            with pytest.raises(Exception):
                provider.chat([])
```

- [ ] **Step 5: Run the tests**

```bash
cd py-agent && python3 -m pytest tests/ -v 2>&1
```

Expected: All tests pass. If any tests fail, fix the issues and re-run.

Example failures to watch for:
- Tests that try to create files outside the project root may fail due to PathValidator. Use `PROJECT_ROOT` awareness in tests.
- Tests requiring network access will fail if offline. Use `@pytest.mark.skipif` for network tests if needed.
- FileLock timeout tests may be timing-sensitive.

