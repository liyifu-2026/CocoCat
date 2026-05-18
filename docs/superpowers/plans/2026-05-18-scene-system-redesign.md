# Scene System Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the scene system to support dynamic scene creation (1:1 scene-agent binding), lifecycle management, and a non-technical-user-friendly UI.

**Architecture:** Scenes and their bound agents are stored in SQLite (replacing filesystem YAML). Scene creation auto-generates an agent. The frontend gets a 5-step creation wizard, a card-based scene list with status badges, and a scene runner page (chat + config panel).

**Tech Stack:** FastAPI (Python), React 19 + TypeScript + Tailwind 4, SQLite (WAL mode)

---

## Phase 1: Database Schema & Backend Foundation

### Task 1: Expand `scenes` table in DB schema

**Files:**
- Modify: `cococat/db/database.py` — lines around the scenes CREATE TABLE

- [ ] **Step 1: Add migration SQL to expand scenes table**

In `cococat/db/database.py`, locate the `scenes` table creation (~line 76). Replace with:

```python
cursor.execute("""
    CREATE TABLE IF NOT EXISTS scenes (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        context TEXT NOT NULL DEFAULT '',
        agent_id TEXT,
        status TEXT NOT NULL DEFAULT 'running'
            CHECK (status IN ('running','paused','archived','deleted')),
        purpose TEXT NOT NULL DEFAULT '',
        kbs TEXT NOT NULL DEFAULT '[]',
        skills TEXT NOT NULL DEFAULT '[]',
        tools TEXT NOT NULL DEFAULT '[]',
        channels TEXT NOT NULL DEFAULT '[]',
        llm_config TEXT NOT NULL DEFAULT '{}',
        visibility TEXT NOT NULL DEFAULT 'private'
            CHECK (visibility IN ('private','shared')),
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        archived_at TEXT,
        FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE SET NULL
    )
""")
```

- [ ] **Step 2: Add migration for existing DB**

In the same file, after the CREATE TABLE blocks, add a migration section:

```python
def _migrate_scenes_table(self):
    """Add new columns to scenes table if they don't exist (2026-05-18)."""
    new_columns = {
        'description': "TEXT NOT NULL DEFAULT ''",
        'context': "TEXT NOT NULL DEFAULT ''",
        'agent_id': "TEXT",
        'status': "TEXT NOT NULL DEFAULT 'running'",
        'purpose': "TEXT NOT NULL DEFAULT ''",
        'kbs': "TEXT NOT NULL DEFAULT '[]'",
        'skills': "TEXT NOT NULL DEFAULT '[]'",
        'tools': "TEXT NOT NULL DEFAULT '[]'",
        'channels': "TEXT NOT NULL DEFAULT '[]'",
        'llm_config': "TEXT NOT NULL DEFAULT '{}'",
        'visibility': "TEXT NOT NULL DEFAULT 'private'",
        'updated_at': "TEXT NOT NULL DEFAULT (datetime('now'))",
        'archived_at': "TEXT",
    }
    existing = {row[1] for row in self.conn.execute("PRAGMA table_info(scenes)")}
    for col_name, col_def in new_columns.items():
        if col_name not in existing:
            self.conn.execute(f"ALTER TABLE scenes ADD COLUMN {col_name} {col_def}")
```

Call `_migrate_scenes_table()` after the scenes CREATE TABLE in `__init__`.

- [ ] **Step 3: Verify migration**

```bash
rm -f cococat.db && python -m cococat 2>&1 | head -5
python -c "
import sqlite3
conn = sqlite3.connect('cococat.db')
cols = [r[1] for r in conn.execute('PRAGMA table_info(scenes)')]
print(cols)
assert 'status' in cols
assert 'agent_id' in cols
assert 'purpose' in cols
print('OK: all columns present')
"
```

- [ ] **Step 4: Commit**

```bash
git add cococat/db/database.py
git commit -m "feat(db): expand scenes table with lifecycle, agent binding, and full config fields"
```

---

### Task 2: Expand SceneStore with new CRUD methods

**Files:**
- Modify: `cococat/db/scene_store.py`

- [ ] **Step 1: Add full-featured create method**

Replace the existing `create` method in `SceneStore`:

```python
def create(self, config: dict) -> str:
    """Create a scene with full configuration. Returns scene_id."""
    scene_id = config["id"]
    self.db.conn.execute("""
        INSERT INTO scenes (id, name, description, context, agent_id, status,
                            purpose, kbs, skills, tools, channels, llm_config, visibility)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        scene_id,
        config["name"],
        config.get("description", ""),
        config.get("context", ""),
        config.get("agent_id"),
        config.get("status", "running"),
        config.get("purpose", ""),
        json.dumps(config.get("kbs", [])),
        json.dumps(config.get("skills", [])),
        json.dumps(config.get("tools", [])),
        json.dumps(config.get("channels", [])),
        json.dumps(config.get("llm_config", {})),
        config.get("visibility", "private"),
    ))
    self.db.conn.commit()
    return scene_id
```

- [ ] **Step 2: Add update method**

```python
def update(self, scene_id: str, updates: dict) -> bool:
    """Update scene fields. `updates` keys match column names."""
    setters = []
    values = []
    for key, val in updates.items():
        setters.append(f"{key} = ?")
        values.append(val)
    if not setters:
        return False
    setters.append("updated_at = datetime('now')")
    values.append(scene_id)
    self.db.conn.execute(
        f"UPDATE scenes SET {', '.join(setters)} WHERE id = ?",
        values
    )
    self.db.conn.commit()
    return self.db.conn.total_changes > 0
```

- [ ] **Step 3: Add status lifecycle methods**

```python
def set_status(self, scene_id: str, status: str) -> bool:
    """Transition scene to new status."""
    now = datetime.utcnow().isoformat()
    if status == "archived":
        self.db.conn.execute(
            "UPDATE scenes SET status = ?, archived_at = ?, updated_at = ? WHERE id = ?",
            (status, now, now, scene_id)
        )
    else:
        self.db.conn.execute(
            "UPDATE scenes SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, scene_id)
        )
    self.db.conn.commit()
    return self.db.conn.total_changes > 0
```

