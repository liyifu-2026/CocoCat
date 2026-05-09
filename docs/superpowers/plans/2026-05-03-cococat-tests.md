# Testing System Plan

**Goal:** Set up pytest and write tests for core Python modules.

**Scope (4 modules → MVP):** `tools.py` (16 tools), `context.py`, `scene_router.py`, `channel.py`. No LLM-dependent tests (avoid API costs). No agent_loop tests (needs mocking infrastructure).

---

### Task 1: pytest setup + context + channel tests

**Files:**
- Create: `py-agent/requirements-dev.txt`
- Create: `tests/test_context.py`
- Create: `tests/test_channel.py`

- [ ] **Step 1: Create requirements-dev.txt**

```
pytest>=7.0.0
```

- [ ] **Step 2: Create test dir**

```powershell
New-Item -ItemType Directory -Force -Path "C:\Users\12991\Desktop\Cococlaw\tests" | Out-Null
New-Item -ItemType File -Force -Path "C:\Users\12991\Desktop\Cococlaw\tests\__init__.py" | Out-Null
```

- [ ] **Step 3: Write test_context.py**

Tests for `build_system_prompt`, `build_tool_descriptions`, `load_scene_context`, `load_env_skills`, `load_agent_memory`, `load_agent_skills`, `load_mounted_kbs`.

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))

from context import build_system_prompt, build_tool_descriptions, load_scene_context


def test_build_system_prompt_contains_identity():
    prompt = build_system_prompt(agent_id="test-id", agent_name="TestAgent")
    assert "test-id" in prompt
    assert "TestAgent" in prompt


def test_build_system_prompt_contains_scene():
    prompt = build_system_prompt(scene_name="TestScene", scene_context="Test context")
    assert "TestScene" in prompt
    assert "Test context" in prompt


def test_build_system_prompt_contains_memory():
    prompt = build_system_prompt(agent_memory="Some remembered facts")
    assert "Some remembered facts" in prompt


def test_build_system_prompt_contains_skills():
    prompt = build_system_prompt(agent_skills="communication skill", env_skills="code_review skill")
    assert "communication skill" in prompt
    assert "code_review skill" in prompt


def test_build_tool_descriptions():
    tools = [
        {"function": {"name": "test_tool", "description": "A test tool",
                       "parameters": {"type": "object", "properties": {"p": {"description": "a param"}}, "required": ["p"]}}}
    ]
    desc = build_tool_descriptions(tools)
    assert "test_tool" in desc
    assert "A test tool" in desc


def test_load_scene_context_nonexistent():
    name, ctx = load_scene_context("nonexistent_scene_xyz")
    assert name == "nonexistent_scene_xyz"
    assert ctx == ""
```

- [ ] **Step 4: Write test_channel.py**

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))

from channel import Channel, ChatMessage


def test_chat_message_creation():
    msg = ChatMessage(channel_type="test", scene_id="s1", user_id="u1", content="hello")
    assert msg.channel_type == "test"
    assert msg.scene_id == "s1"
    assert msg.user_id == "u1"
    assert msg.content == "hello"


def test_chat_message_to_dict():
    msg = ChatMessage(channel_type="test", scene_id="s1", user_id="u1", content="hello")
    d = msg.to_dict()
    assert d["channel_type"] == "test"
    assert d["content"] == "hello"


def test_chat_message_defaults():
    msg = ChatMessage(channel_type="t", scene_id="s", user_id="u", content="c")
    assert msg.msg_type == "text"
    assert msg.msg_id != ""


def test_channel_base_start_raises():
    ch = Channel()
    try:
        ch.start("test", {})
        assert False, "should have raised"
    except NotImplementedError:
        assert True


def test_channel_base_send_raises():
    ch = Channel()
    try:
        ch.send("reply", "user1")
        assert False, "should have raised"
    except NotImplementedError:
        assert True
```

- [ ] **Step 5: Run tests**

