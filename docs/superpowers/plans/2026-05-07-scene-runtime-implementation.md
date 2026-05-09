# SceneRuntime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add SceneManager + SceneRuntime for dynamic agent-to-scene assignment with lifecycle management and resource isolation.

**Architecture:** Five sequential tasks: SceneConfig data loader → SceneRuntime state machine → SceneManager singleton → test suite → entry_manager / context.py integration. Agent communication stays mailbox-based.

**Tech Stack:** Python 3.10+, dataclasses, threading, enum, json

---

### Task 1: Create SceneConfig

**Files:**
- Create: `py-agent/scene_config.py`

- [ ] **Step 1: Write scene_config.py**

```python
"""Scene configuration loader — reads scenes/{scene_id}/ config files."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ChannelConfig:
    channel_type: str = ""
    enabled: bool = True
    config: dict = field(default_factory=dict)


@dataclass
class SceneConfig:
    scene_id: str = ""
    name: str = ""
    context: str = ""
    agent_id: Optional[str] = None
    mounted_kbs: list[str] = field(default_factory=list)
    env_skills: list[str] = field(default_factory=list)
    channels: list[ChannelConfig] = field(default_factory=list)
    display: dict = field(default_factory=dict)


def _scenes_dir() -> str:
    return os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scenes")
    )


def load_scene_config(scene_id: str) -> Optional[SceneConfig]:
    """Load and return SceneConfig from scenes/{scene_id}/ directory.

    Returns None if scene directory doesn't exist.
    """
    scene_dir = os.path.join(_scenes_dir(), scene_id)
    if not os.path.isdir(scene_dir):
        return None

    config = SceneConfig(scene_id=scene_id)

    # Load CONTEXT.md
    context_path = os.path.join(scene_dir, "CONTEXT.md")
    if os.path.exists(context_path):
        with open(context_path, "r", encoding="utf-8") as f:
            config.context = f.read()
        first_line = config.context.strip().split("\n")[0].strip()
        if first_line.startswith("# "):
            config.name = first_line[2:].strip()
        else:
            config.name = scene_id
    else:
        config.name = scene_id

    # Load mounted_kbs.json
    kb_path = os.path.join(scene_dir, "mounted_kbs.json")
    if os.path.exists(kb_path):
        try:
            with open(kb_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                config.mounted_kbs = data.get("mounted", [])
        except Exception:
            pass

    # Load skills/manifest.json
    manifest_path = os.path.join(scene_dir, "skills", "manifest.json")
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                config.env_skills = data.get("env_skills", [])
        except Exception:
            pass

    # Load entries.json
    entries_path = os.path.join(scene_dir, "entries.json")
    if os.path.exists(entries_path):
        try:
            with open(entries_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for entry in data.get("entries", []):
                    cfg = ChannelConfig(
                        channel_type=entry.get("channel", ""),
                        enabled=entry.get("enabled", True),
                        config=entry.get("config", {}),
                    )
                    config.channels.append(cfg)
        except Exception:
            pass

    # Load display.json
    display_path = os.path.join(scene_dir, "display.json")
    if os.path.exists(display_path):
        try:
            with open(display_path, "r", encoding="utf-8") as f:
                config.display = json.load(f)
        except Exception:
            pass

    return config


def list_scenes() -> list[str]:
    """Return all scene IDs (directory names under scenes/)."""
    sdir = _scenes_dir()
    if not os.path.isdir(sdir):
        return []
    return sorted(
        d for d in os.listdir(sdir)
        if os.path.isdir(os.path.join(sdir, d)) and not d.startswith("_")
    )
```

- [ ] **Step 2: Test**

```bash
python3 -c "
import sys; sys.path.insert(0,'py-agent')
from scene_config import load_scene_config, list_scenes
scenes = list_scenes()
print(f'Found {len(scenes)} scenes: {scenes}')
cfg = load_scene_config('default')
assert cfg is not None
assert cfg.scene_id == 'default'
assert cfg.name != ''
assert cfg.context != ''
print(f'Default scene: name={cfg.name}, kbs={cfg.mounted_kbs}, skills={cfg.env_skills}')
cfg2 = load_scene_config('nonexistent')
assert cfg2 is None
print('=== scene_config OK ===')
"
```