- [ ] **Step 4: Add get_full for expanded fields**

```python
def get_full(self, scene_id: str) -> dict | None:
    """Get scene with all config fields hydrated."""
    row = self.db.conn.execute(
        "SELECT * FROM scenes WHERE id = ?", (scene_id,)
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    for json_field in ("kbs", "skills", "tools", "channels", "llm_config"):
        try:
            d[json_field] = json.loads(d.get(json_field, "[]"))
        except (json.JSONDecodeError, TypeError):
            d[json_field] = [] if json_field != "llm_config" else {}
    return d
```

- [ ] **Step 5: Add import for json and datetime at top**

```python
import json
from datetime import datetime
```

- [ ] **Step 6: Commit**

```bash
git add cococat/db/scene_store.py
git commit -m "feat(scene_store): add full CRUD, lifecycle, and JSON hydration methods"
```

---

### Task 3: Expand AgentStore with personality/styling fields

**Files:**
- Modify: `cococat/db/agent_store.py`

- [ ] **Step 1: Add create_full method**

```python
def create_full(self, config: dict) -> str:
    """Create an agent with full configuration including personality fields."""
    agent_id = config["id"]
    metadata = {
        "personality": config.get("personality", ""),
        "tone": config.get("tone", ""),
        "language": config.get("language", ""),
        "avatar": config.get("avatar", ""),
    }
    self.db.conn.execute("""
        INSERT INTO agents (id, name, role, model, scene_id, status, system_prompt, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        agent_id,
        config["name"],
        config.get("role", "resident"),
        config.get("model", "deepseek-chat"),
        config.get("scene_id", "default"),
        config.get("status", "running"),
        config.get("system_prompt", ""),
        json.dumps(metadata),
    ))
    self.db.conn.commit()
    return agent_id
```

- [ ] **Step 2: Add get_personality method**

```python
def get_personality(self, agent_id: str) -> dict:
    """Get agent personality fields from metadata."""
    row = self.db.conn.execute(
        "SELECT metadata FROM agents WHERE id = ?", (agent_id,)
    ).fetchone()
    if not row:
        return {}
    try:
        meta = json.loads(row["metadata"])
        return {
            "personality": meta.get("personality", ""),
            "tone": meta.get("tone", ""),
            "language": meta.get("language", ""),
            "avatar": meta.get("avatar", ""),
        }
    except (json.JSONDecodeError, TypeError):
        return {}
```

- [ ] **Step 3: Add import for json at top**

```python
import json
```

- [ ] **Step 4: Commit**

```bash
git add cococat/db/agent_store.py
git commit -m "feat(agent_store): add create_full and personality field support"
```

---

## Phase 2: Scene API Endpoints

### Task 4: Rewrite scene routes — creation with auto-agent

**Files:**
- Modify: `cococat/routes/scenes.py`
- Create: `cococat/scene/generator.py` — helper for auto-generating scene config

- [ ] **Step 1: Create scene generation helper**

Create `cococat/scene/generator.py`:

```python
"""Auto-generate scene context and agent config from user input."""

AGENT_TONES = {
    "friendly": "亲切友好",
    "professional": "专业严谨",
    "concise": "简洁高效",
    "humorous": "幽默风趣",
}

PURPOSE_CONTEXTS = {
    "customer_service": "你是一个专业的客服。耐心、礼貌、准确地回答用户问题。如果不知道答案，诚实告知并引导用户提供更多信息。",
    "content_writing": "你是一个内容创作助手。根据用户需求撰写、翻译、润色文档。注重语言流畅、逻辑清晰、风格恰当。",
    "project_management": "你是一个项目管理助手。帮助拆分任务、追踪进度、提醒 deadline。保持有条理、主动推进、及时同步。",
    "data_analysis": "你是一个数据分析助手。分析数据、生成洞察、制作可视化报告。基于数据说话，结论要有依据。",
}


def generate_scene_config(purpose: str, name: str, description: str,
                          tone: str, language: str, agent_name: str,
                          agent_model: str) -> dict:
    """Generate full scene + agent config from user wizard input."""
    context = PURPOSE_CONTEXTS.get(purpose, "通用助手场景。")

    if tone == "friendly":
        context += "\n\n语气亲切友好，可以适当使用表情符号，让用户感到温暖。"
    elif tone == "professional":
        context += "\n\n保持专业严谨，用词准确，避免随意和口语化。"
    elif tone == "concise":
        context += "\n\n回答简洁高效，直击要点，不啰嗦。"
    elif tone == "humorous":
        context += "\n\n可以适度幽默风趣，让对话轻松愉快，但不要影响信息准确性。"

    if language == "en":
        context += "\nUse English for all responses."
    elif language == "zh_en":
        context += "\n可以根据用户输入的语言自由切换中英文。"

    return {
        "context": context,
        "agent_system_prompt": context,
    }
```

- [ ] **Step 2: Rewrite scene creation endpoint**

In `cococat/routes/scenes.py`, replace or expand the POST endpoint:

```python
class SceneCreateFull(BaseModel):
    id: str
    name: str
    description: str = ""
    purpose: str = ""  # customer_service, content_writing, project_management, data_analysis, custom
    # Agent fields
    agent_name: str = ""
    agent_tone: str = "friendly"  # friendly, professional, concise, humorous
    agent_language: str = "zh"  # zh, en, zh_en
    agent_model: str = ""
    # Scene fields
    kbs: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    visibility: str = "private"


@router.post("", response_model=dict)
async def create_scene(body: SceneCreateFull, ctx: AppContext = Depends(get_context)):
    # 1. Generate scene context from purpose and tone
    from cococat.scene.generator import generate_scene_config, AGENT_TONES
    gen = generate_scene_config(
        purpose=body.purpose,
        name=body.name,
        description=body.description,
        tone=body.agent_tone,
        language=body.agent_language,
        agent_name=body.agent_name or body.name,
        agent_model=body.agent_model or "",
    )

    # 2. Create agent in DB
    agent_id = body.id  # scene and agent share the same ID (1:1)
    agent_config = {
        "id": agent_id,
        "name": body.agent_name or body.name,
        "role": "resident",
        "model": body.agent_model or "",
        "scene_id": body.id,
        "status": "running",
        "system_prompt": gen["agent_system_prompt"],
        "personality": AGENT_TONES.get(body.agent_tone, ""),
        "tone": body.agent_tone,
        "language": body.agent_language,
    }
    ctx.db.agents.create_full(agent_config)

    # 3. Create scene in DB
    scene_config = {
        "id": body.id,
        "name": body.name,
        "description": body.description,
        "context": gen["context"],
        "agent_id": agent_id,
        "status": "running",
        "purpose": body.purpose,
        "kbs": body.kbs,
        "skills": body.skills,
        "tools": body.tools,
        "channels": body.channels,
        "llm_config": {},
        "visibility": body.visibility,
    }
    ctx.db.scenes.create(scene_config)

    return ctx.db.scenes.get_full(body.id)
```

