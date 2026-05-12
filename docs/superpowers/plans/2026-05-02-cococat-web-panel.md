# Web Management Panel Plan

**Goal:** FastAPI-based web dashboard showing agent status, chat log, scene config, and knowledge bases.

**Architecture:** Standalone FastAPI app that reads the same filesystem (config, chat log, scenes, knowledge). Serves a simple HTML/JS dashboard. Rust and web panel share the same data directory.

---

### Task 1: FastAPI setup + agent status endpoint

**Files:**
- Create: `web/requirements.txt`
- Create: `web/main.py`

- [ ] **Step 1: Create requirements.txt**

```
fastapi>=0.100.0
uvicorn>=0.20.0
```

- [ ] **Step 2: Create web/main.py**

```python
"""CocoCat Web Management Panel — FastAPI backend."""
import json
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="CocoCat Panel")

BASE_DIR = Path(__file__).resolve().parent.parent


@app.get("/api/agents")
def list_agents():
    """Read agent config and status from filesystem."""
    config_path = BASE_DIR / "agents" / "config.toml"
    agents = []
    if config_path.exists():
        import tomllib
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        for a in data.get("agents", []):
            agents.append({
                "id": a["id"],
                "name": a["name"],
                "enabled": a.get("enabled", True),
                "scene": a.get("scene", "default"),
            })
    return {"agents": agents}


@app.get("/api/chat")
def read_chat(limit: int = 50):
    """Read recent chat messages."""
    chat_path = BASE_DIR / "chat" / "group.jsonl"
    messages = []
    if chat_path.exists():
        with open(chat_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        messages.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return {"messages": messages[-limit:]}


@app.get("/api/scenes")
def list_scenes():
    """List scenes and their configs."""
    scenes_dir = BASE_DIR / "scenes"
    scenes = []
    if scenes_dir.exists():
        for d in scenes_dir.iterdir():
            if d.is_dir():
                scene = {"id": d.name, "context": "", "mounted_kbs": [], "env_skills": [], "roster": []}
                ctx_path = d / "CONTEXT.md"
                if ctx_path.exists():
                    scene["context"] = ctx_path.read_text(encoding="utf-8")[:200]
                mount_path = d / "mounted_kbs.json"
                if mount_path.exists():
                    try:
                        scene["mounted_kbs"] = json.loads(mount_path.read_text(encoding="utf-8")).get("mounted", [])
                    except Exception:
                        pass
                skills_path = d / "skills" / "manifest.json"
                if skills_path.exists():
                    try:
                        scene["env_skills"] = json.loads(skills_path.read_text(encoding="utf-8")).get("env_skills", [])
                    except Exception:
                        pass
                roster_path = d / "roster.json"
                if roster_path.exists():
                    try:
                        scene["roster"] = json.loads(roster_path.read_text(encoding="utf-8")).get("agents", [])
                    except Exception:
                        pass
                scenes.append(scene)
    return {"scenes": scenes}


@app.get("/api/skills")
def list_skills():
    """List all skill definitions."""
    skills_dir = BASE_DIR / "skills"
    skills = {"public": [], "private": []}
    if skills_dir.exists():
        for tag in ["public", "private"]:
            tag_dir = skills_dir / tag
            if tag_dir.exists():
                for f in tag_dir.iterdir():
                    if f.suffix == ".md":
                        skills[tag].append({
                            "name": f.stem,
                            "title": f.read_text(encoding="utf-8").split("\n")[0].replace("# Skill: ", ""),
                        })
    return skills


@app.get("/api/knowledge")
def list_knowledge():
    """List knowledge bases."""
    kb_dir = BASE_DIR / "knowledge"
    kbs = []
    if kb_dir.exists():
        for d in kb_dir.iterdir():
            if d.is_dir():
                kbs.append({"id": d.name, "path": str(d)})
    return kbs


@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Simple dashboard page."""
    return """<!DOCTYPE html>
<html lang="zh">
<head><meta charset="utf-8"><title>CocoCat Panel</title>
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 p-8">
<div class="max-w-6xl mx-auto">
<h1 class="text-2xl font-bold mb-6">CocoCat Management Panel</h1>

<div class="grid grid-cols-2 gap-6">
  <div class="bg-white p-4 rounded shadow">
    <h2 class="font-semibold mb-3">Agents</h2>
    <div id="agents" class="text-sm">Loading...</div>
  </div>
  <div class="bg-white p-4 rounded shadow">
    <h2 class="font-semibold mb-3">Chat Log</h2>
    <div id="chat" class="text-sm max-h-64 overflow-y-auto">Loading...</div>
  </div>
  <div class="bg-white p-4 rounded shadow">
    <h2 class="font-semibold mb-3">Scenes</h2>
    <div id="scenes" class="text-sm">Loading...</div>
  </div>
  <div class="bg-white p-4 rounded shadow">
    <h2 class="font-semibold mb-3">Skills</h2>
    <div id="skills" class="text-sm">Loading...</div>
  </div>
</div>
</div>
<script>
async function load() {
  const agents = await (await fetch('/api/agents')).json();
  document.getElementById('agents').innerHTML = agents.agents.map(a =>
    `<div class="py-1">${'&#9632;'} ${a.name} (${a.id}) <span class="text-gray-400">scene: ${a.scene}</span></div>`
  ).join('');

  const chat = await (await fetch('/api/chat?limit=20')).json();
  document.getElementById('chat').innerHTML = chat.messages.map(m =>
    `<div class="py-1 border-b border-gray-100"><span class="font-medium">[${m.from}]</span> ${m.content.substring(0,100)}</div>`
  ).join('');

  const scenes = await (await fetch('/api/scenes')).json();
  document.getElementById('scenes').innerHTML = scenes.scenes.map(s =>
    `<div class="py-2 border-b border-gray-100"><strong>${s.id}</strong> KB: ${s.mounted_kbs.join(', ') || 'none'} Skills: ${s.env_skills.join(', ') || 'none'}</div>`
  ).join('');

  const skills = await (await fetch('/api/skills')).json();
  document.getElementById('skills').innerHTML =
    '<div class="font-medium">Public:</div> ' + (skills.public.map(s => s.title).join(', ') || 'none') +
    '<br><div class="font-medium mt-2">Private:</div> ' + (skills.private.map(s => s.title).join(', ') || 'none');
}
load();
</script>
</body></html>"""
```

- [ ] **Step 3: Test**

```powershell
pip install -r web/requirements.txt
python -m uvicorn web.main:app --port 8000 --reload
```

Open http://localhost:8000 in browser.

- [ ] **Step 4: Commit**

```bash
git add web/
git commit -m "feat: add web management panel with FastAPI"
```
