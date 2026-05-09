# KB Ingestion Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a two-stage LLM ingestion pipeline (llm-wiki pattern) that processes raw source files into structured wiki pages with YAML frontmatter.

**Architecture:** New `py-agent/ingest.py` module with two-stage pipeline (analysis → generation). A new `ingest_to_kb` tool on the Python side. Wiki pages get YAML frontmatter. index.md and log.md auto-maintained. The tool reads raw files from `knowledge/{kb}/raw/sources/` and writes to `knowledge/{kb}/wiki/`.

**Tech Stack:** Python, LLM (DeepSeek via OpenAI API)

---

## File Structure

```
Cococlaw/
├── knowledge/
│   └── team-wiki/
│       ├── purpose.md              # NEW: KB goals
│       ├── index.md                # NEW: auto-maintained catalog
│       ├── log.md                  # NEW: append-only operation log
│       ├── raw/sources/            # NEW: drop zone for raw files
│       ├── wiki/
│       │   ├── entities/           # Existing
│       │   └── concepts/           # Existing
│       └── schema.md               # Updated: page format spec
├── py-agent/
│   ├── ingest.py                   # NEW: two-stage ingestion pipeline
│   └── tools.py                    # + ingest_to_kb tool
```

---

### Task 1: KB structure update + schema.md + purpose.md + index.md + log.md

**Files:**
- Create: `knowledge/team-wiki/purpose.md`
- Create: `knowledge/team-wiki/index.md`
- Create: `knowledge/team-wiki/log.md`
- Create: `knowledge/team-wiki/raw/sources/`
- Modify: `knowledge/team-wiki/schema.md`

- [ ] **Step 1: Create directory structure**

```powershell
New-Item -ItemType Directory -Force -Path "C:\Users\12991\Desktop\Cococlaw\knowledge\team-wiki\raw\sources" | Out-Null
```

- [ ] **Step 2: Create purpose.md**

```markdown
# Team Wiki Purpose

A shared knowledge base documenting the CocoCat system architecture, components, and team practices.

## Goals
- Document system architecture decisions
- Share knowledge about tools and workflows
- Onboard new team members
```

- [ ] **Step 3: Create empty index.md**

```markdown
# Team Wiki Index

Auto-generated catalog. Last updated: (pending)

## Entities
(none yet)

## Concepts
(none yet)
```

- [ ] **Step 4: Create empty log.md**

```markdown
# Team Wiki Log

Append-only operation log.

```

- [ ] **Step 5: Update schema.md**

```markdown
# Team Wiki Schema

## Page Types
- `entities/{slug}.md` — Named things (agents, tools, projects)
- `concepts/{slug}.md` — Ideas, patterns, techniques
- `sources/{slug}.md` — Source document summaries

## Page Format
Every page uses YAML frontmatter:

---
type: entity | concept | source
title: Human-readable title
created: YYYY-MM-DD
sources: ["source-filename"]
tags: ["tag1", "tag2"]
related: ["page-slug"]
---
```

- [ ] **Step 6: Commit**

```bash
git add knowledge/
git commit -m "feat: update KB structure with purpose, index, log, and YAML frontmatter schema"
```

---

### Task 2: Create ingestion pipeline (ingest.py)

**Files:**
- Create: `py-agent/ingest.py`

- [ ] **Step 1: Create ingest.py**