- [ ] **Step 3: Commit**

```bash
git add cococat/routes/scenes.py cococat/scene/generator.py
git commit -m "feat(scenes): scene creation endpoint with auto-generated agent"
```

---

### Task 5: Scene lifecycle endpoints

**Files:**
- Modify: `cococat/routes/scenes.py`

- [ ] **Step 1: Add lifecycle action handler**

Below the existing routes in `cococat/routes/scenes.py`, add:

```python
class SceneLifecycleAction(BaseModel):
    action: str  # pause, resume, archive, delete


@router.post("/{scene_id}/lifecycle", response_model=dict)
async def scene_lifecycle(scene_id: str, body: SceneLifecycleAction,
                          ctx: AppContext = Depends(get_context)):
    scene = ctx.db.scenes.get_full(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    status = scene.get("status", "running")
    action = body.action

    # Validate state transitions
    valid_transitions = {
        "running": {"pause", "archive", "delete"},
        "paused": {"resume", "archive", "delete"},
        "archived": {"resume", "delete"},
        "deleted": set(),
    }
    if action not in valid_transitions.get(status, set()):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot {action} a scene with status '{status}'"
        )

    # Map action to status
    status_map = {
        "resume": "running",
        "pause": "paused",
        "archive": "archived",
        "delete": "deleted",
    }
    new_status = status_map[action]

    # Update scene status
    ctx.db.scenes.set_status(scene_id, new_status)

    # Also update bound agent status
    agent_id = scene.get("agent_id")
    if agent_id:
        if new_status in ("paused", "archived", "deleted"):
            ctx.db.conn.execute(
                "UPDATE agents SET status = 'stopped' WHERE id = ?", (agent_id,)
            )
        elif new_status == "running":
            ctx.db.conn.execute(
                "UPDATE agents SET status = 'running' WHERE id = ?", (agent_id,)
            )
        ctx.db.conn.commit()

    return {"id": scene_id, "status": new_status, "previous_status": status}
```

- [ ] **Step 2: Commit**

```bash
git add cococat/routes/scenes.py
git commit -m "feat(scenes): lifecycle endpoints — pause, resume, archive, delete"
```

---

### Task 6: Scene update endpoint

**Files:**
- Modify: `cococat/routes/scenes.py`

- [ ] **Step 1: Add PATCH endpoint for scene editing**

```python
class SceneUpdateFull(BaseModel):
    name: str | None = None
    description: str | None = None
    context: str | None = None
    kbs: list[str] | None = None
    skills: list[str] | None = None
    tools: list[str] | None = None
    channels: list[str] | None = None
    visibility: str | None = None
    # Agent fields
    agent_name: str | None = None
    agent_tone: str | None = None
    agent_language: str | None = None
    agent_model: str | None = None


@router.patch("/{scene_id}", response_model=dict)
async def update_scene(scene_id: str, body: SceneUpdateFull,
                       ctx: AppContext = Depends(get_context)):
    scene = ctx.db.scenes.get_full(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    # Build scene updates
    scene_updates = {}
    for field in ("name", "description", "context", "visibility"):
        val = getattr(body, field)
        if val is not None:
            scene_updates[field] = val
    for field in ("kbs", "skills", "tools", "channels"):
        val = getattr(body, field)
        if val is not None:
            scene_updates[field] = json.dumps(val)

    if scene_updates:
        ctx.db.scenes.update(scene_id, scene_updates)

    # Build agent updates
    agent_updates = {}
    if body.agent_name is not None:
        agent_updates["name"] = body.agent_name
    if body.agent_model is not None:
        agent_updates["model"] = body.agent_model
    if body.agent_tone is not None or body.agent_language is not None:
        existing_meta = json.loads(
            ctx.db.conn.execute(
                "SELECT metadata FROM agents WHERE id = ?", (scene.get("agent_id"),)
            ).fetchone()["metadata"] or "{}"
        )
        if body.agent_tone is not None:
            existing_meta["tone"] = body.agent_tone
        if body.agent_language is not None:
            existing_meta["language"] = body.agent_language
        agent_updates["metadata"] = json.dumps(existing_meta)

    agent_id = scene.get("agent_id")
    if agent_id and agent_updates:
        set_clauses = ", ".join(f"{k} = ?" for k in agent_updates)
        values = list(agent_updates.values()) + [agent_id]
        ctx.db.conn.execute(
            f"UPDATE agents SET {set_clauses} WHERE id = ?", values
        )
        ctx.db.conn.commit()

    return ctx.db.scenes.get_full(scene_id)
```

- [ ] **Step 2: Commit**

```bash
git add cococat/routes/scenes.py
git commit -m "feat(scenes): full scene update endpoint including agent fields"
```

---

### Task 7: Update scene list/detail endpoints to use DB

**Files:**
- Modify: `cococat/routes/scenes.py`

- [ ] **Step 1: Rewrite list endpoint to use DB exclusively**

