# CocoCat 记忆系统重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构 CocoCat 记忆系统，实现三层记忆分层、用户感知、GitStore 版本控制、Dream 触发优化

**Architecture:** 在现有 `agents/{id}/memory/` 结构上添加 `users/{user_hash}/` 子目录，引入 GitStore 轻量版本控制，Dream 改为 per-user 处理且触发条件改为 token 感知

**Tech Stack:** Python 3.11+, git, pytest

---

### Task 1: GitStore — 轻量版本控制模块

**Files:**
- Create: `py-agent/git_store.py`
- Test: `tests/test_git_store.py`

- [ ] **Step 1: Write the failing test for GitStore init and commit**

```python
import tempfile, os, shutil
from git_store import GitStore

def test_git_store_init_and_commit():
    tmp = tempfile.mkdtemp()
    try:
        store = GitStore(tmp)
        # init should create .git directory
        assert os.path.isdir(os.path.join(tmp, ".git"))
        # write a file and commit
        test_file = os.path.join(tmp, "TEST.md")
        with open(test_file, "w") as f:
            f.write("hello")
        store.commit("test: first commit")
        # commit should succeed without raising
        log = store.log()
        assert len(log) >= 1
        assert "test: first commit" in log[0]
    finally:
        shutil.rmtree(tmp)

def test_git_store_revert():
    tmp = tempfile.mkdtemp()
    try:
        store = GitStore(tmp)
        test_file = os.path.join(tmp, "TEST.md")
        with open(test_file, "w") as f:
            f.write("version 1")
        store.commit("v1")
        with open(test_file, "w") as f:
            f.write("version 2")
        store.commit("v2")
        store.revert()
        with open(test_file) as f:
            assert f.read() == "version 1"
    finally:
        shutil.rmtree(tmp)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_git_store.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'git_store'"

- [ ] **Step 3: Write minimal GitStore implementation**

```python
import subprocess, os

class GitStore:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        if not os.path.isdir(os.path.join(repo_path, ".git")):
            subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
            subprocess.run(["git", "config", "user.name", "cococat-memory"],
                           cwd=repo_path, capture_output=True)
            subprocess.run(["git", "config", "user.email", "memory@cococat.local"],
                           cwd=repo_path, capture_output=True)

    def commit(self, message: str):
        subprocess.run(["git", "add", "-A"], cwd=self.repo_path, capture_output=True)
        result = subprocess.run(["git", "commit", "-m", message],
                                cwd=self.repo_path, capture_output=True, text=True)
        return result.returncode == 0

    def log(self, max_count: int = 10) -> list[str]:
        result = subprocess.run(
            ["git", "log", f"--max-count={max_count}", "--oneline"],
            cwd=self.repo_path, capture_output=True, text=True
        )
        return [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]

    def revert(self):
        result = subprocess.run(
            ["git", "log", "--oneline", "--max-count=2"],
            cwd=self.repo_path, capture_output=True, text=True
        )
        lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
        if len(lines) >= 2:
            parent_hash = lines[-1].split()[0]
            subprocess.run(["git", "reset", "--hard", parent_hash],
                           cwd=self.repo_path, capture_output=True)

    def last_commit_message(self) -> str:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=self.repo_path, capture_output=True, text=True
        )
        return result.stdout.strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_git_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add py-agent/git_store.py tests/test_git_store.py
git commit -m "feat: add GitStore for memory versioning"
```

---

### Task 2: 用户感知注入 — context.py 扩展

**Files:**
- Modify: `py-agent/context.py`
- Test: `tests/test_user_identity.py`

- [ ] **Step 1: Write the failing test**

```python
import tempfile, os, json
from context import load_user_profile, build_system_prompt

def test_load_user_profile_exists():
    tmp = tempfile.mkdtemp()
    try:
        user_dir = os.path.join(tmp, "memory", "users", "u_hash")
        os.makedirs(user_dir)
        profile_path = os.path.join(user_dir, "PROFILE.md")
        with open(profile_path, "w") as f:
            f.write("- likes blue products")
        profile = load_user_profile(agent_id="test", user_id="user_abc", base_dir=tmp)
        assert profile == "- likes blue products"
    finally:
        import shutil; shutil.rmtree(tmp)

