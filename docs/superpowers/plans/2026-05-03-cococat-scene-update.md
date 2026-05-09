# Scene Package Update + Tests Plan

---

### Task 1: Update scene files

- [ ] **Step 1: Update CONTEXT.md**

```markdown
# Customer Service Scene

You are a professional customer service agent. Respond politely, patiently, and helpfully.

## Guidelines
- Be professional and courteous at all times
- Answer questions based on the knowledge base when available
- If you don't know the answer, say so honestly
- Escalate complex issues to a human if needed
- Keep responses concise and clear
- Remember user context from conversation history
```

- [ ] **Step 2: Update skills/manifest.json**

```json
{
  "env_skills": ["communication", "user_memory"]
}
```

- [ ] **Step 3: Update config.json**

```json
{
  "mounted_kbs": [],
  "assigned_agents": [],
  "status": "pending_config",
  "notes": "Set mounted_kbs and assigned_agents, then change status to 'ready'"
}
```

- [ ] **Step 4: Update scene.json** — add weixin entry

```json
{
  "scene_id": "customer-service",
  "title": "智能客服",
  "version": "1.1",
  "description": "Customer service scene with multi-entry support",
  "entries": [
    {
      "channel": "web_api",
      "config": { "endpoint": "/api/scenes/customer-service/chat" },
      "after_import": "ready"
    },
    {
      "channel": "weixin",
      "config": { "app_id": "", "token": "" },
      "after_import": "setup"
    }
  ],
  "config_after_import": {
    "mounted_kbs": [],
    "assigned_agents": { "min": 1, "current": [] }
  }
}
```

- [ ] **Step 5: Commit**

```bash
git add scenes/customer-service/
git commit -m "chore: update customer-service scene for v1.1"
```

---

### Task 2: Add scene tests

**Files:**
- Create: `tests/test_scene_package.py`

- [ ] **Step 1: Write test_scene_package.py**

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))

from scene_package import export_scene, import_scene
import tempfile, zipfile


def test_export_scene():
    result = export_scene("customer-service")
    assert "exported" in result
    # Clean up
    import glob
    for f in glob.glob(os.path.join(os.path.dirname(os.path.dirname(__file__)), "scenes", "customer-service-*.zip")):
        os.remove(f)


def test_import_scene():
    """Export then re-import to verify round-trip."""
    export_scene("customer-service")
    import glob
    scenes_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scenes")
    zips = glob.glob(os.path.join(scenes_dir, "customer-service-*.zip"))
    if zips:
        result = import_scene(zips[0])
        assert "imported" in result
        os.remove(zips[0])


def test_scene_has_required_files():
    scene_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scenes", "customer-service")
    assert os.path.exists(os.path.join(scene_dir, "scene.json"))
    assert os.path.exists(os.path.join(scene_dir, "CONTEXT.md"))
    assert os.path.exists(os.path.join(scene_dir, "config.json"))
    assert os.path.exists(os.path.join(scene_dir, "skills", "manifest.json"))


def test_config_has_pending_status():
    import json
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scenes", "customer-service", "config.json")
    with open(config_path) as f:
        config = json.load(f)
    assert config.get("status") == "pending_config"


def test_scene_json_has_entries():
    import json
    scene_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scenes", "customer-service", "scene.json")
    with open(scene_path) as f:
        scene = json.load(f)
    assert len(scene.get("entries", [])) > 0
    assert scene["entries"][0]["channel"] == "web_api"
```

- [ ] **Step 2: Run tests**

```powershell
python -m pytest tests/test_scene_package.py tests/ -v
```

- [ ] **Step 3: Commit**

```bash
git add scenes/customer-service/ tests/test_scene_package.py
git commit -m "test: update scene package and add scene tests"
```
