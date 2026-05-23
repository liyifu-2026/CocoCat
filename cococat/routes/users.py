"""User management routes."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from cococat.app import get_ctx
from cococat.context import AppContext
from cococat.core.auth_service import AuthService

router = APIRouter(prefix="/api/users", tags=["users"])


class CreateUserRequest(BaseModel):
    username: str
    password: str


class ResetPasswordRequest(BaseModel):
    password: str


@router.get("")
async def list_users(ctx: AppContext = Depends(get_ctx)):
    return AuthService(ctx.db).list_users()


@router.post("")
async def create_user(body: CreateUserRequest, ctx: AppContext = Depends(get_ctx)):
    username = body.username.strip()
    service = AuthService(ctx.db)
    result, error = service.create_user(username, body.password)
    if error == "User already exists":
        raise HTTPException(status_code=409, detail=error)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return {"id": result, "status": "created"}


@router.delete("/{username}")
async def delete_user(username: str, ctx: AppContext = Depends(get_ctx)):
    if not AuthService(ctx.db).delete_user(username):
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "deleted", "username": username}


@router.put("/{username}/password")
async def reset_password(username: str, body: ResetPasswordRequest, ctx: AppContext = Depends(get_ctx)):
    ok, error = AuthService(ctx.db).reset_password(username, body.password)
    if not ok:
        raise HTTPException(status_code=404 if "not found" in error else 400, detail=error)
    return {"status": "password_reset", "username": username}