```python
@router.get("", response_model=list[dict])
async def list_scenes(ctx: AppContext = Depends(get_context)):
    rows = ctx.db.conn.execute(
        "SELECT * FROM scenes WHERE status != 'deleted' ORDER BY created_at DESC"
    ).fetchall()
    scenes = []
    for row in rows:
        d = dict(row)
        for field in ("kbs", "skills", "tools", "channels"):
            try:
                d[field] = json.loads(d.get(field, "[]"))
            except (json.JSONDecodeError, TypeError):
                d[field] = []
        try:
            d["llm_config"] = json.loads(d.get("llm_config", "{}"))
        except (json.JSONDecodeError, TypeError):
            d["llm_config"] = {}
        scenes.append(d)
    return scenes
```

- [ ] **Step 2: Rewrite get endpoint to use DB**

```python
@router.get("/{scene_id}", response_model=dict)
async def get_scene(scene_id: str, ctx: AppContext = Depends(get_context)):
    scene = ctx.db.scenes.get_full(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    # Add agent info
    agent_id = scene.get("agent_id")
    if agent_id:
        agent = ctx.db.agents.get(agent_id)
        if agent:
            personality = ctx.db.agents.get_personality(agent_id)
            scene["agent"] = {
                "id": agent_id,
                "name": agent.get("name", ""),
                "model": agent.get("model", ""),
                "personality": personality.get("personality", ""),
                "tone": personality.get("tone", ""),
                "language": personality.get("language", ""),
            }
    return scene
```

In `cococat/db/agent_store.py`, add:

```python
def get_personality(self, agent_id: str) -> dict:
    """Get agent personality fields from metadata."""
    row = self.db.conn.execute(
        "SELECT metadata FROM agents WHERE id = ?", (agent_id,)
    ).fetchone()
    if not row:
        return {}
    try:
        meta = json.loads(row["metadata"])
        return {
            "personality": meta.get("personality", ""),
            "tone": meta.get("tone", ""),
            "language": meta.get("language", ""),
            "avatar": meta.get("avatar", ""),
        }
    except (json.JSONDecodeError, TypeError):
        return {}
```

- [ ] **Step 3: Commit**

```bash
git add cococat/routes/scenes.py cococat/db/agent_store.py
git commit -m "feat(scenes): DB-backed list and detail endpoints with agent info"
```

---

### Task 8: Remove filesystem YAML write in scene_mgmt.py

**Files:**
- Modify: `cococat/routes/scene_mgmt.py`

- [ ] **Step 1: Rewrite KB update to use DB**

Replace the `update_scene_kbs` handler to use DB:

```python
@router.patch("/{scene_id}/kbs", response_model=dict)
async def update_scene_kbs(scene_id: str, body: KBUpdate,
                           ctx: AppContext = Depends(get_context)):
    scene = ctx.db.scenes.get_full(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    ctx.db.scenes.update(scene_id, {"kbs": json.dumps(body.mounted)})
    return {"id": scene_id, "kbs": body.mounted}
```

Do the same for `update_scene_skills`.

- [ ] **Step 2: Commit**

```bash
git add cococat/routes/scene_mgmt.py
git commit -m "fix(scene_mgmt): route KB/skill updates through DB instead of YAML files"
```

---

### Task 9: Seed default scenes from existing YAML into DB

**Files:**
- Modify: `cococat/app.py` (or `_seed_defaults`)

- [ ] **Step 1: Add migration seed for existing YAML scenes**

In `cococat/app.py`, inside `_seed_defaults`, add:

```python
from cococat.scene.config import list_scenes

def _seed_scenes_from_yaml(db):
    """One-time migration: seed existing scenes/ YAML configs into DB."""
    existing = {r["id"] for r in db.conn.execute("SELECT id FROM scenes")}
    for sc in list_scenes():
        if sc.id in existing:
            continue
        db.scenes.create({
            "id": sc.id,
            "name": sc.name or sc.id,
            "description": "",
            "context": sc.context,
            "agent_id": None,
            "status": "running",
            "purpose": "",
            "kbs": sc.kbs,
            "skills": sc.skills,
            "tools": [],
            "channels": sc.channels,
            "llm_config": {},
            "visibility": "private",
        })
```

Call this in `_seed_defaults()`.

- [ ] **Step 2: Commit**

```bash
git add cococat/app.py
git commit -m "feat(app): seed existing YAML scenes into DB on startup"
```

---

## Phase 3: Frontend — Scene List Page

### Task 10: Scene list page with card grid and status badges

**Files:**
- Modify: `web-ui/src/pages/Scenes.tsx`

- [ ] **Step 1: Rewrite Scenes page with card grid + status badges**

