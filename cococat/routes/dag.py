"""DAG routes — list runs and run detail."""
import os
import logging

import yaml
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger("cococat.routes.dag")

router = APIRouter(prefix="/api", tags=["dag"])


def _dag_dir() -> str:
    return os.environ.get("COCOCAT_DAG_DIR", "runs")


@router.get("/dag")
async def list_dag_runs(session_id: str | None = Query(default=None)):
    """List DAG runs. Optionally filter by session_id."""
    dag_dir = _dag_dir()
    if not os.path.isdir(dag_dir):
        return {"runs": []}

    runs = []
    for run_dir in sorted(os.listdir(dag_dir)):
        dag_path = os.path.join(dag_dir, run_dir, "dag.yaml")
        if not os.path.exists(dag_path):
            continue
        try:
            with open(dag_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except (yaml.YAMLError, OSError):
            continue

        if session_id and data.get("session_id") != session_id:
            continue

        runs.append(data)

    return {"runs": runs}


@router.get("/dag/{run_id}")
async def get_dag_run(run_id: str):
    """Get a single DAG run by ID."""
    dag_dir = _dag_dir()
    dag_path = os.path.join(dag_dir, run_id, "dag.yaml")

    if not os.path.exists(dag_path):
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    try:
        with open(dag_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        raise HTTPException(status_code=500, detail=f"Error reading DAG: {e}")

    return data