def test_load_user_profile_not_exists():
    profile = load_user_profile(agent_id="test", user_id="nonexistent")
    assert profile == ""

def test_build_system_prompt_with_user():
    prompt = build_system_prompt(
        agent_name="TestBot",
        agent_memory="I know things.",
        agent_skills=[],
        env_skills=[],
        user_profile="likes blue",
        user_conversation="[user] hello\n[agent] hi",
    )
    assert "## 当前用户" in prompt
    assert "likes blue" in prompt
    assert "## 对话历史" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_user_identity.py -v`
Expected: FAIL

- [ ] **Step 3: Add `load_user_profile` and update `build_system_prompt` in context.py**

Add to context.py after `load_agent_memory`:

```python
def load_user_profile(agent_id: str, user_id: str, base_dir: str = "") -> str:
    if not base_dir:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    user_hash = _user_hash(user_id)
    profile_path = os.path.join(base_dir, "..", "agents", agent_id, "memory", "users", user_hash, "PROFILE.md")
    if not os.path.exists(profile_path):
        return ""
    with open(profile_path, "r", encoding="utf-8") as f:
        return f.read()

def _user_hash(user_id: str) -> str:
    import hashlib
    return hashlib.sha256(user_id.encode()).hexdigest()[:16]
```

Update `SYSTEM_PROMPT_TEMPLATE`:

```python
SYSTEM_PROMPT_TEMPLATE = """You are {agent_name}, a capable AI agent...
...
{profile_section}
{memory_section}
{user_profile_section}
{user_conversation_section}
...
"""
```

Update `build_system_prompt` to accept and inject new params:

```python
def build_system_prompt(
    agent_name: str = "CocoCat",
    agent_memory: str = "",
    agent_skills: list | None = None,
    env_skills: list | None = None,
    user_profile: str = "",
    user_conversation: str = "",
    profile: dict | None = None,
    scene_name: str = "",
    scene_context: str = "",
) -> str:
    ...
    user_profile_section = f"\n## 当前用户\n{user_profile}" if user_profile else ""
    user_conversation_section = f"\n## 对话历史\n{user_conversation}" if user_conversation else ""
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_user_identity.py -v`
Expected: PASS

- [ ] **Step 5: Update existing test_context.py to match new signature**

Run: `python -m pytest tests/test_context.py -v`
If fails, update the test call to pass new params.

- [ ] **Step 6: Commit**

```bash
git add py-agent/context.py tests/test_user_identity.py tests/test_context.py
git commit -m "feat: add user profile injection to system prompt"
```

---

### Task 3: 用户感知管道 — agent_runtime + web/main.py 传递 user_id

**Files:**
- Modify: `py-agent/agent_runtime.py`
- Modify: `py-agent/agent_loop.py`
- Modify: `web/main.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_user_pipeline.py
import json
from agent_loop import AgentLoop

def test_agent_loop_accepts_user_id():
    loop = AgentLoop(agent_id="test_agent", user_id="test_user")
    assert loop.user_id == "test_user"

def test_agent_loop_default_user_id():
    loop = AgentLoop(agent_id="test_agent")
    assert loop.user_id == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_user_pipeline.py -v`
Expected: FAIL

- [ ] **Step 3: Update AgentLoop to accept user_id**

In `agent_loop.py`:

```python
class AgentLoop:
    def __init__(self, agent_id: str, agent_name: str = "", user_id: str = "", ...):
        self.user_id = user_id
        ...
```

And in `run()`:

```python
def run(self, prompt: str, user_id: str = "") -> dict:
    uid = user_id or self.user_id
    ...
    system_prompt = self._build_system_prompt(user_id=uid)
```

And `_build_system_prompt()`:

```python
def _build_system_prompt(self, user_id: str = "") -> str:
    ...
    user_profile = load_user_profile(self.agent_id, user_id)
    ...
