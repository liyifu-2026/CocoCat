"""User management routes."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

import bcrypt

from cococat.app import get_ctx
from cococat.context import AppContext

router = APIRouter(prefix="/api/users", tags=["users"])


class CreateUserRequest(BaseModel):
    username: str
    password: str


class ResetPasswordRequest(BaseModel):
    password: str


@router.get("")
async def list_users(ctx: AppContext = Depends(get_ctx)):
    rows = ctx.db._conn.execute(
        "SELECT id, display_name, created_at FROM users ORDER BY created_at"
    ).fetchall()
    return [{"id": r["id"], "display_name": r["display_name"] or "", "created_at": r["created_at"]} for r in rows]


@router.post("")
async def create_user(body: CreateUserRequest, ctx: AppContext = Depends(get_ctx)):
    username = body.username.strip()
    if not username or len(body.password) < 4:
        raise HTTPException(status_code=400, detail="Username required, password >= 4 chars")

    existing = ctx.db._conn.execute("SELECT id FROM users WHERE id = ?", (username,)).fetchone()
    if existing:
        raise HTTPException(status_code=409, detail="User already exists")

    password_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    ctx.db._conn.execute(
        "INSERT INTO users (id, password_hash) VALUES (?, ?)",
        (username, password_hash),
    )
    ctx.db._conn.commit()

    import os
    os.makedirs(f"config/users/{username}", exist_ok=True)
    os.makedirs(f"agents/{username}", exist_ok=True)

    return {"id": username, "status": "created"}


@router.delete("/{username}")
async def delete_user(username: str, ctx: AppContext = Depends(get_ctx)):
    existing = ctx.db._conn.execute("SELECT id FROM users WHERE id = ?", (username,)).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

    ctx.db._conn.execute("DELETE FROM users WHERE id = ?", (username,))
    ctx.db._conn.commit()

    import shutil, os
    for d in [f"config/users/{username}", f"agents/{username}"]:
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)

    return {"status": "deleted", "username": username}


@router.put("/{username}/password")
async def reset_password(username: str, body: ResetPasswordRequest, ctx: AppContext = Depends(get_ctx)):
    existing = ctx.db._conn.execute("SELECT id FROM users WHERE id = ?", (username,)).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

    if len(body.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be >= 4 chars")

    password_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    ctx.db._conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (password_hash, username),
    )
    ctx.db._conn.commit()

    return {"status": "password_reset", "username": username}
