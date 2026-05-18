# KB-Agent Autonomous Capabilities Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Enable kb-agent to autonomously create knowledge bases, trigger cron jobs from YAML config, load ingestion skill, and wire image processing into the pipeline.

**Tech Stack:** Python (FastAPI backend), YAML config, existing ingest/kb_tools infrastructure.

---

### Task 1: `create_kb` Tool + API Endpoint

**Files:**
- Modify: `cococat/core/tools/kb_tools.py` — add `create_kb` function
- Modify: `cococat/core/tools/__init__.py` — register in `_make_kb_admin_tools()`
- Modify: `cococat/routes/knowledge.py` — add `POST /api/knowledge` endpoint
- Create: `tests/cococat/test_kb_create.py` — tests

**Steps:**

1. Add `create_kb` tool function in `cococat/core/tools/kb_tools.py`:

```python
def _create_kb(kb_name: str, purpose: str = "") -> str:
    """Create a new knowledge base with the required directory structure."""
    import os
    base = os.path.join("knowledge", kb_name)
    if os.path.exists(os.path.join(base, "wiki")):
        return f"Knowledge base '{kb_name}' already exists"
    dirs = [
        os.path.join(base, "wiki", "entities"),
        os.path.join(base, "wiki", "concepts"),
        os.path.join(base, "raw", "sources"),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
    with open(os.path.join(base, "purpose.md"), "w", encoding="utf-8") as f:
        f.write(f"# {kb_name}\n\n{purpose or 'Knowledge base for ' + kb_name}\n")
    with open(os.path.join(base, "index.md"), "w", encoding="utf-8") as f:
        f.write(f"# {kb_name} Index\n\n## Entities\n\n## Concepts\n")
    with open(os.path.join(base, "log.md"), "w", encoding="utf-8") as f:
        f.write(f"# {kb_name} Change Log\n\n")
    return f"Created knowledge base '{kb_name}'"
```

2. Register in `_make_kb_admin_tools()` return dict:

```python
"create_kb": Tool(
    name="create_kb",
    description="Create a new knowledge base with proper directory structure. Use when you need a new KB for organizing information.",
    parameters={
        "type": "object",
        "properties": {
            "kb_name": {"type": "string", "description": "Name for the new knowledge base (lowercase, hyphens)"},
            "purpose": {"type": "string", "description": "Brief description of what this KB is for"},
        },
        "required": ["kb_name"],
    },
    func=lambda kb_name, purpose="": _create_kb(kb_name, purpose),
),
```

3. Add `POST /api/knowledge` endpoint in `cococat/routes/knowledge.py`:

```python
from pydantic import BaseModel

class CreateKBRequest(BaseModel):
    name: str
    purpose: str = ""

@router.post("")
async def create_knowledge(body: CreateKBRequest):
    import os
    base = os.path.join("knowledge", body.name)
    if os.path.exists(os.path.join(base, "wiki")):
        raise HTTPException(status_code=409, detail=f"KB '{body.name}' already exists")
    dirs = [
        os.path.join(base, "wiki", "entities"),
        os.path.join(base, "wiki", "concepts"),
        os.path.join(base, "raw", "sources"),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
    with open(os.path.join(base, "purpose.md"), "w") as f:
        f.write(f"# {body.name}\n\n{body.purpose or 'Knowledge base for ' + body.name}\n")
    with open(os.path.join(base, "index.md"), "w") as f:
        f.write(f"# {body.name} Index\n\n## Entities\n\n## Concepts\n")
    with open(os.path.join(base, "log.md"), "w") as f:
        f.write(f"# {body.name} Change Log\n\n")
    return {"status": "created", "name": body.name}
```

4. Write tests in `tests/cococat/test_kb_create.py`:

```python
import os, shutil, pytest
from cococat.core.tools.kb_tools import _create_kb

def test_create_kb():
    name = "test-create-kb"
    path = os.path.join("knowledge", name)
    if os.path.exists(path):
        shutil.rmtree(path)
    result = _create_kb(name, "Test KB")
    assert "Created" in result
    assert os.path.exists(os.path.join(path, "wiki", "entities"))
    assert os.path.exists(os.path.join(path, "purpose.md"))
    shutil.rmtree(path)

def test_create_kb_already_exists():
    name = "test-create-kb-exists"
    path = os.path.join("knowledge", name)
    os.makedirs(os.path.join(path, "wiki"), exist_ok=True)
    try:
        result = _create_kb(name)
        assert "already exists" in result
    finally:
        shutil.rmtree(path)
```

5. Run: `python -m pytest tests/cococat/test_kb_create.py -v`
6. Commit

---

### Task 2: Cron Auto-Scheduling from YAML Config