- [ ] **Step 3: Commit**

```bash
git add py-agent/scene_config.py
git commit -m "feat: add SceneConfig loader from scenes/{id}/ directory"
```

---

### Task 2: Create AgentHandle

**Files:**
- Create: `py-agent/agent_handle.py`

- [ ] **Step 1: Write agent_handle.py**

```python
"""AgentHandle — runtime reference to an agent process via mailbox communication."""
from __future__ import annotations

import json
import os
import logging
from datetime import datetime

logger = logging.getLogger("cococat.agent_handle")


def _mailbox_dir() -> str:
    return os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agents", "mailbox")
    )


class AgentHandle:
    """Runtime handle to an agent, communicating via mailbox files.

    The agent process polls agents/mailbox/{agent_id}/inbox.jsonl for new messages.
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.scene_id: str | None = None

    @property
    def is_assigned(self) -> bool:
        return self.scene_id is not None

    def assign_to_scene(self, scene_id: str, scene_context: str):
        """Send a scene_assign command to the agent's mailbox."""
        self.scene_id = scene_id
        self._send_command("scene_assign", {
            "scene_id": scene_id,
            "context": scene_context,
        })
        logger.info(f"Agent {self.agent_id} assigned to scene {scene_id}")

    def release(self):
        """Send a scene_release command and clear assignment."""
        if self.scene_id:
            self._send_command("scene_release", {"scene_id": self.scene_id})
            logger.info(f"Agent {self.agent_id} released from scene {self.scene_id}")
            self.scene_id = None

    def send_message(self, channel: str, user_id: str, content: str) -> str | None:
        """Write a user message to the agent's inbox. Returns message_id."""
        mailbox_dir = os.path.join(_mailbox_dir(), self.agent_id)
        os.makedirs(mailbox_dir, exist_ok=True)
        inbox_path = os.path.join(mailbox_dir, "inbox.jsonl")

        from sandbox import FileLock
        entry = {
            "from": f"scene:{self.scene_id}:{channel}:{user_id}",
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "status": "unread",
            "scene_id": self.scene_id,
            "channel": channel,
            "external_user": user_id,
        }
        with FileLock(inbox_path):
            with open(inbox_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry.get("from")

    def _send_command(self, command: str, data: dict):
        """Write a system command to the agent's control mailbox."""
        mailbox_dir = os.path.join(_mailbox_dir(), self.agent_id)
        os.makedirs(mailbox_dir, exist_ok=True)
        control_path = os.path.join(mailbox_dir, "control.jsonl")

        from sandbox import FileLock
        entry = {
            "command": command,
            "data": data,
            "timestamp": datetime.now().isoformat(),
        }
        with FileLock(control_path):
            with open(control_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
```

- [ ] **Step 2: Test import**

```bash
python3 -c "
import sys; sys.path.insert(0,'py-agent')
from agent_handle import AgentHandle
h = AgentHandle('test_agent')
assert h.agent_id == 'test_agent'
assert h.is_assigned == False
print('=== agent_handle OK ===')
"
```

- [ ] **Step 3: Commit**

```bash
git add py-agent/agent_handle.py
git commit -m "feat: add AgentHandle with mailbox-based scene assign/release"
```

---

### Task 3: Create SceneManager + SceneRuntime

**Files:**
- Create: `py-agent/scene_manager.py`

- [ ] **Step 1: Write scene_manager.py**