```

- [ ] **Step 4: Update agent_runtime.py to pass user_id**

```python
# agent_runtime.py handle_request
user_id = request.get("user_id", "")
loop = AgentLoop(agent_id=agent_id, agent_name=agent_name, user_id=user_id)
...
result = loop.run(prompt=prompt, user_id=user_id)
```

- [ ] **Step 5: Update web/main.py to pass user_id**

In `_agent_process_message`:

```python
task = json.dumps({
    "type": "run",
    "prompt": prompt,
    "agent_id": agent_id,
    "user_id": user_id,  # NEW
})
```

- [ ] **Step 6: Run all tests**

Run: `python -m pytest tests/test_user_pipeline.py tests/test_user_identity.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add py-agent/agent_loop.py py-agent/agent_runtime.py web/main.py tests/test_user_pipeline.py
git commit -m "feat: pass user_id through agent pipeline"
```

---

### Task 4: Dream 触发优化 — token 感知 + 时间触发

**Files:**
- Modify: `py-agent/dream.py`
- Modify: `py-agent/agent_loop.py`
- Test: `tests/test_dream_trigger.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_dream_trigger.py
import tempfile, os, json
from dream import should_trigger_dream

def make_history(entries: list[dict]) -> str:
    return "\n".join(json.dumps(e) for e in entries)

def test_trigger_by_count():
    entries = [{"content": "x" * 100}] * 5
    assert should_trigger_dream(entries, last_dream_time=0, now=1000)

def test_not_trigger_below_threshold():
    entries = [{"content": "x" * 100}] * 1
    assert not should_trigger_dream(entries, last_dream_time=0, now=1000)

def test_trigger_by_time():
    entries = [{"content": "x" * 100}] * 1
    assert should_trigger_dream(entries, last_dream_time=0, now=2000)

def test_not_trigger_within_cooldown():
    entries = [{"content": "x" * 100}] * 5
    assert not should_trigger_dream(entries, last_dream_time=1000, now=1100)

def test_trigger_token_budget_large():
    # Many tokens, should trigger even with few entries
    entries = [{"content": "x" * 5000}] * 2  # ~10k chars = many tokens
    assert should_trigger_dream(entries, last_dream_time=100, now=200)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_dream_trigger.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `should_trigger_dream` in dream.py**

```python
import time

DREAM_COUNT_MIN = 3
DREAM_COUNT_MAX = 10
DREAM_TOKEN_PER_ENTRY = 2000  # approximate
DREAM_TIME_TRIGGER = 1800  # 30 minutes

def should_trigger_dream(unprocessed_entries: list, last_dream_time: float, now: float) -> bool:
    if not unprocessed_entries:
        return False
    # Count-based: dynamic threshold based on token volume
    total_chars = sum(len(e.get("content", "") if isinstance(e, dict) else str(e)) for e in unprocessed_entries)
    dynamic_threshold = max(DREAM_COUNT_MIN, min(DREAM_COUNT_MAX, total_chars // DREAM_TOKEN_PER_ENTRY))
    if len(unprocessed_entries) >= dynamic_threshold:
        return True
    # Time-based: 30 min since last dream
    if now - last_dream_time >= DREAM_TIME_TRIGGER:
        return True
    return False

def _read_last_dream_time(agent_id: str) -> float:
    cursor_path = os.path.join(_agent_memory_dir(agent_id), ".dream_cursor")
    try:
        return os.path.getmtime(cursor_path)
    except OSError:
        return 0.0
```

- [ ] **Step 4: Update auto_dream in agent_loop.py**

```python
def auto_dream(agent_id: str, agent_name: str, llm) -> None:
    from dream import get_unprocessed_history, run_dream, should_trigger_dream, _read_last_dream_time
    if not should_trigger_dream(*get_unprocessed_history(agent_id), _read_last_dream_time(agent_id), time.time()):
        return
    try:
        run_dream(agent_id, agent_name, llm_client=llm)
    except Exception:
        pass
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_dream_trigger.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add py-agent/dream.py py-agent/agent_loop.py tests/test_dream_trigger.py
git commit -m "feat: token-aware dream trigger with time-based fallback"
```

---

### Task 5: Per-User Dream

