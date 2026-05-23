"""KB routes — file upload, list, search, wiki pages."""
import asyncio
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
from cococat.app import get_ctx
from cococat.context import AppContext
from cococat.core.knowledge_service import KnowledgeService

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class CreateKBRequest(BaseModel):
    name: str
    purpose: str = ""


def _get_service(ctx: AppContext) -> KnowledgeService:
    return KnowledgeService(str(ctx.config_store.knowledge_dir))


def _trigger_ingest(ctx: AppContext, kb_name: str, filename: str) -> None:
    """Fire-and-forget ingest via sandbox."""
    sandbox = ctx.sandbox_provider
    if sandbox:
        from cococat.core.tools import resolve_tools_for_mode, resolve_tavily_key
        sub_executor = ctx.sub_executor
        tools = resolve_tools_for_mode(
            "kb-admin",
            sub_agent_executor=sub_executor.dispatch if sub_executor else None,
            tavily_api_key=resolve_tavily_key(ctx.config_store),
        )
        asyncio.create_task(sandbox.run_once(
            prompt=f"Ingest file '{filename}' into knowledge base '{kb_name}'",
            agent_id="kb",
            mode="kb-admin",
            tools=tools,
        ))


@router.post("/{kb_name}/upload")
async def upload_file(
    kb_name: str,
    ctx: AppContext = Depends(get_ctx),
    file: UploadFile = File(...),
):
    content = await file.read()
    svc = _get_service(ctx)
    svc.save_upload(kb_name, file.filename or "upload.bin", content)
    _trigger_ingest(ctx, kb_name, file.filename or "upload.bin")
    return {"status": "queued", "filename": file.filename, "kb_name": kb_name}


@router.get("")
async def list_kbs(ctx: AppContext = Depends(get_ctx)):
    return {"kbs": _get_service(ctx).list_kbs()}


@router.post("")
async def create_knowledge(body: CreateKBRequest, ctx: AppContext = Depends(get_ctx)):
    svc = _get_service(ctx)
    error = svc.create_kb(body.name, body.purpose)
    if error:
        raise HTTPException(status_code=409, detail=error)
    return {"status": "created", "name": body.name}


@router.get("/{kb_name}/wiki")
async def wiki_index(kb_name: str, ctx: AppContext = Depends(get_ctx)):
    entities, concepts = _get_service(ctx).wiki_index(kb_name)
    return {"entities": entities, "concepts": concepts}


@router.get("/{kb_name}/wiki/{page_type}/{page_name}")
async def wiki_page(kb_name: str, page_type: str, page_name: str, ctx: AppContext = Depends(get_ctx)):
    page = _get_service(ctx).wiki_page(kb_name, page_type, page_name)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return page


@router.get("/{kb_name}/search")
async def search_kb(kb_name: str, q: str = "", ctx: AppContext = Depends(get_ctx)):
    return {"results": _get_service(ctx).search(kb_name, q)}


@router.get("/{kb_name}/graph")
async def knowledge_graph(kb_name: str, ctx: AppContext = Depends(get_ctx)):
    import os
    from cococat.ingest.graph import KnowledgeGraph
    kb_path = str(ctx.config_store.knowledge_dir / kb_name)
    if not os.path.isdir(kb_path):
        raise HTTPException(status_code=404, detail="Page not found")
    graph = KnowledgeGraph(kb_path)
    return {"graph": graph.to_d3(), "insights": graph.insights()}
