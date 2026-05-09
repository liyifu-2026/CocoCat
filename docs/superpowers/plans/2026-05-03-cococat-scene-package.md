# Scene Package Export/Import Plan

**Goal:** Scenes can be exported to `.zip` packages and imported into another CocoCat instance.

---

### Task 1: Export scene tool

**Files:**
- Create: `py-agent/scene_package.py`

- [ ] **Step 1: Create scene_package.py**

```python
"""Scene package export/import utilities."""
import os
import json
import zipfile
import shutil
from datetime import datetime


def export_scene(scene_id: str, output_path: str = "") -> str:
    """Export a scene to a .zip package. Excludes runtime data (users/)."""
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scenes", scene_id)
    if not os.path.isdir(base):
        return f"Scene '{scene_id}' not found"

    # Collect files to include
    include_patterns = ["scene.json", "CONTEXT.md", "config.json", "skills/", "purpose.md", "index.md", "log.md", "schema.md"]
    output_path = output_path or os.path.join(os.path.dirname(base), f"{scene_id}-{datetime.now().strftime('%Y%m%d')}.zip")

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(base):
            # Skip runtime data
            dirs[:] = [d for d in dirs if d != "users"]
            rel_root = os.path.relpath(root, os.path.dirname(base))
            for f in files:
                filepath = os.path.join(root, f)
                arcname = os.path.join(rel_root, f)
                zf.write(filepath, arcname)

    return f"Scene '{scene_id}' exported to {output_path}"


def import_scene(package_path: str) -> str:
    """Import a scene from a .zip package."""
    scenes_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scenes")

    with zipfile.ZipFile(package_path, "r") as zf:
        # Validate: must contain scene.json
        names = zf.namelist()
        scene_jsons = [n for n in names if n.endswith("scene.json")]
        if not scene_jsons:
            return "Invalid package: no scene.json found"

        # Extract
        scene_rel_dir = os.path.dirname(scene_jsons[0])
        extract_path = os.path.dirname(scenes_dir)
        zf.extractall(extract_path)

        # Mark as pending config
        imported_scene_id = os.path.basename(scene_rel_dir)
        config_path = os.path.join(scenes_dir, imported_scene_id, "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config = json.load(f)
            config["status"] = "pending_config"
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)

        return f"Scene '{imported_scene_id}' imported. Status: pending_config. Configure mounted_kbs and assigned_agents in config.json, then set status to ready."
```

- [ ] **Step 2: Test**

```powershell
python -c "import sys; sys.path.insert(0,'py-agent'); from scene_package import export_scene, import_scene; import tempfile; r=export_scene('customer-service'); print('export:', r)" 2>&1
```

- [ ] **Step 3: Commit**

```bash
git add py-agent/scene_package.py
git commit -m "feat: add scene package export and import"
```

---

### Task 2: Config validation + status check

- [ ] **Step 1: Add config_ready check to scene.json loading**

The scene system already reads config.json. No code change needed — users manually edit config.json to set `status: "ready"`.

- [ ] **Step 2: Commit**

Already covered by Task 1.