```python
"""Two-stage KB ingestion pipeline (llm-wiki pattern)."""
import os
import json
import re
from datetime import datetime
from llm import LLMClient


ANALYSIS_PROMPT = """You are a knowledge base ingestion analyst. Analyze the following source document and produce a structured analysis.

## Source Document
{source_content}

## KB Purpose
{kb_purpose}

## Schema Rules
{schema}

## Output Format
Return a JSON object with these fields:
{{
  "title": "Document title",
  "type": "entity or concept or source",
  "summary": "One-paragraph summary of the document",
  "entities": ["entity names found"],
  "concepts": ["concept names found"],
  "key_points": ["key point 1", "key point 2"],
  "tags": ["tag1", "tag2"],
  "related": ["existing related page slugs"]
}}
"""


GENERATION_PROMPT = """You are a knowledge base writer. Based on the analysis below, generate a wiki page for the knowledge base.

## Analysis
{analysis_json}

## Existing Content (for context)
{existing_content}

## Task
Write a single wiki page in markdown with YAML frontmatter.

Frontmatter fields:
- type: {page_type}
- title: {title}
- created: {today}
- sources: [{source_filename}]
- tags: [{tags}]
- related: [{related}]

The body should be well-structured markdown with:
- A clear heading structure
- Bullet points for key information
- Links to related concepts where relevant

Return ONLY the page content with frontmatter, no additional text.
"""


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    return text[:60]


def _find_kb_dir() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "knowledge")


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def write_text(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def run_ingest(kb_id: str, source_filename: str, llm_client=None) -> str:
    """Two-stage ingestion pipeline. Returns summary string."""
    llm = llm_client or LLMClient()
    kb_dir = os.path.join(_find_kb_dir(), kb_id)
    source_path = os.path.join(kb_dir, "raw", "sources", source_filename)

    if not os.path.exists(source_path):
        return f"Source file not found: {source_path}"

    # Read source file
    source_content = read_text(source_path)
    source_content = source_content[:4000]  # Cap for MVP

    # Read KB config files
    kb_purpose = ""
    purpose_path = os.path.join(kb_dir, "purpose.md")
    if os.path.exists(purpose_path):
        kb_purpose = read_text(purpose_path)[:1000]

    schema = ""
    schema_path = os.path.join(kb_dir, "schema.md")
    if os.path.exists(schema_path):
        schema = read_text(schema_path)[:1000]

    # Read existing wiki pages for context
    existing_content = ""
    wiki_dir = os.path.join(kb_dir, "wiki")
    if os.path.isdir(wiki_dir):
        lines = []
        for root, dirs, files in os.walk(wiki_dir):
            for f in files:
                if f.endswith(".md"):
                    rel = os.path.relpath(os.path.join(root, f), wiki_dir)
                    try:
                        content = read_text(os.path.join(root, f))
                        lines.append(f"--- {rel} ---\n{content[:500]}")
                    except Exception:
                        pass
        existing_content = "\n\n".join(lines[:10])

    # === Phase 1: Analysis ===
    analysis_prompt = ANALYSIS_PROMPT.format(
        source_content=source_content,
        kb_purpose=kb_purpose,
        schema=schema,
    )
    analysis_text = ""
    try:
        resp = llm.chat(
            messages=[{"role": "user", "content": analysis_prompt}],
            max_tokens=1024,
            temperature=0.3,
        )
        analysis_text = (resp.get("content") or "").strip()
        # Try to parse as JSON
        analysis = json.loads(analysis_text)
    except (json.JSONDecodeError, Exception):
        # Fallback: construct analysis from text
        analysis = {
            "title": source_filename.replace(".md", "").replace("-", " ").title(),
            "type": "concept",
            "summary": analysis_text[:500],
            "entities": [],
            "concepts": [],
            "key_points": [],
            "tags": [],
            "related": [],
        }

    title = analysis.get("title", source_filename)
    page_type = analysis.get("type", "concept")
    tags = analysis.get("tags", [])
    related = analysis.get("related", [])
    today = datetime.now().strftime("%Y-%m-%d")
    slug = slugify(title)

    # === Phase 2: Generation ===
    gen_prompt = GENERATION_PROMPT.format(
        page_type=page_type,
        title=title,
        today=today,
        source_filename=source_filename,
        tags=", ".join(tags) if tags else "none",
        related=", ".join(related) if related else "none",
        analysis_json=json.dumps(analysis, indent=2),
        existing_content=existing_content[:2000],
    )

    page_content = ""
    try:
        resp = llm.chat(
            messages=[{"role": "user", "content": gen_prompt}],
            max_tokens=1536,
            temperature=0.3,
        )
        page_content = (resp.get("content") or "").strip()
    except Exception as e:
        page_content = f"Error generating page: {e}"

    # Write page
    type_dir = page_type + "s" if not page_type.endswith("s") else page_type + ""
    if page_type == "entity":
        subdir = "entities"
    elif page_type == "concept":
        subdir = "concepts"
    else:
        subdir = page_type + "s"

    page_dir = os.path.join(wiki_dir, subdir)
    page_path = os.path.join(page_dir, f"{slug}.md")
    write_text(page_path, page_content)
    _update_index(kb_dir, wiki_dir)
    _append_log(kb_dir, title, slug, source_filename)

    return f"Ingested '{source_filename}' → created '{subdir}/{slug}.md' ({page_type})"


def _update_index(kb_dir: str, wiki_dir: str):
    """Rebuild index.md from wiki directory structure."""
    entities = []
    concepts = []
    if os.path.isdir(wiki_dir):
        for root, dirs, files in os.walk(wiki_dir):
            for f in files:
                if f.endswith(".md"):
                    rel = os.path.relpath(os.path.join(root, f), wiki_dir)
                    if rel.startswith("entities"):
                        entities.append(f.replace(".md", ""))
                    elif rel.startswith("concepts"):
                        concepts.append(f.replace(".md", ""))
    content = "# Team Wiki Index\n\n"
    content += f"Auto-generated. Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    if entities:
        content += "## Entities\n"
        for e in sorted(entities):
            content += f"- [[{e}]]\n"
        content += "\n"
    if concepts:
        content += "## Concepts\n"
        for c in sorted(concepts):
            content += f"- [[{c}]]\n"
    write_text(os.path.join(kb_dir, "index.md"), content)


def _append_log(kb_dir: str, title: str, slug: str, source: str):
    """Append an operation entry to log.md."""
    entry = f"- {datetime.now().strftime('%Y-%m-%d %H:%M')} | Ingested '{source}' → {slug}.md | {title}\n"
    log_path = os.path.join(kb_dir, "log.md")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)
```