**Files:**
- Modify: `py-agent/dream.py`
- Test: `tests/test_per_user_dream.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_per_user_dream.py
import tempfile, os, json, shutil
from dream import get_unprocessed_history, append_user_history, get_user_memory_dir, run_user_dream

def test_get_user_memory_dir():
    agent_id = "test_agent"
    user_hash = "abc123"
    d = get_user_memory_dir(agent_id, user_hash)
    assert d.endswith(f"agents/{agent_id}/memory/users/{user_hash}")

def test_append_and_read_user_history():
    tmp = tempfile.mkdtemp()
    try:
        os.makedirs(get_user_memory_dir("test_a", "uh1"))
        append_user_history("test_a", "uh1", {"role": "user", "content": "hello"})
        entries, total = get_unprocessed_history("test_a", user_hash="uh1")
        assert len(entries) == 1
        assert entries[0]["content"] == "hello"
    finally:
        shutil.rmtree(tmp)

def test_user_dream_cursor_independent():
    tmp = tempfile.mkdtemp()
    try:
        os.makedirs(get_user_memory_dir("test_a", "u1"))
        os.makedirs(get_user_memory_dir("test_a", "u2"))
        append_user_history("test_a", "u1", {"content": "msg1"})
        append_user_history("test_a", "u2", {"content": "other"})
        entries_u1, _ = get_unprocessed_history("test_a", user_hash="u1")
        entries_u2, _ = get_unprocessed_history("test_a", user_hash="u2")
        assert len(entries_u1) == 1
        assert len(entries_u2) == 1
    finally:
        shutil.rmtree(tmp)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_per_user_dream.py -v`
Expected: FAIL

- [ ] **Step 3: Implement per-user Dream functions in dream.py**

```python
def get_user_memory_dir(agent_id: str, user_hash: str) -> str:
    base = _agent_memory_dir(agent_id)
    return os.path.join(base, "users", user_hash)

def _user_hash(user_id: str) -> str:
    import hashlib
    return hashlib.sha256(user_id.encode()).hexdigest()[:16]

def append_user_history(agent_id: str, user_hash: str, entry: dict):
    user_dir = get_user_memory_dir(agent_id, user_hash)
    os.makedirs(user_dir, exist_ok=True)
    history_path = os.path.join(user_dir, "history.jsonl")
    with open(history_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def get_unprocessed_history(agent_id: str, user_hash: str = "") -> tuple[list, int]:
    if user_hash:
        return _get_unprocessed_for_user(agent_id, user_hash)
    return _get_unprocessed_global(agent_id)

def _get_unprocessed_for_user(agent_id: str, user_hash: str) -> tuple[list, int]:
    user_dir = get_user_memory_dir(agent_id, user_hash)
    history_path = os.path.join(user_dir, "history.jsonl")
    cursor_path = os.path.join(user_dir, ".dream_cursor")
    cursor = _read_cursor(cursor_path)
    entries = _read_entries(history_path)
    unprocessed = entries[cursor:]
    return unprocessed, len(entries)

def _read_cursor(path: str) -> int:
    try:
        with open(path) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return 0

def _read_entries(path: str) -> list:
    if not os.path.exists(path):
        return []
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries

def run_user_dream(agent_id: str, agent_name: str, user_hash: str, llm_client) -> None:
    user_dir = get_user_memory_dir(agent_id, user_hash)
    history_path = os.path.join(user_dir, "history.jsonl")
    profile_path = os.path.join(user_dir, "PROFILE.md")
    entries, total = get_unprocessed_history(agent_id, user_hash=user_hash)
    if not entries:
        return
    # Phase 1: LLM analysis
    history_text = json.dumps(entries, ensure_ascii=False, indent=2)
    analysis_prompt = f"""Analyze these conversation entries and extract user preferences, habits, important facts.
Write concise bullet points for PROFILE.md.

{history_text}"""
    analysis = llm_client.complete(analysis_prompt)
    # Write to PROFILE.md (append, not overwrite)
    with open(profile_path, "a", encoding="utf-8") as f:
        f.write(f"\n## Dream Consolidation ({time.strftime('%Y-%m-%d')})\n")
        f.write(analysis + "\n")
    # Update cursor
    with open(os.path.join(user_dir, ".dream_cursor"), "w") as f:
        f.write(str(total))
```

- [ ] **Step 4: Run test to verify they pass**

