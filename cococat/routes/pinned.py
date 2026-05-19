"""Pinned facts routes — CRUD for frontend."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
import os

from cococat.app import get_ctx
from cococat.context import AppContext

router = APIRouter(prefix="/api/pinned", tags=["pinned"])


class PinRequest(BaseModel):
    fact: str


class UnpinRequest(BaseModel):
    keyword: str


def _pinned_path(ctx: AppContext) -> str:
    user_id = ctx.user_id or "admin"
    return f"agents/{user_id}/pinned.md"


def _read_pinned(ctx: AppContext) -> str:
    path = _pinned_path(ctx)
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write_pinned(ctx: AppContext, content: str) -> None:
    path = _pinned_path(ctx)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


@router.get("")
async def list_pinned(ctx: AppContext = Depends(get_ctx)):
    return {"facts": _read_pinned(ctx)}


@router.post("")
async def add_pinned(req: PinRequest, ctx: AppContext = Depends(get_ctx)):
    fact = req.fact.strip()
    if not fact:
        raise HTTPException(status_code=400, detail="fact is required")
    content = _read_pinned(ctx)
    content = content.rstrip("\n") + "\n" + fact + "\n"
    _write_pinned(ctx, content)
    return {"status": "pinned", "fact": fact}


@router.delete("")
async def remove_pinned(req: UnpinRequest, ctx: AppContext = Depends(get_ctx)):
    keyword = req.keyword.strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="keyword is required")
    content = _read_pinned(ctx)
    lines = content.split("\n")
    kept = [l for l in lines if keyword.lower() not in l.lower()]
    _write_pinned(ctx, "\n".join(kept))
    return {"status": "unpinned", "keyword": keyword}
