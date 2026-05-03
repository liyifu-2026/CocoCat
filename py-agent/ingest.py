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
- Use [[Wikilink]] format to link to related pages (e.g. [[cococat]] or [[multi-agent-systems]])
- Add a "## See Also" section at the end with [[wikilinks]] to related pages

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


def _update_related_pages(kb_dir: str, wiki_dir: str, new_slug: str, related: list):
    """After creating a new page, update ALL related pages to cross-reference back."""
    if not related:
        return
    for root, dirs, files in os.walk(wiki_dir):
        for f in files:
            if not f.endswith(".md"):
                continue
            rel = os.path.relpath(os.path.join(root, f), wiki_dir)
            slug = f.replace(".md", "")
            if slug == new_slug:
                continue
            content = read_text(os.path.join(root, f))
            # Check if this page should link back
            for related_slug in related:
                if slug == related_slug and f"[[{new_slug}" not in content:
                    # Add cross-reference
                    if "related:" in content.split("---")[1] if content.startswith("---") else False:
                        # Update YAML frontmatter
                        parts = content.split("---")
                        if len(parts) >= 3:
                            front = parts[1]
                            if f"- {new_slug}" not in front:
                                front = front.rstrip() + f"\n  - {new_slug}\n"
                                parts[1] = front
                                write_text(os.path.join(root, f), "---".join(parts))
                    # Also add a [[wikilink]] in the body
                    body_start = content.find("---", content.find("---") + 1) + 3 if content.startswith("---") else 0
                    body = content[body_start:]
                    # Add link in "See also" section
                    if "## See Also" not in body and "## Related" not in body:
                        body += f"\n## See Also\n- [[{new_slug}]]\n"
                        write_text(os.path.join(root, f), content[:body_start] + body)


def run_ingest(kb_id: str, source_filename: str, llm_client=None) -> str:
    """Two-stage ingestion pipeline. Returns summary string."""
    llm = llm_client or LLMClient()
    kb_dir = os.path.join(_find_kb_dir(), kb_id)
    source_path = os.path.join(kb_dir, "raw", "sources", source_filename)

    if not os.path.exists(source_path):
        return f"Source file not found: {source_path}"

    source_content = read_text(source_path)
    source_content = source_content[:4000]

    kb_purpose = ""
    purpose_path = os.path.join(kb_dir, "purpose.md")
    if os.path.exists(purpose_path):
        kb_purpose = read_text(purpose_path)[:1000]

    schema = ""
    schema_path = os.path.join(kb_dir, "schema.md")
    if os.path.exists(schema_path):
        schema = read_text(schema_path)[:1000]

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
    analysis = None
    try:
        resp = llm.chat(
            messages=[{"role": "user", "content": analysis_prompt}],
            max_tokens=1024,
            temperature=0.3,
        )
        analysis_text = (resp.get("content") or "").strip()
        analysis = json.loads(analysis_text)
    except (json.JSONDecodeError, Exception):
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
        tags=", ".join(tags) if tags else "",
        related=", ".join(related) if related else "",
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
    _update_related_pages(kb_dir, wiki_dir, slug, related)
    _append_log(kb_dir, title, slug, source_filename)

    return f"Ingested '{source_filename}' -> created '{subdir}/{slug}.md' ({page_type}), updated {len(related)} related pages"


def _update_index(kb_dir: str, wiki_dir: str):
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
            content += f"- {e}\n"
        content += "\n"
    if concepts:
        content += "## Concepts\n"
        for c in sorted(concepts):
            content += f"- {c}\n"
    write_text(os.path.join(kb_dir, "index.md"), content)


def _append_log(kb_dir: str, title: str, slug: str, source: str):
    entry = f"- {datetime.now().strftime('%Y-%m-%d %H:%M')} | Ingested '{source}' -> {slug}.md | {title}\n"
    log_path = os.path.join(kb_dir, "log.md")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)


def run_lint(kb_id: str) -> str:
    """Health-check a wiki. Returns report of issues found."""
    kb_dir = os.path.join(_find_kb_dir(), kb_id)
    wiki_dir = os.path.join(kb_dir, "wiki")
    if not os.path.isdir(wiki_dir):
        return f"Wiki not found: {kb_id}"
    issues = []
    all_pages = {}
    inbound_links = {}
    for root, dirs, files in os.walk(wiki_dir):
        for f in files:
            if not f.endswith(".md"):
                continue
            slug = f.replace(".md", "")
            path = os.path.join(root, f)
            content = read_text(path)
            all_pages[slug] = path
            # Find [[wikilinks]] in body
            for link in re.findall(r'\[\[([^\]]+)\]\]', content):
                target = link.split("|")[0].strip().lower()
                inbound_links.setdefault(target, []).append(slug)
    # Check orphans
    for slug in all_pages:
        if slug not in inbound_links and slug not in ("index", "log"):
            issues.append(f"Orphan page: '{slug}' has no inbound [[links]]")
    # Check broken wikilinks
    for target, sources in inbound_links.items():
        if target not in all_pages:
            issues.append(f"Broken link: '[[{target}]]' from {sources}")
    # Check frontmatter
    for slug, path in all_pages.items():
        content = read_text(path)
        if content.startswith("---"):
            parts = content.split("---")
            if len(parts) >= 3:
                front = parts[1]
                for field in ("type:", "title:", "created:"):
                    if field not in front:
                        issues.append(f"Missing frontmatter '{field}' in '{slug}'")
    if not issues:
        return f"Wiki '{kb_id}' is healthy: {len(all_pages)} pages, {len(inbound_links)} cross-references."
    report = f"Wiki '{kb_id}' lint found {len(issues)} issues:\n\n"
    for i, issue in enumerate(issues, 1):
        report += f"{i}. {issue}\n"
    return report


def run_save_to_kb(kb_id: str, title: str, content: str, page_type: str = "concept", llm_client=None) -> str:
    """Save a Q&A result or analysis as a new wiki page."""
    llm = llm_client or LLMClient()
    kb_dir = os.path.join(_find_kb_dir(), kb_id)
    wiki_dir = os.path.join(kb_dir, "wiki")
    subdir = "entities" if page_type == "entity" else "concepts"
    today = datetime.now().strftime("%Y-%m-%d")
    slug = slugify(title)
    gen_prompt = f"""Generate a wiki page with YAML frontmatter.

Frontmatter:
- type: {page_type}
- title: {title}
- created: {today}
- tags: [kb-qa]

Content:
{content[:3000]}

Use [[Wikilink]] format to reference related pages. Add a "## See Also" section.
Return ONLY the page with frontmatter."""
    try:
        resp = llm.chat(messages=[{"role": "user", "content": gen_prompt}], max_tokens=1024, temperature=0.3)
        page_content = (resp.get("content") or "").strip()
    except Exception as e:
        return f"Error generating page: {e}"
    page_dir = os.path.join(wiki_dir, subdir)
    page_path = os.path.join(page_dir, f"{slug}.md")
    write_text(page_path, page_content)
    _update_index(kb_dir, wiki_dir)
    _append_log(kb_dir, title, slug, f"qa:{title}")
    return f"Saved '{slug}.md' to {subdir}/"