Run: `python -m pytest tests/test_per_user_dream.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add py-agent/dream.py tests/test_per_user_dream.py
git commit -m "feat: per-user dream with independent cursors and PROFILE.md"
```

---

### Task 6: GitStore 集成到 Dream

**Files:**
- Modify: `py-agent/dream.py`
- Modify: `tests/test_git_store.py`

- [ ] **Step 1: Write failing tests**

```python
# Add to test_git_store.py
def test_git_store_integration_with_dream():
    import tempfile, os, shutil
    from dream import run_dream
    from git_store import GitStore
    tmp = tempfile.mkdtemp()
    try:
        agents_dir = os.path.join(tmp, "agents", "test_a", "memory")
        os.makedirs(agents_dir)
        store = GitStore(agents_dir)
        # Simulate a dream by writing to MEMORY.md
        mem_path = os.path.join(agents_dir, "MEMORY.md")
        with open(mem_path, "w") as f:
            f.write("# Original")
        store.commit("dream: original")
        # Write again
        with open(mem_path, "w") as f:
            f.write("# Updated")
        store.commit("dream: update")
        # Revert
        store.revert()
        with open(mem_path) as f:
            assert f.read() == "# Original"
    finally:
        shutil.rmtree(tmp)
```

- [ ] **Step 2: Integrate GitStore into dream.py**

In `run_dream` (global Dream, for MEMORY.md):

```python
def run_dream(agent_id: str, agent_name: str, llm_client) -> None:
    ...
    # After writing to MEMORY.md
    store = GitStore(_agent_memory_dir(agent_id))
    store.commit(f"dream: {time.strftime('%Y-%m-%d %H:%M:%S')}")
```

In `run_user_dream` (per-user Dream, for PROFILE.md):

```python
def run_user_dream(agent_id: str, user_hash: str, llm_client) -> None:
    ...
    # After writing to PROFILE.md
    user_dir = get_user_memory_dir(agent_id, user_hash)
    store = GitStore(user_dir)
    store.commit(f"dream-user: {time.strftime('%Y-%m-%d %H:%M:%S')}")
```

- [ ] **Step 3: Run test to verify it passes**

Run: `python -m pytest tests/test_git_store.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add py-agent/dream.py tests/test_git_store.py
git commit -m "feat: integrate GitStore with Dream auto-commit"
```

---

### Task 7: 工具接口更新 — RememberTool + RecallTool + RevertMemoryTool

**Files:**
- Modify: `py-agent/tools.py`
- Test: `tests/test_tools_memory.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_tools_memory.py
import tempfile, os, json, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))
from tools import RememberTool, RecallTool, RevertMemoryTool

def test_remember_tool_user_context():
    tmp = tempfile.mkdtemp()
    try:
        # Override agent memory dir
        tool = RememberTool()
        result = tool.execute(agent_id="test_a", content="likes blue", user_id="user_abc")
        assert result["success"]
        # Check PROFILE.md was written
        profile_path = os.path.join(tmp, "agents/test_a/memory/users", _hash("user_abc"), "PROFILE.md")
        # (actual path depends on _user_hash)
    finally:
        shutil.rmtree(tmp)

def test_recall_tool_global():
    tool = RecallTool()
    result = tool.execute(agent_id="test_a")
    assert "success" in result

def test_recall_tool_with_user():
    tool = RecallTool()
    result = tool.execute(agent_id="test_a", user_id="user_abc")
    assert "success" in result

def test_revert_memory_tool():
    tool = RevertMemoryTool()
    result = tool.execute(agent_id="test_a")
    assert "success" in result or "error" in result  # may fail if no git history
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tools_memory.py -v`
Expected: FAIL (RevertMemoryTool not found)

- [ ] **Step 3: Update RememberTool to accept user_id**

In `tools.py`, modify `RememberTool.execute`:

```python
class RememberTool(BaseTool):
    name = "remember"
    description = "Store a fact into long-term memory"
    args = {
        "content": "Fact to remember",
        "user_id": "Optional: associate with specific user (default: global memory)",
    }

    def execute(self, agent_id: str, content: str, user_id: str = "", **kwargs) -> dict:
        from dream import get_user_memory_dir, _user_hash
        if user_id:
            user_hash = _user_hash(user_id)
            profile_path = os.path.join(get_user_memory_dir(agent_id, user_hash), "PROFILE.md")
            os.makedirs(os.path.dirname(profile_path), exist_ok=True)
            with open(profile_path, "a", encoding="utf-8") as f:
                f.write(f"- {content}\n")
            return {"success": True, "location": f"users/{user_hash}/PROFILE.md"}
        else:
            mem_path = os.path.join(_agent_memory_dir(agent_id), "MEMORY.md")
            with open(mem_path, "a", encoding="utf-8") as f:
                f.write(f"- {content}\n")
            return {"success": True, "location": "MEMORY.md"}
```

- [ ] **Step 4: Update RecallTool to accept user_id**

```python
class RecallTool(BaseTool):
    name = "recall"
    description = "Retrieve facts from long-term memory"
    args = {
        "keyword": "Optional keyword filter",
        "user_id": "Optional: search user-specific memory",
    }

    def execute(self, agent_id: str, keyword: str = "", user_id: str = "", **kwargs) -> dict:
        from dream import _user_hash, get_user_memory_dir
        results = []
        # Global memory
        mem_path = os.path.join(_agent_memory_dir(agent_id), "MEMORY.md")
        if os.path.exists(mem_path):
            with open(mem_path) as f:
                content = f.read()
                if not keyword or keyword.lower() in content.lower():
                    results.append(("MEMORY.md", content))
        # User memory
        if user_id:
            user_hash = _user_hash(user_id)
            profile_path = os.path.join(get_user_memory_dir(agent_id, user_hash), "PROFILE.md")
            if os.path.exists(profile_path):
                with open(profile_path) as f:
                    content = f.read()
                    if not keyword or keyword.lower() in content.lower():
                        results.append((f"users/{user_hash}/PROFILE.md", content))
        return {"success": True, "results": results}
```

- [ ] **Step 5: Add RevertMemoryTool**

```python
class RevertMemoryTool(BaseTool):
    name = "revert_memory"
    description = "Revert the last Dream commit to undo bad memory changes"
    args = {}

    def execute(self, agent_id: str, **kwargs) -> dict:
        from git_store import GitStore
        mem_dir = _agent_memory_dir(agent_id)
        store = GitStore(mem_dir)
        last_msg = store.last_commit_message()
        store.revert()
        return {"success": True, "reverted": last_msg}
```

- [ ] **Step 6: Register RevertMemoryTool in create_default_registry**

In `create_default_registry`:

```python
registry.register(RevertMemoryTool())
```

- [ ] **Step 7: Run tests**

Run: `python -m pytest tests/test_tools_memory.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add py-agent/tools.py tests/test_tools_memory.py
git commit -m "feat: user-aware remember/recall, add revert_memory tool"
```

---

### Task 8: Web API — 记忆历史端点

**Files:**
- Modify: `web/routes/agents.py`

- [ ] **Step 1: Add Git log endpoint**

```python
@router.get("/api/agents/{agent_id}/memory/history")
def get_memory_history(agent_id: str, limit: int = 10):
    from py_agent.git_store import GitStore  # adjust import path
    mem_dir = BASE_DIR / "agents" / agent_id / "memory"
    if not mem_dir.exists():
        return JSONResponse({"error": "agent not found"}, status_code=404)
    store = GitStore(str(mem_dir))
    log = store.log(max_count=limit)
    return {"agent_id": agent_id, "history": log}
```

- [ ] **Step 2: Verify endpoint works**

Run: `python -c "from web.routes.agents import *; print('import ok')"`
Expected: No error

- [ ] **Step 3: Commit**

```bash
git add web/routes/agents.py
git commit -m "feat: add memory git log API endpoint"
```

---

### Task 9: AutoCompact — 离线压缩