Replace the placeholder content in `web-ui/src/pages/Scenes.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Plus, Play, Pause, Archive, Trash2, Edit3, MessageSquare } from "lucide-react";

interface Scene {
  id: string;
  name: string;
  description: string;
  status: string;
  purpose: string;
  kbs: string[];
  skills: string[];
  channels: string[];
  agent?: { name: string };
  created_at: string;
}

const STATUS_LABELS: Record<string, { label: string; className: string }> = {
  running: { label: "运行中", className: "bg-green-100 text-green-700" },
  paused: { label: "已暂停", className: "bg-yellow-100 text-yellow-700" },
  archived: { label: "已归档", className: "bg-blue-100 text-blue-700" },
};

const PURPOSE_ICONS: Record<string, string> = {
  customer_service: "🎧",
  content_writing: "📝",
  project_management: "📋",
  data_analysis: "🔍",
};

export default function ScenesPage() {
  const navigate = useNavigate();
  const { data: scenes, refetch } = useQuery<Scene[]>({
    queryKey: ["scenes"],
    queryFn: async () => {
      const res = await fetch("/api/scenes");
      if (!res.ok) throw new Error("Failed to load scenes");
      return res.json();
    },
  });

  const handleLifecycle = async (id: string, action: string) => {
    await fetch(`/api/scenes/${id}/lifecycle`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });
    refetch();
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">场景</h1>
        <button
          onClick={() => navigate("/scenes/new")}
          className="flex items-center gap-2 bg-blue-500 text-white px-4 py-2 rounded-lg hover:bg-blue-600"
        >
          <Plus size={18} /> 新建场景
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {scenes?.map((scene) => {
          const statusInfo = STATUS_LABELS[scene.status] ?? { label: scene.status, className: "bg-gray-100 text-gray-600" };
          const isArchived = scene.status === "archived";
          return (
            <div
              key={scene.id}
              className={`border rounded-xl p-5 hover:shadow-md transition-shadow ${
                isArchived ? "opacity-60" : ""
              }`}
            >
              <div className="flex items-start justify-between mb-2">
                <h3 className="font-semibold text-lg">{scene.name}</h3>
                <span className={`text-xs px-2 py-1 rounded-full ${statusInfo.className}`}>
                  {statusInfo.label}
                </span>
              </div>
              {scene.description && (
                <p className="text-sm text-gray-500 mb-3">{scene.description}</p>
              )}
              <div className="flex flex-wrap gap-2 mb-3">
                {scene.agent && (
                  <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                    {scene.agent.name}
                  </span>
                )}
                {scene.kbs?.map((kb) => (
                  <span key={kb} className="text-xs bg-purple-50 text-purple-600 px-2 py-0.5 rounded">
                    📚 {kb}
                  </span>
                ))}
                {scene.channels?.map((ch) => (
                  <span key={ch} className="text-xs bg-teal-50 text-teal-600 px-2 py-0.5 rounded">
                    {ch === "web" ? "🌐 Web" : ch}
                  </span>
                ))}
              </div>
              <div className="flex gap-3">
                {scene.status === "running" && (
                  <>
                    <button onClick={() => navigate(`/scenes/${scene.id}/run`)} className="text-sm text-blue-500 hover:text-blue-700 flex items-center gap-1">
                      <MessageSquare size={14} /> 聊天
                    </button>
                    <button onClick={() => navigate(`/scenes/${scene.id}`)} className="text-sm text-blue-500 hover:text-blue-700 flex items-center gap-1">
                      <Edit3 size={14} /> 编辑
                    </button>
                    <button onClick={() => handleLifecycle(scene.id, "pause")} className="text-sm text-yellow-500 hover:text-yellow-700 flex items-center gap-1">
                      <Pause size={14} /> 暂停
                    </button>
                  </>
                )}
                {scene.status === "paused" && (
                  <>
                    <button onClick={() => handleLifecycle(scene.id, "resume")} className="text-sm text-green-500 hover:text-green-700 flex items-center gap-1">
                      <Play size={14} /> 恢复
                    </button>
                    <button onClick={() => navigate(`/scenes/${scene.id}`)} className="text-sm text-blue-500 hover:text-blue-700 flex items-center gap-1">
                      <Edit3 size={14} /> 编辑
                    </button>
                    <button onClick={() => handleLifecycle(scene.id, "archive")} className="text-sm text-blue-500 hover:text-blue-700 flex items-center gap-1">
                      <Archive size={14} /> 归档
                    </button>
                  </>
                )}
                {scene.status === "archived" && (
                  <>
                    <button onClick={() => handleLifecycle(scene.id, "resume")} className="text-sm text-green-500 hover:text-green-700 flex items-center gap-1">
                      <Play size={14} /> 恢复
                    </button>
                    <button onClick={() => handleLifecycle(scene.id, "delete")} className="text-sm text-red-500 hover:text-red-700 flex items-center gap-1">
                      <Trash2 size={14} /> 删除
                    </button>
                  </>
                )}
              </div>
            </div>
          );
        })}
        <button
          onClick={() => navigate("/scenes/new")}
          className="border-2 border-dashed border-gray-300 rounded-xl p-5 flex items-center justify-center min-h-[120px] hover:border-blue-300 hover:bg-blue-50/50 transition-colors"
        >
          <div className="text-center">
            <Plus size={28} className="mx-auto text-gray-400" />
            <p className="text-sm text-gray-500 mt-2">新建场景</p>
          </div>
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add web-ui/src/pages/Scenes.tsx
git commit -m "feat(frontend): card-grid scene list with status badges and lifecycle actions"
```

---

## Phase 4: Frontend — Scene Creation Wizard

### Task 11: Scene creation wizard page (5 steps)

**Files:**
- Create: `web-ui/src/pages/SceneNew.tsx`
- Modify: `web-ui/src/App.tsx` — add route

- [ ] **Step 1: Add route in App.tsx**

In `web-ui/src/App.tsx`, add the route before the catch-all:

```tsx
import SceneNew from "./pages/SceneNew";

// Add inside <Routes>:
<Route path="/scenes/new" element={<SceneNew />} />
```

- [ ] **Step 2: Create SceneNew page with 5-step wizard**

Create `web-ui/src/pages/SceneNew.tsx`:

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, ArrowRight, Check } from "lucide-react";

const PURPOSES = [
  { id: "customer_service", label: "客服", icon: "🎧" },
  { id: "content_writing", label: "内容写作", icon: "📝" },
  { id: "project_management", label: "项目管理", icon: "📋" },
  { id: "data_analysis", label: "数据分析", icon: "🔍" },
  { id: "custom", label: "自定义", icon: "✨" },
];

const TONES = [
  { id: "friendly", label: "亲切友好", emoji: "😊" },
  { id: "professional", label: "专业严谨", emoji: "👔" },
  { id: "concise", label: "简洁高效", emoji: "⚡" },
  { id: "humorous", label: "幽默风趣", emoji: "🎭" },
];

const STEPS = ["场景用途", "Agent 风格", "知识与技能", "渠道入口", "确认创建"];

interface FormData {
  id: string;
  name: string;
  description: string;
  purpose: string;
  agentName: string;
  agentTone: string;
  agentLanguage: string;
  agentModel: string;
  kbs: string[];
  skills: string[];
  channels: string[];
}

