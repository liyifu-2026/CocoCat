"""DAG routes — list runs, run detail, delete (supports both SQLite and file storage)."""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from cococat.app import get_ctx
from cococat.context import AppContext

logger = logging.getLogger("cococat.routes.dag")

router = APIRouter(prefix="/api", tags=["dag"])


def _load_run_data(ctx: AppContext, run_id: str) -> dict | None:
    """Load DAG run data from active store."""
    store = ctx.dag_store
    if store is None:
        return None
    return store.load(run_id)


def _list_all_runs(ctx: AppContext) -> list[dict]:
    """List all DAG runs from active store."""
    store = ctx.dag_store
    if store is None:
        return []
    return store.list_all()


@router.get("/dag")
async def list_dag_runs(session_id: str | None = Query(default=None), ctx: AppContext = Depends(get_ctx)):
    """List DAG runs. Optionally filter by session_id."""
    runs = _list_all_runs(ctx)
    if session_id:
        runs = [r for r in runs if r.get("session_id") == session_id]
    return {"runs": runs}


@router.get("/dag/{run_id}")
async def get_dag_run(run_id: str, ctx: AppContext = Depends(get_ctx)):
    """Get a single DAG run by ID."""
    data = _load_run_data(ctx, run_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return data


@router.delete("/dag/{run_id}")
async def delete_dag_run(run_id: str, ctx: AppContext = Depends(get_ctx)):
    """Delete a DAG run."""
    store = ctx.dag_store
    if store is None:
        raise HTTPException(status_code=404, detail="DAG store not available")
    data = store.load(run_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    store.delete(run_id)
    return {"status": "deleted", "run_id": run_id}


@router.delete("/dag")
async def delete_dag_by_session(session_id: str = Query(...), ctx: AppContext = Depends(get_ctx)):
    """Delete all DAG runs for a session."""
    store = ctx.dag_store
    if store is None:
        return {"status": "no_store", "deleted": 0}

    deleted = 0
    for run in store.list_all():
        if run.get("session_id") == session_id:
            store.delete(run.get("run_id", ""))
            deleted += 1

    return {"status": "deleted", "count": deleted}