```powershell
pip install pytest -q
python -m pytest tests/test_context.py tests/test_channel.py -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add py-agent/requirements-dev.txt tests/
git commit -m "test: add pytest setup + context + channel tests"
```

---

### Task 2: scene_router + tools tests

**Files:**
- Create: `tests/test_scene_router.py`
- Create: `tests/test_tools.py`

- [ ] **Step 1: Write test_scene_router.py**

```python
import sys, os, tempfile, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))

# Monkey-patch scene_router to use temp dir
import scene_router
original_dir = os.path.dirname(scene_router.__file__)


def test_store_and_get_history():
    with tempfile.TemporaryDirectory() as tmp:
        # Override scene_router's base path
        scene_router._BASE = tmp
        scene_router.store_message("test-scene", "user1", {"content": "hello", "direction": "incoming", "channel_type": "web"})
        scene_router.store_message("test-scene", "user1", {"content": "hi back", "direction": "outgoing", "channel_type": "web"})
        history = scene_router.get_history("test-scene", "user1")
        assert len(history) == 2
        assert history[0]["content"] == "hello"
        assert history[1]["content"] == "hi back"


def test_get_history_empty():
    with tempfile.TemporaryDirectory() as tmp:
        scene_router._BASE = tmp
        history = scene_router.get_history("nonexistent", "user1")
        assert history == []


def test_store_message_creates_dir():
    with tempfile.TemporaryDirectory() as tmp:
        scene_router._BASE = tmp
        scene_router.store_message("s1", "u1", {"content": "test", "direction": "incoming", "channel_type": "web"})
        assert os.path.exists(os.path.join(tmp, "scenes", "s1", "users", "u1", "history.jsonl"))
```

- [ ] **Step 2: Write test_tools.py** (basic tool interface tests, no LLM)

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))

from tools import (ReadFileTool, WriteFileTool, ExecCommandTool, GlobSearchTool,
                   GrepSearchTool, SubAgentTool, DispatchTaskTool, HireAgentTool,
                   SearchKbTool, RememberTool, RecallTool, DreamTool,
                   IngestToKbTool, WebFetchTool, WebSearchTool, EditFileTool,
                   AskUserTool, ToolRegistry, create_default_registry)


def test_all_tools_have_names():
    r = create_default_registry()
    names = [t.name for t in r._tools.values()]
    assert len(names) >= 12  # At least 12 tools
    assert "read_file" in names
    assert "write_file" in names
    assert "exec_command" in names
    assert "edit_file" in names
    assert "web_fetch" in names
    assert "web_search" in names


def test_tool_to_openai_schema():
    tool = ReadFileTool()
    schema = tool.to_openai_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "read_file"
    assert "parameters" in schema["function"]


def test_tool_registry_register_and_get():
    r = ToolRegistry()
    t = ReadFileTool()
    r.register(t)
    assert r.get("read_file") is t
    assert r.get("nonexistent") is None


def test_tool_registry_get_definitions():
    r = ToolRegistry()
    r.register(ReadFileTool())
    defs = r.get_definitions()
    assert len(defs) == 1
    assert defs[0]["function"]["name"] == "read_file"


def test_execute_unknown_tool():
    r = ToolRegistry()
    result = r.execute("unknown_tool", {})
    assert "unknown" in result


def test_read_file_not_found():
    t = ReadFileTool()
    result = t.execute(path="/nonexistent/path/file.txt")
    assert "not found" in result


def test_write_file_creates_dirs(tmp_path):
    t = WriteFileTool()
    p = os.path.join(str(tmp_path), "sub", "test.txt")
    result = t.execute(path=p, content="hello")
    assert "Successfully wrote" in result
    assert os.path.exists(p)
    with open(p) as f:
        assert f.read() == "hello"
```

- [ ] **Step 3: Run all tests**

```powershell
python -m pytest tests/ -v
```

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "test: add scene_router and tools tests"
```
