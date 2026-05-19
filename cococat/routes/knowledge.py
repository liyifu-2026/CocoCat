"""KB upload route — handles file upload and ingest task creation."""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
from cococat.db import new_uuid
from cococat.app import get_ctx
from cococat.context import AppContext

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class CreateKBRequest(BaseModel):
    name: str
    purpose: str = ""


@router.post("/{kb_name}/upload")
async def upload_file(
    kb_name: str,
    ctx: AppContext = Depends(get_ctx),
    file: UploadFile = File(...),
):
    """Upload a file to a knowledge base for ingestion."""
    import os

    kb_dir = str(ctx.config_store.knowledge_dir / kb_name)
    raw_dir = os.path.join(kb_dir, "raw", "sources")
    os.makedirs(raw_dir, exist_ok=True)

    content = await file.read()
    file_path = os.path.join(raw_dir, file.filename or "upload.bin")
    with open(file_path, "wb") as f:
        f.write(content)

    task_uuid = new_uuid()
    ctx.db.tasks.create(
        task_uuid=task_uuid,         target_agent="kb-agent", source="kb",
        method="process_kb_source",
        params=f'{{"kb_name": "{kb_name}", "filename": "{file.filename}"}}',
    )

    return {
        "status": "queued",
        "task_uuid": task_uuid,
        "kb_name": kb_name,
        "filename": file.filename,
    }


@router.get("")
async def list_kbs(ctx: AppContext = Depends(get_ctx)):
    """List all knowledge bases."""
    import os
    kb_dir = str(ctx.config_store.knowledge_dir)
    if not os.path.isdir(kb_dir):
        return {"kbs": []}

    kbs = []
    for name in os.listdir(kb_dir):
        path = os.path.join(kb_dir, name)
        if os.path.isdir(path) and not name.startswith("."):
            purpose = ""
            purpose_path = os.path.join(path, "purpose.md")
            if os.path.exists(purpose_path):
                with open(purpose_path, encoding="utf-8") as f:
                    purpose = f.read(300)
            kbs.append({"id": name, "purpose": purpose})

    return {"kbs": kbs}


@router.post("")
async def create_knowledge(body: CreateKBRequest, ctx: AppContext = Depends(get_ctx)):
    """Create a new knowledge base."""
    import os
    base = str(ctx.config_store.knowledge_dir / body.name)
    if os.path.exists(os.path.join(base, "wiki")):
        raise HTTPException(status_code=409, detail=f"Knowledge base '{body.name}' already exists")
    dirs = [
        os.path.join(base, "wiki", "entities"),
        os.path.join(base, "wiki", "concepts"),
        os.path.join(base, "raw", "sources"),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
    with open(os.path.join(base, "purpose.md"), "w", encoding="utf-8") as f:
        f.write(f"# {body.name}\n\n{body.purpose or 'Knowledge base for ' + body.name}\n")
    with open(os.path.join(base, "index.md"), "w", encoding="utf-8") as f:
        f.write(f"# {body.name} Index\n\n## Entities\n\n## Concepts\n")
    with open(os.path.join(base, "log.md"), "w", encoding="utf-8") as f:
        f.write(f"# {body.name} Change Log\n\n")
    return {"status": "created", "name": body.name}


@router.get("/{kb_name}/wiki")
async def wiki_index(kb_name: str, ctx: AppContext = Depends(get_ctx)):
    """Get wiki index for a KB."""
    import os
    kb_path = str(ctx.config_store.knowledge_dir / kb_name)
    if not os.path.isdir(kb_path):
        return {"error": "not found"}, 404

    entities = _list_dir(os.path.join(kb_path, "wiki", "entities"))
    concepts = _list_dir(os.path.join(kb_path, "wiki", "concepts"))

    return {"entities": entities, "concepts": concepts}


@router.get("/{kb_name}/wiki/{page_type}/{page_name}")
async def wiki_page(kb_name: str, page_type: str, page_name: str, ctx: AppContext = Depends(get_ctx)):
    """Read a wiki page."""
    import os
    path = str(ctx.config_store.knowledge_dir / kb_name / "wiki" / page_type / f"{page_name}.md")
    if not os.path.exists(path):
        return {"error": "not found"}, 404

    with open(path, encoding="utf-8") as f:
        content = f.read(10000)

    return {"name": page_name, "type": page_type, "content": content}


@router.get("/{kb_name}/search")
async def search_kb(kb_name: str, q: str = "", ctx: AppContext = Depends(get_ctx)):
    """Search KB wiki pages."""
    import os
    wiki_dir = str(ctx.config_store.knowledge_dir / kb_name / "wiki")
    if not os.path.isdir(wiki_dir) or not q:
        return {"results": []}

    results = []
    for root, _, files in os.walk(wiki_dir):
        for fname in files:
            if not fname.endswith(".md"):
                continue
            path = os.path.join(root, fname)
            with open(path, encoding="utf-8") as f:
                content = f.read(5000)
            if q.lower() in content.lower():
                rel = os.path.relpath(root, wiki_dir)
                results.append({
                    "name": fname[:-3],
                    "type": rel,
                    "snippet": content[:200],
                })

    return {"results": results[:20]}


@router.get("/{kb_name}/graph")
async def knowledge_graph(kb_name: str, ctx: AppContext = Depends(get_ctx)):
    """Get knowledge graph data for visualization."""
    import os
    from cococat.ingest.graph import KnowledgeGraph

    kb_path = str(ctx.config_store.knowledge_dir / kb_name)
    if not os.path.isdir(kb_path):
        return {"error": "not found"}, 404

    graph = KnowledgeGraph(kb_path)
    return {
        "graph": graph.to_d3(),
        "insights": graph.insights(),
    }


def _list_dir(path: str) -> list[str]:
    import os
    if not os.path.isdir(path):
        return []
    return sorted(
        f[:-3] for f in os.listdir(path) if f.endswith(".md") and not f.startswith(".")
    )