```python
"""SceneManager — manages SceneRuntime lifecycle and agent assignment."""
from __future__ import annotations

import logging
from enum import Enum
from threading import Lock

from scene_config import SceneConfig, load_scene_config
from agent_handle import AgentHandle

logger = logging.getLogger("cococat.scene_manager")


class SceneState(Enum):
    IDLE = "idle"
    ACTIVATING = "activating"
    ACTIVE = "active"
    DEACTIVATING = "deactivating"


class SceneRuntime:
    """Runtime instance of a scene with lifecycle management."""

    def __init__(self, config: SceneConfig):
        self.config = config
        self.state = SceneState.IDLE
        self.agent_handle: AgentHandle | None = None
        self.channels: list = []  # channel instances (set by entry_manager)

    @property
    def scene_id(self) -> str:
        return self.config.scene_id

    @property
    def agent_id(self) -> str | None:
        return self.agent_handle.agent_id if self.agent_handle else None

    def assign_agent(self, agent_id: str) -> bool:
        """Assign an agent to this scene. Returns True on success."""
        if self.state not in (SceneState.IDLE, SceneState.ACTIVE):
            logger.warning(f"Cannot assign: scene {self.scene_id} is {self.state.value}")
            return False
        self.state = SceneState.ACTIVATING
        self.agent_handle = AgentHandle(agent_id)
        self.agent_handle.assign_to_scene(self.scene_id, self.config.context)
        self.state = SceneState.ACTIVE
        logger.info(f"Scene {self.scene_id} activated with agent {agent_id}")
        return True

    def unassign_agent(self) -> bool:
        """Unassign the current agent. Returns True on success."""
        if self.state != SceneState.ACTIVE:
            logger.warning(f"Cannot unassign: scene {self.scene_id} is {self.state.value}")
            return False
        self.state = SceneState.DEACTIVATING
        for ch in self.channels:
            try:
                ch.stop()
            except Exception as e:
                logger.warning(f"Error stopping channel: {e}")
        self.channels.clear()
        if self.agent_handle:
            self.agent_handle.release()
            self.agent_handle = None
        self.state = SceneState.IDLE
        logger.info(f"Scene {self.scene_id} deactivated")
        return True


class SceneManager:
    """Singleton — manages all scene runtimes."""

    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._runtimes = {}
        return cls._instance

    def get_or_create(self, scene_id: str) -> SceneRuntime | None:
        """Get existing runtime or create from config. Returns None if scene unknown."""
        if scene_id in self._runtimes:
            return self._runtimes[scene_id]
        config = load_scene_config(scene_id)
        if config is None:
            return None
        runtime = SceneRuntime(config)
        self._runtimes[scene_id] = runtime
        return runtime

    def get_runtime(self, scene_id: str) -> SceneRuntime | None:
        return self._runtimes.get(scene_id)

    def assign_agent(self, scene_id: str, agent_id: str) -> bool:
        runtime = self.get_or_create(scene_id)
        if runtime is None:
            logger.error(f"Scene {scene_id} not found")
            return False
        return runtime.assign_agent(agent_id)

    def unassign_agent(self, scene_id: str) -> bool:
        runtime = self.get_runtime(scene_id)
        if runtime is None:
            return False
        return runtime.unassign_agent()

    def list_active(self) -> list[str]:
        return [s for s, r in self._runtimes.items() if r.state == SceneState.ACTIVE]

    def list_idle(self) -> list[str]:
        return [s for s, r in self._runtimes.items() if r.state == SceneState.IDLE]
```

- [ ] **Step 2: Test basic lifecycle**

```bash
python3 -c "
import sys; sys.path.insert(0,'py-agent')
from scene_manager import SceneManager, SceneState

mgr = SceneManager()
rt = mgr.get_or_create('default')
assert rt is not None
assert rt.state == SceneState.IDLE
print(f'Scene {rt.scene_id} loaded, state={rt.state.value}')

# Assign
ok = rt.assign_agent('test_agent')
assert ok
assert rt.state == SceneState.ACTIVE
assert rt.agent_id == 'test_agent'
print(f'Assigned agent {rt.agent_id}, state={rt.state.value}')

# Unassign
ok = rt.unassign_agent()
assert ok
assert rt.state == SceneState.IDLE
assert rt.agent_id is None
print(f'Unassigned, state={rt.state.value}')

print('=== SceneManager OK ===')
"
```

- [ ] **Step 3: Commit**

```bash
git add py-agent/scene_manager.py
git commit -m "feat: add SceneManager + SceneRuntime with lifecycle state machine"
```

---

### Task 4: Write tests