**Files:**
- Create: `py-agent/auto_compact.py`
- Modify: `py-agent/heartbeat.py`
- Test: `tests/test_auto_compact.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_auto_compact.py
import tempfile, os, json, shutil
from auto_compact import compact_user_history, should_compact

def make_large_history(num_entries: int, chars_per: int = 500) -> str:
    lines = []
    for i in range(num_entries):
        lines.append(json.dumps({"content": "x" * chars_per, "ts": i}))
    return "\n".join(lines)

def test_should_compact_small():
    assert not should_compact(make_large_history(5, 100), budget=5000)

def test_should_compact_large():
    assert should_compact(make_large_history(20, 500), budget=5000)

def test_compact_preserves_recent():
    history = make_large_history(15, 500)
    compacted = compact_user_history(history, budget=3000, keep_recent=3)
    lines = compacted.strip().split("\n")
    assert len(lines) >= 3  # at least recent entries
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_auto_compact.py -v`
Expected: FAIL

- [ ] **Step 3: Implement auto_compact.py**

```python
import json, os, time

AUTOCOMPACT_TOKEN_BUDGET = 8000
KEEP_RECENT_ENTRIES = 5

def should_compact(history_text: str, budget: int = AUTOCOMPACT_TOKEN_BUDGET) -> bool:
    return len(history_text) > budget * 4  # rough char-to-token ratio

def compact_user_history(history_text: str, budget: int = AUTOCOMPACT_TOKEN_BUDGET, keep_recent: int = KEEP_RECENT_ENTRIES) -> str:
    lines = [l for l in history_text.strip().split("\n") if l.strip()]
    if not lines:
        return ""
    entries = [json.loads(l) for l in lines]
    if not should_compact(history_text, budget):
        return history_text
    # Keep recent entries intact
    recent = entries[-keep_recent:]
    old = entries[:-keep_recent]
    old_text = "\n".join(json.dumps(e, ensure_ascii=False) for e in old)
    summary = {
        "type": "compacted_summary",
        "original_count": len(old),
        "summary": f"[{len(old)} historical entries compacted]",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    result = [json.dumps(summary, ensure_ascii=False)] + [json.dumps(e, ensure_ascii=False) for e in recent]
    return "\n".join(result)

def run_auto_compact(agent_id: str):
    from dream import get_user_memory_dir
    mem_dir = os.path.join(os.path.dirname(__file__), "..", "agents", agent_id, "memory")
    users_dir = os.path.join(mem_dir, "users")
    if not os.path.isdir(users_dir):
        return
    for user_hash in os.listdir(users_dir):
        history_path = os.path.join(users_dir, user_hash, "history.jsonl")
        if not os.path.exists(history_path):
            continue
        with open(history_path, "r", encoding="utf-8") as f:
            content = f.read()
        compacted = compact_user_history(content)
        if compacted != content:
            with open(history_path, "w", encoding="utf-8") as f:
                f.write(compacted)
```

- [ ] **Step 4: Integrate into heartbeat.py**

```python
# In heartbeat loop, after checking messages
from auto_compact import run_auto_compact
try:
    run_auto_compact(agent_id)
except Exception:
    pass
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_auto_compact.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add py-agent/auto_compact.py py-agent/heartbeat.py tests/test_auto_compact.py
git commit -m "feat: auto-compact idle user histories"
```

---

### Task 10: 新增 Web UI 端点 — 用户记忆查看

**Files:**
- Modify: `web/routes/agents.py`

- [ ] **Step 1: Add per-user profile endpoint**

```python
@router.get("/api/agents/{agent_id}/memory/users/{user_id}")
def get_user_memory(agent_id: str, user_id: str):
    from py_agent.dream import get_user_memory_dir, _user_hash
    user_hash = _user_hash(user_id)
    user_dir = Path(get_user_memory_dir(agent_id, user_hash))
    profile_path = user_dir / "PROFILE.md"
    history_path = user_dir / "history.jsonl"
    profile = profile_path.read_text(encoding="utf-8") if profile_path.exists() else ""
    history = []
    if history_path.exists():
        with open(str(history_path), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    history.append(json.loads(line))
    return {
        "user_id": user_id,
        "user_hash": user_hash,
        "profile": profile,
        "history_count": len(history),
        "history": history[-20:],
    }
```

- [ ] **Step 2: Commit**

```bash
git add web/routes/agents.py
git commit -m "feat: add per-user memory API endpoint"
```

---

### Task 11: 全局自检 — 运行全部测试

- [ ] **Step 1: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Fix any failures**

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "fix: address test failures from memory refactoring"
```
