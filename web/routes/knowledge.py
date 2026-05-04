"""Knowledge base routes.

TODO: Migrate all endpoints to proxy through Rust HTTP API:
  - GET /api/knowledge/{kb_id} → Rust GET /api/knowledge/{kb_id}
  - GET /api/knowledge/{kb_id}/wiki → Rust GET /api/knowledge/{kb_id}/wiki
  - GET /api/knowledge/{kb_id}/wiki/{type}/{name} → Rust equivalent
  - GET /api/knowledge/{kb_id}/search → Rust GET /api/knowledge/{kb_id}/search
"""
import json
import re
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent


@router.get("/api/knowledge/{kb_id}")
def get_knowledge_base(kb_id: str):
    kb_dir = BASE_DIR / "knowledge" / kb_id
    if not kb_dir.exists():
        return JSONResponse({"error": "knowledge base not found"}, status_code=404)

    result = {"id": kb_id}
    for name in ("purpose.md", "schema.md", "index.md"):
        path = kb_dir / name
        if path.exists():
            result[name.replace(".md", "")] = path.read_text(encoding="utf-8")
    return result


@router.get("/api/knowledge/{kb_id}/wiki")
def list_wiki_pages(kb_id: str):
    wiki_dir = BASE_DIR / "knowledge" / kb_id / "wiki"
    if not wiki_dir.exists():
        return {"pages": []}

    pages = []
    for type_dir in wiki_dir.iterdir():
        if not type_dir.is_dir():
            continue
        page_type = type_dir.name
        for md_file in sorted(type_dir.iterdir()):
            if md_file.suffix != ".md":
                continue
            name = md_file.stem
            content = md_file.read_text(encoding="utf-8")
            title = name
            tags = []

            fm_match = re.match(r"^---\n(.+?)\n---", content, re.DOTALL)
            if fm_match:
                fm = fm_match.group(1)
                tm = re.search(r"^title:\s*\"?(.+?)\"?\s*$", fm, re.MULTILINE)
                if tm:
                    title = tm.group(1).strip()
                tgm = re.search(r"^tags:\s*\[(.+?)\]", fm, re.DOTALL)
                if tgm:
                    tags = [t.strip().strip("\"'") for t in tgm.group(1).split(",")]

            pages.append({
                "name": name,
                "title": title,
                "type": page_type,
                "tags": tags,
                "path": f"/api/knowledge/{kb_id}/wiki/{page_type}/{name}",
            })

    return {"pages": pages}


@router.get("/api/knowledge/{kb_id}/wiki/{page_type}/{page_name}")
def get_wiki_page(kb_id: str, page_type: str, page_name: str):
    md_path = BASE_DIR / "knowledge" / kb_id / "wiki" / page_type / f"{page_name}.md"
    if not md_path.exists():
        return JSONResponse({"error": "page not found"}, status_code=404)

    content = md_path.read_text(encoding="utf-8")
    frontmatter = {}

    fm_match = re.match(r"^---\n(.+?)\n---\n*(.*)", content, re.DOTALL)
    if fm_match:
        fm_text = fm_match.group(1)
        body = fm_match.group(2)
        for line in fm_text.split("\n"):
            if ":" in line:
                k, _, v = line.partition(":")
                frontmatter[k.strip()] = v.strip().strip("\"'")
    else:
        body = content

    return {
        "frontmatter": frontmatter,
        "body": body.strip(),
    }


@router.get("/api/knowledge/{kb_id}/search")
def search_wiki(kb_id: str, q: str = ""):
    wiki_dir = BASE_DIR / "knowledge" / kb_id / "wiki"
    if not wiki_dir.exists() or not q:
        return {"results": []}

    q_lower = q.lower()
    results = []

    for type_dir in wiki_dir.iterdir():
        if not type_dir.is_dir():
            continue
        for md_file in type_dir.iterdir():
            if md_file.suffix != ".md":
                continue
            content = md_file.read_text(encoding="utf-8")
            if q_lower not in content.lower():
                continue

            name = md_file.stem
            page_type = type_dir.name
            title = name
            snippet = ""

            fm_match = re.match(r"^---\n(.+?)\n---\n*(.*)", content, re.DOTALL)
            if fm_match:
                fm = fm_match.group(1)
                body = fm_match.group(2)
                tm = re.search(r"^title:\s*\"?(.+?)\"?\s*$", fm, re.MULTILINE)
                if tm:
                    title = tm.group(1).strip()
                body_lower = body.lower()
                idx = body_lower.find(q_lower)
                if idx >= 0:
                    start = max(0, idx - 60)
                    end = min(len(body), idx + len(q) + 60)
                    snippet = body[start:end].replace("\n", " ")
            else:
                body = content
                idx = body.lower().find(q_lower)
                if idx >= 0:
                    start = max(0, idx - 60)
                    end = min(len(body), idx + len(q) + 60)
                    snippet = body[start:end].replace("\n", " ")

            results.append({
                "name": name,
                "title": title,
                "type": page_type,
                "path": f"/api/knowledge/{kb_id}/wiki/{page_type}/{name}",
                "snippet": snippet.strip(),
            })

    return {"results": results}