**Files:**
- Create: `tests/test_scene.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for SceneConfig, SceneManager, SceneRuntime, AgentHandle."""
import sys, os, json, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))

from scene_config import load_scene_config, list_scenes
from scene_manager import SceneManager, SceneRuntime, SceneState


def test_list_scenes():
    scenes = list_scenes()
    assert "default" in scenes
    assert "development" in scenes


def test_load_default_scene():
    cfg = load_scene_config("default")
    assert cfg is not None
    assert cfg.scene_id == "default"
    assert cfg.name != ""
    assert cfg.context != ""
    assert isinstance(cfg.mounted_kbs, list)
    assert isinstance(cfg.env_skills, list)


def test_load_nonexistent_scene():
    assert load_scene_config("nonexistent_12345") is None


def test_scene_runtime_initial_state():
    from scene_config import load_scene_config
    cfg = load_scene_config("default")
    rt = SceneRuntime(cfg)
    assert rt.state == SceneState.IDLE
    assert rt.agent_id is None


def test_scene_runtime_assign():
    from scene_config import load_scene_config
    cfg = load_scene_config("default")
    rt = SceneRuntime(cfg)
    ok = rt.assign_agent("test_agent")
    assert ok
    assert rt.state == SceneState.ACTIVE
    assert rt.agent_id == "test_agent"


def test_scene_runtime_unassign():
    from scene_config import load_scene_config
    cfg = load_scene_config("default")
    rt = SceneRuntime(cfg)
    rt.assign_agent("test_agent")
    ok = rt.unassign_agent()
    assert ok
    assert rt.state == SceneState.IDLE
    assert rt.agent_id is None


def test_scene_manager_singleton():
    m1 = SceneManager()
    m2 = SceneManager()
    assert m1 is m2


def test_scene_manager_get_or_create():
    mgr = SceneManager()
    rt = mgr.get_or_create("default")
    assert rt is not None
    assert rt.scene_id == "default"


def test_scene_manager_get_or_create_unknown():
    mgr = SceneManager()
    assert mgr.get_or_create("__nonexistent__") is None


def test_scene_manager_assign_unassign():
    mgr = SceneManager()
    ok = mgr.assign_agent("default", "test_agent")
    assert ok
    rt = mgr.get_runtime("default")
    assert rt.state == SceneState.ACTIVE
    ok = mgr.unassign_agent("default")
    assert ok
    assert rt.state == SceneState.IDLE


def test_scene_manager_list_active():
    mgr = SceneManager()
    mgr.assign_agent("development", "test_agent2")
    active = mgr.list_active()
    assert "development" in active
    mgr.unassign_agent("development")
    active = mgr.list_active()
    assert "development" not in active


def test_agent_handle_assign_release():
    from agent_handle import AgentHandle
    h = AgentHandle("test_agent")
    assert h.is_assigned == False
    h.assign_to_scene("test_scene", "context")
    assert h.is_assigned == True
    assert h.scene_id == "test_scene"
    h.release()
    assert h.is_assigned == False
    assert h.scene_id is None
```

- [ ] **Step 2: Run tests**

```bash
python3 -m pytest tests/test_scene.py -v --tb=short
```
Expected: All passing.

- [ ] **Step 3: Commit**

```bash
git add tests/test_scene.py
git commit -m "test: add SceneConfig, SceneManager, SceneRuntime, AgentHandle tests"
```

---

### Task 5: Integrate with entry_manager

**Files:**
- Modify: `web/entry_manager.py` — use SceneRuntime lifecycle for channel management

- [ ] **Step 1: Update entry_manager.py**

Replace `start_agent_entries` and `start_scene_entries` with a SceneRuntime-aware flow:

```python
def start_all_entries():
    """Start all entries for all scenes via SceneRuntime."""
    from scene_manager import SceneManager
    from scene_config import list_scenes, load_scene_config

    mgr = SceneManager()

    for scene_id in list_scenes():
        config = load_scene_config(scene_id)
        if not config or not config.channels:
            continue
        runtime = mgr.get_or_create(scene_id)
        if runtime is None:
            continue
        _start_scene_channels(runtime)


def _start_scene_channels(runtime):
    """Start all enabled channels for a scene runtime."""
    from channels.channel_factory import create_channel

    for ch_cfg in runtime.config.channels:
        if not ch_cfg.enabled:
            continue
        if ch_cfg.channel_type == "web_api":
            print(f"[EntryManager] Web API for scene '{runtime.scene_id}' — handled by FastAPI")
            continue
        try:
            ch = create_channel(ch_cfg.channel_type)
            ch.on_message = lambda msg, s=runtime, ct=ch_cfg.channel_type: _route_to_scene(
                s, ct, msg.user_id, msg.content
            )
            ch.start(runtime.scene_id, ch_cfg.config)
            runtime.channels.append(ch)
            print(f"[EntryManager] {ch_cfg.channel_type} channel started for scene '{runtime.scene_id}'")
        except Exception as e:
            print(f"[EntryManager] Failed to start {ch_cfg.channel_type}: {e}")


def _route_to_scene(runtime: "SceneRuntime", channel_type: str, user_id: str, content: str):
    """Route a message to a scene's agent via its AgentHandle."""
    if runtime.state.name != "ACTIVE" or not runtime.agent_handle:
        print(f"[EntryManager] Scene '{runtime.scene_id}' not active, dropping message from {user_id}")
        return
    runtime.agent_handle.send_message(channel_type, user_id, content)
```

- [ ] **Step 2: Test import**

```bash
python3 -c "
import sys; sys.path.insert(0,'web'); sys.path.insert(0,'py-agent')
from entry_manager import start_all_entries, _route_to_scene
from scene_manager import SceneManager
print('=== entry_manager + SceneManager integration OK ===')
"
```

- [ ] **Step 3: Commit**

```bash
git add web/entry_manager.py
git commit -m "refactor: entry_manager uses SceneRuntime lifecycle for channel management"
```

---

### Task 6: Context.py scene-level KB filtering

**Files:**
- Modify: `py-agent/context.py` — `build_system_prompt` optionally filter KBs list

- [ ] **Step 1: Add scene-aware KB overview param**

The current `build_system_prompt` already accepts `knowledge_overview`. The change is at the caller side (AgentLoop) to pass only scene-mounted KBs. No change needed to `context.py` itself — the `load_knowledge_overview(scene_id)` function already filters by scene.

Verify:

```bash
python3 -c "
import sys; sys.path.insert(0,'py-agent')
from context import load_knowledge_overview
overview = load_knowledge_overview('development')
print(f'Development KBs: {overview[:100] if overview else \"(none)\"}')
"
```

- [ ] **Step 2: Ensure agent_loop.py passes scene_id to context builder**

Verify the integration point in AgentLoop:

```python
# agent_loop.py (already supports scene_name + scene_context)
# Verify knowledge_overview is also loaded per-scene:
from context import load_knowledge_overview, load_scene_context, load_env_skills

scene_name, scene_context = load_scene_context(self.scene_id)
env_skills = load_env_skills(self.scene_id)
knowledge = load_knowledge_overview(self.scene_id)

system_prompt = build_system_prompt(
    scene_name=scene_name,
    scene_context=scene_context,
    env_skills=env_skills,
    knowledge_overview=knowledge,
    ...
)
```

- [ ] **Step 3: Commit (if changes needed)**

```bash
git add py-agent/agent_loop.py  # if modified
git commit -m "fix: pass scene-filtered KB overview to agent system prompt"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- Task 1: SceneConfig loader (loads from scenes/{id}/*) ✓
- Task 2: AgentHandle with mailbox communication ✓
- Task 3: SceneManager singleton + SceneRuntime with IDLE/ACTIVATING/ACTIVE/DEACTIVATING ✓
- Task 4: Tests for all above ✓
- Task 5: entry_manager integration with SceneRuntime lifecycle ✓
- Task 6: context.py scene-level KB filtering (via existing load_knowledge_overview) ✓

**2. Placeholder scan:** No TBD/TODO/fill-in patterns found.

**3. Type consistency:**
- `SceneState` enum values match across SceneRuntime and SceneManager ✓
- `SceneConfig` field names match loader ✓
- `AgentHandle.assign_to_scene(scene_id, context)` consistent with SceneRuntime usage ✓
- `_route_to_scene(runtime, channel_type, user_id, content)` matches AgentHandle.send_message signature ✓