- [ ] **Step 2: Test import**

```powershell
python -c "import sys; sys.path.insert(0,'py-agent'); from ingest import run_ingest, slugify; print('slug test:', slugify('Hello World! Test')); print('import ok')"
```

- [ ] **Step 3: Commit**

```bash
git add py-agent/ingest.py
git commit -m "feat: add two-stage KB ingestion pipeline"
```

---

### Task 3: Add ingest_to_kb tool

**Files:**
- Modify: `py-agent/tools.py`

- [ ] **Step 1: Add IngestToKbTool class**

Read `C:\Users\12991\Desktop\Cococlaw\py-agent\tools.py`. Add after `DreamTool` class:

```python
class IngestToKbTool(Tool):
    """Ingest a raw source file into a knowledge base. Two-stage LLM pipeline: analyze then generate wiki pages."""
    name = "ingest_to_kb"
    description = "Process a raw source file into structured wiki pages in a knowledge base. Specify kb_id and source_filename (relative to knowledge/{kb}/raw/sources/)."
    parameters = {
        "type": "object",
        "properties": {
            "kb_id": {"type": "string", "description": "Knowledge base ID (e.g. team-wiki)"},
            "source_filename": {"type": "string", "description": "Source filename in knowledge/{kb}/raw/sources/"},
        },
        "required": ["kb_id", "source_filename"],
    }

    def execute(self, kb_id="", source_filename="", **kwargs) -> str:
        from ingest import run_ingest
        try:
            result = run_ingest(kb_id, source_filename)
            return result
        except Exception as e:
            return f"Ingestion failed: {e}"
```

- [ ] **Step 2: Register in create_default_registry**

Add before `return registry`:
```python
    registry.register(IngestToKbTool())
```

- [ ] **Step 3: Test**

```powershell
python -c "import sys; sys.path.insert(0,'py-agent'); from tools import IngestToKbTool; print('ingest tool ok')"
```

- [ ] **Step 4: Commit**

```bash
git add py-agent/tools.py
git commit -m "feat: add ingest_to_kb tool for agent use"
```

---

### Task 4: End-to-end test

- [ ] **Step 1: Create a test source file**

```powershell
New-Item -ItemType Directory -Force -Path "C:\Users\12991\Desktop\Cococlaw\knowledge\team-wiki\raw\sources" | Out-Null
@'
# CocoCat Message Bus Architecture

The message bus is the central communication layer in CocoCat.

## Components
- Rust Core: spawns agents, routes messages
- JSON-RPC: line-delimited protocol over stdin/stdout
- Dispatch Queue: file-based async message passing
- Chat Log: append-only group.jsonl

## Flow
1. Leader calls dispatch_task tool
2. Tool writes JSON to agents/dispatch_queue/
3. Rust reads queue and forwards to target agent
4. Response is returned and logged to chat
'@ | Out-File -Encoding utf8 "C:\Users\12991\Desktop\Cococlaw\knowledge\team-wiki\raw\sources\message-bus-architecture.md"
```

- [ ] **Step 2: Run ingestion directly**

```powershell
$env:OPENAI_API_KEY = "sk-055b943d0a2d4212a7c8bc0064623a45"
$env:OPENAI_BASE_URL = "https://api.deepseek.com"
$env:LLM_MODEL = "deepseek-v4-flash"
python -c "import sys; sys.path.insert(0,'py-agent'); from ingest import run_ingest; r = run_ingest('team-wiki', 'message-bus-architecture.md'); print(r)"
```

- [ ] **Step 3: Verify output**

```powershell
Write-Output "=== New page ==="
Get-ChildItem "C:\Users\12991\Desktop\Cococlaw\knowledge\team-wiki\wiki\*" -Recurse -Filter "*.md" | Select-Object -ExpandProperty Name
Write-Output "`n=== Index ==="
Get-Content "C:\Users\12991\Desktop\Cococlaw\knowledge\team-wiki\index.md" -Tail 10
Write-Output "`n=== Log ==="
Get-Content "C:\Users\12991\Desktop\Cococlaw\knowledge\team-wiki\log.md"
```

- [ ] **Step 4: Commit**

```bash
git add knowledge/team-wiki/raw/sources/message-bus-architecture.md knowledge/team-wiki/wiki/ knowledge/team-wiki/index.md knowledge/team-wiki/log.md
git commit -m "feat: verify KB ingestion pipeline end-to-end"
```