**Files:**
- Modify: `cococat/core/bootstrap.py` — read `cron` from resident YAML, generate job files
- Test: `tests/cococat/test_cron_bootstrap.py`

**Steps:**

1. In `cococat/core/bootstrap.py`, in `_load_residents()`, after creating agent, add:

```python
# Generate cron jobs from YAML config
_cron_entries = r.get("cron", [])
if _cron_entries:
    _seed_cron_jobs(agent_id, _cron_entries)
```

2. Add `_seed_cron_jobs` function:

```python
def _seed_cron_jobs(agent_id: str, entries: list[dict]) -> None:
    """Generate runs/cron/{agent_id}-{name}.json from YAML cron declarations."""
    import json as _json
    cron_dir = os.path.join("runs", "cron")
    os.makedirs(cron_dir, exist_ok=True)
    for entry in entries:
        name = entry.get("name", "task")
        schedule = entry.get("schedule", "@daily")
        filename = f"{agent_id}-{name}.json"
        filepath = os.path.join(cron_dir, filename)
        if not os.path.exists(filepath):
            job = {
                "agent_id": agent_id,
                "name": name,
                "schedule": schedule,
                "task": entry.get("task", f"Run {name} maintenance"),
            }
            with open(filepath, "w", encoding="utf-8") as f:
                _json.dump(job, f)
            logger.info("Seeded cron job: %s (%s)", filename, schedule)
```

3. Write tests in `tests/cococat/test_cron_bootstrap.py`:

```python
import os, json, shutil
from cococat.core.bootstrap import _seed_cron_jobs

def test_seed_cron_jobs():
    entries = [
        {"name": "lint", "schedule": "@daily"},
        {"name": "dedup", "schedule": "@weekly"},
    ]
    _seed_cron_jobs("test-agent", entries)
    for name in ("lint", "dedup"):
        path = os.path.join("runs", "cron", f"test-agent-{name}.json")
        assert os.path.exists(path)
        with open(path) as f:
            job = json.load(f)
        assert job["schedule"] in ("@daily", "@weekly")
        os.remove(path)

def test_seed_cron_jobs_idempotent():
    entries = [{"name": "once", "schedule": "@daily"}]
    _seed_cron_jobs("test-agent", entries)
    mtime1 = os.path.getmtime("runs/cron/test-agent-once.json")
    _seed_cron_jobs("test-agent", entries)
    mtime2 = os.path.getmtime("runs/cron/test-agent-once.json")
    assert mtime1 == mtime2  # not overwritten
    os.remove("runs/cron/test-agent-once.json")
```

4. Run: `python -m pytest tests/cococat/test_cron_bootstrap.py -v`
5. Commit

---

### Task 3: Load `knowledge-ingestion` Skill

**Files:**
- Modify: `cococat/core/bootstrap.py` — read `skills` from YAML, create profile.yaml
- Create: `agents/kb-agent/profile.yaml` (or generate from bootstrap)

**Steps:**

1. In `_load_residents()`, after reading agent config, handle skills:

```python
_skills = r.get("skills", [])
if _skills:
    # Write agent profile.yaml with skills for get_agent_skills() to pick up
    profile_dir = f"agents/{agent_id}"
    os.makedirs(profile_dir, exist_ok=True)
    profile_path = os.path.join(profile_dir, "profile.yaml")
    if not os.path.exists(profile_path):
        import yaml as _yaml
        with open(profile_path, "w") as f:
            _yaml.dump({"skills": _skills}, f)
        logger.info("Created %s with skills: %s", profile_path, _skills)
```

2. Verify: `python -c "from cococat.core.agent import Agent; print(Agent.__init__.__code__.co_filename)"` — check that `get_agent_skills(agent_dir)` is called during Agent init. It should pick up the newly created profile.yaml.

3. Test: restart backend, check kb-agent logs for loaded skills.

4. Commit

---

### Task 4: Wire ImagePipeline into IngestPipeline

**Files:**
- Modify: `cococat/ingest/ingest.py` — call ImagePipeline during analysis phase

**Steps:**

1. In `IngestPipeline._analyze()`, add image extraction after file reading:

```python
from cococat.ingest.image import ImagePipeline

# Inside _analyze, after reading source file content:
image_pipeline = ImagePipeline(vision_llm=self.llm)
images = image_pipeline.find_images(source_path, content)
if images:
    captioned = image_pipeline.caption_images(images)
    content += "\n\n## Extracted Images\n" + "\n".join(
        f"- [{img.filename}]: {cap}" for img, cap in captioned
    )
```

2. Write tests verifying ImagePipeline is called during ingest.
3. Commit