export default function SceneNew() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<FormData>({
    id: `scene-${Date.now()}`,
    name: "",
    description: "",
    purpose: "customer_service",
    agentName: "",
    agentTone: "friendly",
    agentLanguage: "zh",
    agentModel: "",
    kbs: [],
    skills: [],
    channels: ["web"],
  });

  const update = (field: keyof FormData, value: any) =>
    setForm((f) => ({ ...f, [field]: value }));

  const toggleArray = (field: keyof FormData, item: string) => {
    const arr = form[field] as string[];
    update(field, arr.includes(item) ? arr.filter((x) => x !== item) : [...arr, item]);
  };

  const handleCreate = async () => {
    const res = await fetch("/api/scenes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    });
    if (res.ok) {
      navigate(`/scenes/${form.id}/run`);
    }
  };

  return (
    <div className="max-w-xl mx-auto p-6">
      {/* Step indicator */}
      <div className="flex items-center gap-2 mb-8">
        {STEPS.map((s, i) => (
          <div key={s} className="flex items-center gap-2 flex-1">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                i <= step ? "bg-blue-500 text-white" : "bg-gray-200 text-gray-500"
              }`}
            >
              {i < step ? <Check size={16} /> : i + 1}
            </div>
            <span className={`text-xs ${i <= step ? "text-blue-600" : "text-gray-400"}`}>
              {s}
            </span>
            {i < STEPS.length - 1 && <div className="flex-1 h-px bg-gray-200 ml-2" />}
          </div>
        ))}
      </div>

      {/* Step 1: Purpose */}
      {step === 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-4">这个场景是干什么的？</h2>
          <label className="block text-sm font-medium text-gray-700 mb-1">场景名称 *</label>
          <input
            className="w-full border rounded-lg px-3 py-2 mb-4 text-sm"
            value={form.name}
            onChange={(e) => update("name", e.target.value)}
            placeholder="例如：售后客服"
          />
          <label className="block text-sm font-medium text-gray-700 mb-2">场景用途 *</label>
          <div className="grid grid-cols-2 gap-3 mb-4">
            {PURPOSES.map((p) => (
              <button
                key={p.id}
                onClick={() => update("purpose", p.id)}
                className={`border rounded-lg p-3 text-center text-sm ${
                  form.purpose === p.id
                    ? "border-blue-500 bg-blue-50"
                    : "border-gray-200 hover:border-gray-300"
                }`}
              >
                <span className="text-xl">{p.icon}</span>
                <p className="mt-1">{p.label}</p>
              </button>
            ))}
          </div>
          <label className="block text-sm font-medium text-gray-700 mb-1">一句话描述</label>
          <input
            className="w-full border rounded-lg px-3 py-2 text-sm"
            value={form.description}
            onChange={(e) => update("description", e.target.value)}
            placeholder="这个场景具体做什么"
          />
        </div>
      )}

      {/* Step 2: Agent Style */}
      {step === 1 && (
        <div>
          <h2 className="text-lg font-semibold mb-4">Agent 是什么风格？</h2>
          <label className="block text-sm font-medium text-gray-700 mb-1">Agent 名称</label>
          <input
            className="w-full border rounded-lg px-3 py-2 mb-4 text-sm"
            value={form.agentName || form.name}
            onChange={(e) => update("agentName", e.target.value)}
            placeholder="默认等于场景名"
          />
          <label className="block text-sm font-medium text-gray-700 mb-2">说话风格</label>
          <div className="grid grid-cols-2 gap-3 mb-4">
            {TONES.map((t) => (
              <button
                key={t.id}
                onClick={() => update("agentTone", t.id)}
                className={`border rounded-lg p-3 text-center text-sm ${
                  form.agentTone === t.id
                    ? "border-blue-500 bg-blue-50"
                    : "border-gray-200 hover:border-gray-300"
                }`}
              >
                <span className="text-xl">{t.emoji}</span>
                <p className="mt-1">{t.label}</p>
              </button>
            ))}
          </div>
          <label className="block text-sm font-medium text-gray-700 mb-2">语言</label>
          <div className="flex gap-3 mb-4">
            {[
              { id: "zh", label: "中文" },
              { id: "en", label: "English" },
              { id: "zh_en", label: "中英混合" },
            ].map((l) => (
              <button
                key={l.id}
                onClick={() => update("agentLanguage", l.id)}
                className={`border rounded-lg px-4 py-2 text-sm ${
                  form.agentLanguage === l.id
                    ? "border-blue-500 bg-blue-50"
                    : "border-gray-200"
                }`}
              >
                {l.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Step 3: KB + Skills */}
      {step === 2 && (
        <div>
          <h2 className="text-lg font-semibold mb-4">它需要知道什么？</h2>
          <label className="block text-sm font-medium text-gray-700 mb-2">挂载知识库（可选）</label>
          <div className="border rounded-lg p-3 mb-4">
            {["退货政策 FAQ", "产品手册", "team-wiki"].map((kb) => (
              <label key={kb} className="flex items-center gap-2 py-2 border-b last:border-0 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.kbs.includes(kb)}
                  onChange={() => toggleArray("kbs", kb)}
                  className="accent-blue-500"
                />
                📚 {kb}
              </label>
            ))}
            <p className="text-xs text-gray-400 mt-2 cursor-pointer">+ 上传新知识库</p>
          </div>
          <label className="block text-sm font-medium text-gray-700 mb-2">启用技能（可选）</label>
          <div className="flex flex-wrap gap-2">
            {["communication", "prd_writing", "code_review", "file-ops", "strategy"].map((s) => (
              <button
                key={s}
                onClick={() => toggleArray("skills", s)}
                className={`px-3 py-1.5 rounded-full text-xs border ${
                  form.skills.includes(s)
                    ? "border-blue-500 bg-blue-50 text-blue-600"
                    : "border-gray-200 text-gray-500"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Step 4: Channels */}
      {step === 3 && (
        <div>
          <h2 className="text-lg font-semibold mb-4">用户从哪里找到它？</h2>
          <div className="grid grid-cols-2 gap-3">
            {[
              { id: "web", label: "Web 聊天", icon: "🌐" },
              { id: "wechat", label: "微信", icon: "💬" },
              { id: "feishu", label: "飞书", icon: "🐦" },
              { id: "api", label: "API", icon: "🔌" },
            ].map((ch) => (
              <button
                key={ch.id}
                onClick={() => toggleArray("channels", ch.id)}
                className={`border rounded-lg p-4 text-center ${
                  form.channels.includes(ch.id)
                    ? "border-blue-500 bg-blue-50"
                    : "border-gray-200 hover:border-gray-300"
                }`}
              >
                <div className="text-2xl">{ch.icon}</div>
                <p className="text-sm font-medium mt-1">{ch.label}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Step 5: Review */}
      {step === 4 && (
        <div>
          <h2 className="text-lg font-semibold mb-4">确认创建</h2>
          <div className="bg-gray-50 rounded-lg p-4 text-sm">
            {[
              ["场景名", form.name],
              ["用途", PURPOSES.find((p) => p.id === form.purpose)?.label],
              ["Agent", `${form.agentName || form.name} · ${TONES.find((t) => t.id === form.agentTone)?.label} · ${form.agentLanguage === "zh" ? "中文" : form.agentLanguage}`],
              ["知识库", form.kbs.length ? form.kbs.join(", ") : "无"],
              ["技能", form.skills.length ? form.skills.join(", ") : "无"],
              ["渠道", form.channels.join(", ")],
            ].map(([label, value]) => (
              <div key={label} className="flex justify-between py-2 border-b last:border-0">
                <span className="text-gray-500">{label}</span>
                <span className="font-medium">{value}</span>
              </div>
            ))}
          </div>
          <button
            onClick={handleCreate}
            className="w-full mt-6 bg-blue-500 text-white py-3 rounded-lg font-semibold hover:bg-blue-600"
          >
            🚀 创建场景
          </button>
        </div>
      )}

      {/* Navigation buttons */}
      {step < 4 && (
        <div className="flex justify-between mt-8">
          <button
            onClick={() => setStep(step - 1)}
            disabled={step === 0}
            className="flex items-center gap-1 px-4 py-2 text-sm border rounded-lg disabled:opacity-30"
          >
            <ArrowLeft size={16} /> 上一步
          </button>
          <button
            onClick={() => setStep(step + 1)}
            disabled={step === 0 && !form.name}
            className="flex items-center gap-1 px-4 py-2 text-sm bg-blue-500 text-white rounded-lg disabled:opacity-30"
          >
            下一步 <ArrowRight size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add web-ui/src/pages/SceneNew.tsx web-ui/src/App.tsx
git commit -m "feat(frontend): 5-step scene creation wizard page"
```

---

## Phase 5: Frontend — Scene Runner Page

### Task 12: Scene runner page (chat + config side panel)

**Files:**
- Create: `web-ui/src/pages/SceneRun.tsx`
- Modify: `web-ui/src/App.tsx` — add route

- [ ] **Step 1: Add route in App.tsx**

```tsx
import SceneRun from "./pages/SceneRun";
// Inside <Routes>:
<Route path="/scenes/:id/run" element={<SceneRun />} />
```

- [ ] **Step 2: Create SceneRun page**

Create `web-ui/src/pages/SceneRun.tsx`:

```tsx
import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Settings, Pause } from "lucide-react";

interface SceneFull {
  id: string;
  name: string;
  description: string;
  status: string;
  agent?: { name: string; tone: string; language: string };
  kbs: string[];
  skills: string[];
  channels: string[];
}

export default function SceneRun() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [input, setInput] = useState("");
  const [showConfig, setShowConfig] = useState(false);

  const { data: scene } = useQuery<SceneFull>({
    queryKey: ["scene", id],
    queryFn: async () => {
      const res = await fetch(`/api/scenes/${id}`);
      if (!res.ok) throw new Error("Scene not found");
      return res.json();
    },
  });

  const sendMessage = async () => {
    if (!input.trim()) return;
    setMessages((m) => [...m, { role: "user", content: input }]);
    setInput("");
    // TODO: hook into real chat/agent system
    setMessages((m) => [...m, { role: "assistant", content: "（Agent 响应区域 — 待接入真实 Agent 系统）" }]);
  };

  if (!scene) return <div className="p-6">Loading...</div>;

  return (
    <div className="flex h-[calc(100vh-4rem)]">
      {/* Chat area */}
      <div className="flex-1 flex flex-col">
        <div className="border-b px-4 py-3 flex items-center gap-3">
          <button onClick={() => navigate("/scenes")}>
            <ArrowLeft size={20} />
          </button>
          <h2 className="font-semibold">{scene.name}</h2>
          <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full ml-2">
            ▶ 运行中
          </span>
          <button onClick={() => setShowConfig(!showConfig)} className="ml-auto">
            <Settings size={20} className="text-gray-400 hover:text-gray-600" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.length === 0 && (
            <div className="text-center text-gray-400 mt-20">
              <p className="text-lg">👋 开始和 {scene.agent?.name || scene.name} 对话吧</p>
              <p className="text-sm mt-1">{scene.description}</p>
            </div>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              className={`max-w-[80%] rounded-lg px-4 py-2 text-sm ${
                m.role === "user"
                  ? "bg-blue-500 text-white ml-auto"
                  : "bg-gray-100"
              }`}
            >
              {m.content}
            </div>
          ))}
        </div>
        <div className="border-t p-3 flex gap-2">
          <input
            className="flex-1 border rounded-lg px-3 py-2 text-sm"
            placeholder="输入消息..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          />
          <button
            onClick={sendMessage}
            className="bg-blue-500 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-600"
          >
            发送
          </button>
        </div>
      </div>

      {/* Config side panel */}
      {showConfig && (
        <div className="w-72 border-l bg-white p-4 overflow-y-auto">
          <h3 className="font-semibold text-sm mb-3">⚙ 场景设置</h3>
          <div className="space-y-3 text-sm">
            <div>
              <p className="text-gray-400 text-xs">Agent</p>
              <p className="font-medium">{scene.agent?.name || "—"}</p>
            </div>
            <div>
              <p className="text-gray-400 text-xs">风格</p>
              <p>{scene.agent?.tone || "—"}</p>
            </div>
            <div>
              <p className="text-gray-400 text-xs">语言</p>
              <p>{scene.agent?.language || "—"}</p>
            </div>
            <div>
              <p className="text-gray-400 text-xs">知识库</p>
              {scene.kbs?.length ? scene.kbs.map((k) => <p key={k}>📚 {k}</p>) : <p className="text-gray-400">无</p>}
            </div>
            <div>
              <p className="text-gray-400 text-xs">技能</p>
              <div className="flex flex-wrap gap-1 mt-1">
                {scene.skills?.length ? scene.skills.map((s) => (
                  <span key={s} className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full">{s}</span>
                )) : <span className="text-gray-400">无</span>}
              </div>
            </div>
            <div>
              <p className="text-gray-400 text-xs">渠道</p>
              {scene.channels?.map((ch) => <p key={ch}>{ch}</p>)}
            </div>
          </div>
          <div className="mt-6 space-y-2">
            <button
              onClick={() => navigate(`/scenes/${id}`)}
              className="w-full text-sm text-blue-500 border border-blue-500 rounded-lg py-2 hover:bg-blue-50"
            >
              编辑场景
            </button>
            <button className="w-full text-sm text-red-500 border border-red-300 rounded-lg py-2 hover:bg-red-50 flex items-center justify-center gap-1">
              <Pause size={14} /> 暂停场景
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add web-ui/src/pages/SceneRun.tsx web-ui/src/App.tsx
git commit -m "feat(frontend): scene runner page with chat and config side panel"
```

---

## Phase 6: Cleanup & Integration

### Task 13: Update SceneRail sidebar for new scene model

**Files:**
- Modify: `web-ui/src/components/SceneRail.tsx`

- [ ] **Step 1: Update SceneRail to show scenes from DB with status**

Keep the existing sidebar structure but ensure it properly lists scenes from `/api/scenes` (which now returns DB data). Add status indicators:

```tsx
// In the scene list rendering, add a status dot
const statusColors: Record<string, string> = {
  running: "bg-green-400",
  paused: "bg-yellow-400",
  archived: "bg-gray-400",
};
// Render each scene with:
<span className={`w-2 h-2 rounded-full ${statusColors[scene.status] || "bg-gray-300"}`} />
```

- [ ] **Step 2: Commit**

```bash
git add web-ui/src/components/SceneRail.tsx
git commit -m "feat(frontend): update SceneRail with scene status indicators"
```

---

### Task 14: Update scene config loader to prefer DB

**Files:**
- Modify: `cococat/scene/config.py`
- Modify: `cococat/core/agent.py` — `bind_to_scene` compatibility

- [ ] **Step 1: Add DB-backed scene loading in config.py**

Add a new loader that checks DB first, falls back to filesystem:

```python
def load_scene_from_db(scene_id: str, db) -> Optional[SceneConfig]:
    """Load scene config from database, fall back to filesystem."""
    # Try DB first
    if db and hasattr(db, 'scenes'):
        data = db.scenes.get_full(scene_id)
        if data:
            return SceneConfig(
                id=data["id"],
                name=data.get("name", ""),
                context=data.get("context", ""),
                roster=[],  # deprecated in 1:1 model
                kbs=data.get("kbs", []),
                skills=data.get("skills", []),
                channels=data.get("channels", []),
            )
    # Fall back to filesystem for backward compatibility
    return load_scene_config(scene_id)
```

- [ ] **Step 2: Commit**

```bash
git add cococat/scene/config.py
git commit -m "feat(scene): DB-backed scene config loading with filesystem fallback"
```

---

### Task 15: Basic integration test

**Files:**
- Create: `tests/test_scene_lifecycle.py`

- [ ] **Step 1: Write integration test**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from cococat.app import create_app
from cococat.db.database import Database
import tempfile
import os


@pytest.fixture
async def client():
    db_path = os.path.join(tempfile.mkdtemp(), "test.db")
    db = Database(db_path)
    app = create_app(db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_scene_create_and_lifecycle(client):
    # 1. Create scene
    payload = {
        "id": "test-scene-1",
        "name": "测试场景",
        "description": "一个测试场景",
        "purpose": "customer_service",
        "agent_name": "测试助手",
        "agent_tone": "friendly",
        "agent_language": "zh",
        "kbs": ["test-kb"],
        "skills": ["communication"],
        "channels": ["web"],
        "visibility": "private",
    }
    resp = await client.post("/api/scenes", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "test-scene-1"
    assert data["status"] == "running"
    assert data["agent_id"] is not None

    # 2. Pause scene
    resp = await client.post("/api/scenes/test-scene-1/lifecycle", json={"action": "pause"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"

    # 3. Resume scene
    resp = await client.post("/api/scenes/test-scene-1/lifecycle", json={"action": "resume"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"

    # 4. Archive scene
    resp = await client.post("/api/scenes/test-scene-1/lifecycle", json={"action": "archive"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"

    # 5. Cannot pause an archived scene
    resp = await client.post("/api/scenes/test-scene-1/lifecycle", json={"action": "pause"})
    assert resp.status_code == 400  # invalid transition


@pytest.mark.asyncio
async def test_scene_list_excludes_deleted(client):
    resp = await client.get("/api/scenes")
    assert resp.status_code == 200
    scenes = resp.json()
    for s in scenes:
        assert s["status"] != "deleted"
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/test_scene_lifecycle.py -v
```

Expected: All pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_scene_lifecycle.py
git commit -m "test: scene lifecycle integration tests"
```

---

### Task 16: Verify frontend builds

**Files:**
- (No file changes — verification only)

- [ ] **Step 1: TypeCheck**

```bash
cd web-ui && npx tsc --noEmit 2>&1 | tail -20
```

Fix any type errors in the new pages.

- [ ] **Step 2: Build check**

```bash
cd web-ui && npm run build 2>&1 | tail -10
```

Expected: Build succeeds without errors.

- [ ] **Step 3: Start and smoke test**

```bash
# Start backend
python -m cococat &
# Start frontend
cd web-ui && npm run dev &
```

Manually verify:
- Navigate to /app/scenes → see card grid
- Click "新建场景" → wizard page loads
- Complete wizard → scene created, redirects to runner
- Runner page shows chat + config panel
- Pause/resume/archive from scene list works

---

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | 1–3 | DB schema + store expansion |
| 2 | 4–9 | Scene API (create, lifecycle, update, list, seed) |
| 3 | 10 | Frontend scene list with cards |
| 4 | 11 | Frontend scene creation wizard |
| 5 | 12 | Frontend scene runner (chat + config) |
| 6 | 13–16 | Cleanup, integration tests, build verification |

**Total: 16 tasks, ~50 steps**
