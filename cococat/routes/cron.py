"""Cron routes — list, create, update, delete cron job files in runs/cron/."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from cococat.app import get_ctx
from cococat.context import AppContext
from cococat.core.cron_worker import _parse_schedule, _to_timestamp

logger = logging.getLogger("cococat.routes.cron")

router = APIRouter(prefix="/api/cron", tags=["cron"])


class CronEntry(BaseModel):
    id: str
    agent_id: str
    name: str
    schedule: str
    task: str
    status: str = "active"
    last_run: str | None = None
    at_time: str | None = None
    created_at: str
    error: str | None = None


class CronCreate(BaseModel):
    id: str
    agent_id: str
    name: str
    schedule: str
    task: str
    at_time: str | None = None


class CronUpdate(BaseModel):
    schedule: str | None = None
    task: str | None = None
    status: str | None = None
    at_time: str | None = None


def _read_cron_file(filename: str, cron_dir: str) -> dict | None:
    filepath = os.path.join(cron_dir, filename)
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _write_cron_file(filename: str, entry: dict, cron_dir: str) -> None:
    os.makedirs(cron_dir, exist_ok=True)
    filepath = os.path.join(cron_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(entry, f, indent=2, ensure_ascii=False)


def _compute_next_run(entry: dict) -> str | None:
    interval = _parse_schedule(entry.get("schedule", ""))
    if interval is None or interval <= 0:
        return None
    last_run = _to_timestamp(entry.get("last_run", 0))
    at_time = entry.get("at_time", "")
    if at_time and interval >= 86400:
        try:
            h, m = map(int, at_time.strip().split(":"))
        except (ValueError, IndexError):
            pass
        else:
            now = datetime.now()
            candidate = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if candidate <= now:
                candidate = candidate.replace(day=candidate.day + 1)
            if last_run > 0 and last_run + interval > candidate.timestamp():
                return datetime.fromtimestamp(last_run + interval).isoformat()
            return candidate.isoformat()
    return datetime.fromtimestamp(last_run + interval).isoformat()


@router.get("")
async def list_cron(ctx: AppContext = Depends(get_ctx)):
    cron_dir = str(ctx.config_store.cron_dir)
    if not os.path.isdir(cron_dir):
        return {"entries": []}
    entries = []
    for filename in sorted(os.listdir(cron_dir)):
        if not filename.endswith(".json"):
            continue
        entry = _read_cron_file(filename, cron_dir)
        if entry is None:
            continue
        entry["next_run"] = _compute_next_run(entry)
        entries.append(entry)
    return {"entries": entries}


@router.post("")
async def create_cron(body: CronCreate, ctx: AppContext = Depends(get_ctx)):
    cron_dir = str(ctx.config_store.cron_dir)
    filename = f"{body.id}.json"
    if os.path.exists(os.path.join(cron_dir, filename)):
        raise HTTPException(status_code=409, detail=f"Cron job '{body.id}' already exists")
    if _parse_schedule(body.schedule) is None:
        raise HTTPException(status_code=400, detail=f"Unparseable schedule: {body.schedule}")
    entry = {
        "id": body.id,
        "agent_id": body.agent_id,
        "name": body.name,
        "schedule": body.schedule,
        "task": body.task,
        "at_time": body.at_time,
        "status": "active",
        "last_run": 0,
        "created_at": datetime.now().isoformat(),
    }
    _write_cron_file(filename, entry, cron_dir)
    return entry


@router.patch("/{cron_id}")
async def update_cron(cron_id: str, body: CronUpdate, ctx: AppContext = Depends(get_ctx)):
    cron_dir = str(ctx.config_store.cron_dir)
    filename = f"{cron_id}.json"
    entry = _read_cron_file(filename, cron_dir)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Cron job '{cron_id}' not found")
    changed = False
    if body.schedule is not None:
        if _parse_schedule(body.schedule) is None:
            raise HTTPException(status_code=400, detail=f"Unparseable schedule: {body.schedule}")
        entry["schedule"] = body.schedule
        changed = True
    if body.task is not None:
        entry["task"] = body.task
        changed = True
    if body.at_time is not None:
        entry["at_time"] = body.at_time if body.at_time else ""
        changed = True
    if body.status is not None:
        if body.status not in ("active", "paused"):
            raise HTTPException(status_code=400, detail="Status must be 'active' or 'paused'")
        entry["status"] = body.status
        changed = True
    if changed:
        _write_cron_file(filename, entry, cron_dir)
    entry["next_run"] = _compute_next_run(entry)
    return entry


@router.delete("/{cron_id}")
async def delete_cron(cron_id: str, ctx: AppContext = Depends(get_ctx)):
    cron_dir = str(ctx.config_store.cron_dir)
    filename = f"{cron_id}.json"
    filepath = os.path.join(cron_dir, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"Cron job '{cron_id}' not found")
    os.remove(filepath)
    return {"status": "deleted", "id": cron_id}
